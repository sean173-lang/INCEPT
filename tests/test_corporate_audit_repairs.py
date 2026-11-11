"""Actual adapter/cache/report paths with synthetic payloads and mocked transports."""
import copy
from contextlib import closing
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts import german_register, companies_house
from scripts.api_usage import UsageTracker, JsonCache, use_tracker, BudgetExceeded, DuplicateRequestBlocked
from scripts.corporate_cache import CorporateCacheRecord, captured_record
from scripts.corporate_intelligence import CorporateIntelligence, CorporateRequest, DEMO, CorporateResult
from scripts.company_service import CompanyService
from scripts.service_schemas import VerificationRequest
from scripts.incept_corporate_demo import scenarios
from scripts.incept_document_workflow import build_workflow
from scripts.onboarding_schemas import OnboardingRequest, OnboardingBundle
from scripts.onboarding import OnboardingService
from scripts.http_service import create_app
import test_incept_autonomous_workflow as workflow_tests


class CorporateAuditRepairs(OfflineTestCase):
    code = workflow_tests.AutonomousIntakeWorkflowTests.code

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.nodes = {n['name']: n for n in build_workflow()['nodes']}
        self.catalog = json.loads(DEMO.read_text())['records']

    def case(self, jurisdiction='Germany'):
        return scenarios()['germany_company' if jurisdiction == 'Germany' else 'uk_company']

    def request(self, jurisdiction='Germany', **changes):
        data = dict(synthetic_data=True, client_id='demo-client', matter_id='demo-matter', client=self.case(jurisdiction)['client'])
        data.update(changes)
        return CorporateRequest(**data)

    def key(self, jurisdiction='Germany'):
        c = self.case(jurisdiction)['client']; provider = 'OpenRegister' if jurisdiction == 'Germany' else 'Companies House'
        identity = c['approved_provider_id'] if jurisdiction == 'Germany' else {'endpoint':'/company/'+c['approved_provider_id'], 'params':None}
        return UsageTracker.key(provider, 'company_details' if jurisdiction == 'Germany' else 'public_data', identity)

    def seed(self, jurisdiction='Germany', days=0):
        c = self.case(jurisdiction)['client']; provider = 'OpenRegister' if jurisdiction == 'Germany' else 'Companies House'
        raw = self.catalog[c['approved_provider_id']]['record']
        value = captured_record(provider, c['approved_provider_id'], raw)
        value['retrieved_at'] = (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
        JsonCache(self.root).put(self.key(jurisdiction), value)
        return value

    def collect(self, jurisdiction='Germany'):
        return CorporateIntelligence(self.root).collect(self.request(jurisdiction))

    def test_german_adapter_disk_cache_round_trip_to_assessment(self):
        body = self.case(); identifier = body['client']['approved_provider_id']
        sdk = MagicMock(); sdk.return_value.company.get_details_v1.return_value.model_dump.return_value = self.catalog[identifier]['record']
        with use_tracker(UsageTracker(approved=True, cache_dir=self.root)), patch.object(german_register, 'get_client', sdk):
            first = german_register.get_company(identifier)
        record = CorporateCacheRecord.model_validate(json.loads((self.root/(self.key()+'.json')).read_text())['value'])
        self.assertEqual(record.verification_status, 'provider_reported_unverified')
        self.assertEqual(record.retrieved_at, first.retrieved_at)
        with patch.object(german_register, 'get_client', side_effect=AssertionError('No second SDK call')):
            result = self.collect()
        self.assertEqual(result.status, 'CACHED'); self.assertEqual(result.identity_verification_status, 'verified')
        self.assertIn(body['client']['name'], result.section_markdown)
        self.assertEqual(result.sources[0].retrieved_at, first.retrieved_at)
        self.assertFalse(result.current_registry_verification); self.assertEqual(result.provider_requests, 0)
        sdk.assert_called_once()

    def test_uk_adapter_disk_cache_round_trip_to_assessment(self):
        identifier = self.case('UK')['client']['approved_provider_id']; raw = self.catalog[identifier]['record']
        with use_tracker(UsageTracker(cache_dir=self.root)), patch.object(companies_house, '_api_request', return_value=raw) as transport:
            first = companies_house.get_company_profile(identifier)
        with use_tracker(UsageTracker(cache_dir=self.root)), patch.object(companies_house, '_api_request', side_effect=AssertionError('No restart duplicate')):
            second = companies_house.get_company_profile(identifier)
            result = self.collect('UK')
        transport.assert_called_once(); self.assertEqual(first, second)
        self.assertEqual(first.retrieved_at, second.retrieved_at)
        self.assertTrue(second.cache_hit); self.assertEqual(result.status, 'CACHED')
        self.assertIn('INCEPT DEMO LTD', result.section_markdown)
        self.assertEqual(result.sources[0].retrieved_at, first.retrieved_at)

    def test_cache_reads_preserve_bytes_provenance_and_evidence_timestamp(self):
        value = self.seed('UK'); path = self.root/(self.key('UK')+'.json'); before = path.read_bytes()
        request = VerificationRequest(company_name='INCEPT DEMO LTD', jurisdiction='UK', provider_company_id='DEMO0001')
        times=[]
        with use_tracker(UsageTracker(cache_dir=self.root)), patch.object(companies_house, '_api_request', side_effect=AssertionError('Cache only')):
            service = CompanyService(UsageTracker())
            for _ in range(3):
                company = service.verify(request).company
                self.assertEqual(company.retrieved_at, value['retrieved_at']); self.assertTrue(company.cache_hit)
                self.assertIsNotNone(company.cache_age_seconds); self.assertGreaterEqual(company.cache_age_seconds, 0)
                times.append(company.cache_accessed_at)
        self.assertNotEqual(times[0], times[-1]); self.assertEqual(before, path.read_bytes())

    def test_stale_records_warn_with_original_age_for_both_jurisdictions(self):
        for country in ('Germany','UK'):
            value = self.seed(country, days=90); result = self.collect(country)
            self.assertEqual(result.status, 'NEEDS_REVIEW'); self.assertEqual(result.sources[0].freshness, 'stale')
            self.assertGreater(result.sources[0].cache_age_seconds, 89*86400)
            self.assertEqual(result.sources[0].retrieved_at, value['retrieved_at'])
            self.assertTrue(any(w.category=='freshness' for w in result.warnings))
            self.assertFalse(result.current_registry_verification)

    def test_legacy_missing_conflicting_and_synthetic_provenance_fail_closed(self):
        good = self.seed()
        variants = [good['payload'], {'payload':good['payload'],'retrieved_at':good['retrieved_at']},
                    {**good,'provenance':{}}, {**good,'registry_identifier':'WRONG'}, {**good,'jurisdiction':'UK'},
                    {**good,'verification_status':'verified'}, {**good,'retrieved_at':None},
                    captured_record('OpenRegister','DEMO-INCEPT-DE',good['payload'],synthetic=True)]
        for value in variants:
            JsonCache(self.root).put(self.key(), value)
            result = self.collect(); self.assertEqual(result.status,'UNAVAILABLE')
            self.assertTrue(any(w.category=='provenance' for w in result.warnings))
        JsonCache(self.root).put(self.key(), {'payload':good['payload'],'retrieved_at':good['retrieved_at']})
        with use_tracker(UsageTracker(cache_dir=self.root)), patch.object(german_register,'get_client',side_effect=AssertionError('No speculative refresh')):
            legacy = german_register.get_company('DEMO-INCEPT-DE')
            self.assertEqual(legacy.evidence_status,'legacy_unverified')
            self.assertEqual(legacy.retrieved_at,good['retrieved_at'])

    def assemble(self, corporate, *, base=None):
        route={'company':True,'client_type':'company','jurisdiction':'Germany','intake':{'matter':{'governing_law':'Germany'}},'substantive_law_status':'explicit_German_law'}
        base = copy.deepcopy(base) if base else {'bundle':{'assessment':{'content_markdown':'# DEMO','sources':[],'missing_information':[]}},'uncertainty':[]}
        return self.code('Unified Corporate Mandate Report',base,{'Route Client Type and Law':route,'Corporate Intelligence Result':corporate})

    def assert_propagates(self, result):
        assembled=self.assemble(result.model_dump(mode='json')); assessment=assembled['bundle']['assessment']
        self.assertTrue(result.warnings)
        indexed={source['source_id'] for source in assessment['sources']}
        for warning in result.warnings:
            self.assertTrue(set(warning.source_ids)<=indexed)
            self.assertIn(warning.message,assembled['uncertainty'])
            self.assertIn(warning.message,[w['message'] for w in assessment['review_warnings']])
            self.assertIn(warning.warning_id,assessment['content_markdown'])
            if warning.category=='missing_information':self.assertIn(warning.message,assessment['missing_information'])
            else:self.assertNotIn(warning.message,assessment['missing_information'])
        return assembled

    def test_missing_registry_information_and_provenance_propagate(self):
        request=self.request(); request.client.registration_number=None
        self.assert_propagates(CorporateIntelligence(self.root).collect(request))
        self.assert_propagates(self.collect())

    def test_conflicting_identity_stale_and_authority_warnings_propagate(self):
        self.seed(days=90); result=self.collect(); assembled=self.assert_propagates(result)
        self.assertIn('authority',[w['category'] for w in assembled['bundle']['assessment']['review_warnings']])
        request=self.request(); request.client.name='Other synthetic company GmbH'
        conflicting=CorporateIntelligence(self.root).collect(request)
        self.assertTrue(conflicting.discrepancies); self.assert_propagates(conflicting)

    def test_provider_failure_warnings_are_nonblocking_and_sanitized(self):
        self.seed()
        with patch('scripts.company_service.german_register.get_company', side_effect=TimeoutError('NEVER PUBLISH THIS')):
            result=self.collect()
        self.assertEqual(result.status,'UNAVAILABLE'); self.assertNotIn('NEVER PUBLISH THIS',result.model_dump_json())
        self.assertTrue(any(w.category=='provider_failure' for w in result.warnings)); self.assert_propagates(result)

    def test_ambiguous_identity_warns_without_publishing_registry_facts(self):
        self.seed()
        from scripts.service_schemas import VerificationResponse
        with patch('scripts.company_service.CompanyService.verify',return_value=VerificationResponse(status='ambiguous',message='Synthetic candidate identity requires review.',development=False)):
            result=self.collect()
        self.assertIsNone(result.verified_legal_name); self.assertEqual(result.identity_verification_status,'ambiguous')
        self.assert_propagates(result)

    def test_no_spurious_warning_and_stable_deduplication(self):
        empty=CorporateResult(client_id='demo',matter_id='demo',status='CACHED',identity_verification_status='verified')
        result=self.assemble(empty.model_dump(mode='json'))
        self.assertEqual(result['uncertainty'],[]); self.assertEqual(result['bundle']['assessment']['review_warnings'],[])
        self.seed(); real=self.collect(); first=self.assert_propagates(real); second=self.assemble(real.model_dump(mode='json'),base=first)
        self.assertEqual(first['uncertainty'],second['uncertainty'])
        self.assertEqual(first['bundle']['assessment']['review_warnings'],second['bundle']['assessment']['review_warnings'])
        individual=CorporateIntelligence(self.root).collect(self.request(client=scenarios()['individual']['client']))
        self.assertEqual(individual.warnings,[])

    def test_enriched_bundle_retains_fastapi_schema_and_existing_n8n_validator(self):
        body=self.case(); request=OnboardingRequest.model_validate(body)
        bundle=OnboardingService(self.root/'preview.sqlite3').preview(request)
        self.seed(); corporate=self.collect()
        result=self.assemble(corporate.model_dump(mode='json'),base={'bundle':bundle.model_dump(mode='json'),'uncertainty':[]})
        OnboardingBundle.model_validate(result['bundle'])
        # Original preview still passes the actual canonical v2 validator.
        checked=self.code('Validate Onboarding Bundle',{'statusCode':200,'body':bundle.model_dump(mode='json')},{'Validate Intake':{'intake':body}})
        self.assertTrue(checked['valid'])

    def test_matter_idempotency_survives_service_restart(self):
        path=self.root/'matters.sqlite3'; request=OnboardingRequest.model_validate(self.case())
        one=OnboardingService(path).preview(request); two=OnboardingService(path).preview(request)
        self.assertEqual(one,two)
        with closing(sqlite3.connect(path)) as db:
            for table in ('clients','matters','previews'):self.assertEqual(db.execute('SELECT count(*) FROM '+table).fetchone()[0],1)
        self.assertEqual(len(two.proposed_actions),5)
        self.assertTrue(all(a.state=='pending_lawyer_approval' and not a.executed for a in two.proposed_actions))

    def test_budget_failure_and_no_automatic_retry_preserved(self):
        with patch.object(german_register,'get_client') as factory,use_tracker(UsageTracker(approved=True,max_openregister_credits=0)):
            with self.assertRaises(BudgetExceeded):german_register.get_company('DEMO-INCEPT-DE')
            factory.assert_not_called()
        tracker=UsageTracker(approved=True,cache_dir=self.root,max_openregister_credits=10)
        with patch.object(german_register,'get_client',side_effect=TimeoutError('private')) as factory,use_tracker(tracker):
            with self.assertRaises(TimeoutError):german_register.get_company('DEMO-INCEPT-DE')
            with self.assertRaises(DuplicateRequestBlocked):german_register.get_company('DEMO-INCEPT-DE')
        factory.assert_called_once(); self.assertEqual(tracker.run_credits,10)
        # A fresh cache-only intake still cannot retry after this process/session ends.
        self.assertEqual(self.collect().provider_requests,0)

    def test_fastapi_exposes_typed_warning_and_timestamp_schemas(self):
        app=create_app(cache_dir=None,ledger_path=None,onboarding_db=self.root/'demo.sqlite3',corporate_cache_dir=self.root)
        self.seed()
        with TestClient(app) as client:
            schema=client.get('/openapi.json').json()['components']['schemas']
            self.assertIn('ReviewWarning',schema); self.assertIn('cache_accessed_at',schema['CompanyIdentity']['properties'])
            response=client.post('/v1/onboarding/corporate-intelligence',json=self.request().model_dump(mode='json'))
            self.assertEqual(response.status_code,200); self.assertEqual(response.json()['status'],'CACHED')
            self.assertTrue(response.json()['warnings']); self.assertIsNotNone(response.json()['sources'][0]['cache_age_seconds'])

    def test_legacy_uk_cache_cannot_establish_verified_identity(self):
        raw=self.catalog['DEMO0001']['record']
        JsonCache(self.root).put(self.key('UK'),raw)
        tracker=UsageTracker(cache_dir=self.root)
        with use_tracker(tracker),patch.object(companies_house,'_api_request',side_effect=AssertionError('No automatic request')):
            result=CompanyService(tracker).verify(VerificationRequest(company_name='INCEPT DEMO LTD',jurisdiction='UK',provider_company_id='DEMO0001'))
        self.assertEqual(result.status,'verification_failed'); self.assertIsNone(result.verification_id)

    def test_future_and_malformed_cached_evidence_never_becomes_current(self):
        value=self.seed()
        for timestamp in ((datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'not-a-date','2026-11-11T00:00:00'):
            bad={**value,'retrieved_at':timestamp};JsonCache(self.root).put(self.key(),bad)
            result=self.collect()
            self.assertNotEqual(result.status,'CACHED');self.assertFalse(result.current_registry_verification)
            with use_tracker(UsageTracker(cache_dir=self.root)),patch.object(german_register,'get_client',side_effect=AssertionError('No refresh')):
                with self.assertRaises(ValueError):german_register.get_company('DEMO-INCEPT-DE')
        path=self.root/(self.key()+'.json')
        for raw in ('{bad','{"value": []}'):
            path.write_text(raw);result=self.collect();self.assertEqual(result.status,'UNAVAILABLE')

    def test_n8n_helper_failure_keeps_provider_failure_category(self):
        fallback=self.code('Corporate Intelligence Result',{'statusCode':503})
        result=self.assemble(fallback)
        warning=result['bundle']['assessment']['review_warnings'][0]
        self.assertEqual(warning['category'],'provider_failure')
        self.assertIn(warning['message'],result['uncertainty'])
        self.assertNotIn(warning['message'],result['bundle']['assessment']['missing_information'])
