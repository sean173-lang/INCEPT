"""Synthetic cache-only scenarios. No live provider identity or research is claimed."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import copy
import json
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.corporate_intelligence import CorporateIntelligence,CorporateRequest,DEMO,CacheOnlyTracker
from scripts.api_usage import UsageTracker,JsonCache,UsageBlocked
from scripts.http_service import create_app
from scripts.onboarding_schemas import OnboardingRequest
from scripts.onboarding import intake_fingerprint

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,11,11,tzinfo=timezone.utc)


class CorporateIntelligenceTests(OfflineTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.base=json.loads((ROOT/'examples/onboarding_preview.json').read_text())
        self.service=CorporateIntelligence(self.root,allow_demo=True,clock=lambda:NOW)

    def client(self,jurisdiction='Germany'):
        germany=jurisdiction=='Germany'
        return {**self.base['client'],'name':'INCEPT DEMO GmbH' if germany else 'INCEPT DEMO LTD','client_type':'company','jurisdiction':jurisdiction,
                'registration_number':'DEMO-246468' if germany else 'DEMO0001','register_court':'Synthetic Berlin court' if germany else None,
                'register_type':'HRB' if germany else None,'approved_provider_id':'DEMO-INCEPT-DE' if germany else 'DEMO0001'}

    def request(self,client=None,**kw):
        return CorporateRequest(synthetic_data=True,client_id='demo-client',matter_id='demo-matter',client=client or self.client(),source_policy='approved_demo_fixture',**kw)

    def test_individual_no_provider_or_corporate_section(self):
        client={**self.base['client'],'client_type':'individual'}
        with patch.object(CacheOnlyTracker,'execute',side_effect=AssertionError('No adapter allowed')):
            result=self.service.collect(self.request(client))
        self.assertEqual(result.status,'not_applicable');self.assertIsNone(result.section_markdown);self.assertEqual(result.provider_requests,0)

    def test_german_and_uk_reuse_detail_verification_and_classified_evidence(self):
        for jurisdiction,provider in [('Germany','OpenRegister'),('United Kingdom','Companies House')]:
            with self.subTest(jurisdiction=jurisdiction):
                result=self.service.collect(self.request(self.client(jurisdiction)))
                self.assertEqual(result.identity_verification_status,'verified');self.assertEqual(result.provider,provider)
                self.assertEqual(result.status,'UNVERIFIED');self.assertTrue(result.synthetic_evidence)
                self.assertFalse(result.current_registry_verification);self.assertEqual(result.provider_requests,0);self.assertEqual(result.financial_requests,0)
                self.assertEqual(result.cached_operations,2);self.assertTrue(result.management)
                self.assertEqual(result.management[0]['source_id'],result.sources[0].source_id)
                self.assertIn('Corporate Client Intelligence',result.section_markdown)
                self.assertEqual(result.section_markdown.count('### '),7)
                self.assertTrue(result.warnings)
                source_ids={s.source_id for s in result.sources}
                self.assertTrue(all(set(f.source_ids)<=source_ids for f in result.findings))
                self.assertTrue(all(r['jurisdiction'] in ('Germany','EU') if jurisdiction=='Germany' else r['jurisdiction'] in ('UK','EU') for r in result.reference_guidance))

    def test_unknown_type_jurisdiction_missing_identity_do_not_lookup(self):
        cases=[{**self.client(),'client_type':'unknown'},{**self.client(),'jurisdiction':'unknown'},{**self.client(),'jurisdiction':'unsupported'},
               {**self.client(),'registration_number':None},{**self.client(),'approved_provider_id':None},{**self.client(),'register_court':None}]
        with patch.object(CacheOnlyTracker,'execute',side_effect=AssertionError('No speculative lookups')):
            for c in cases:
                r=self.service.collect(self.request(c));self.assertEqual(r.status,'NEEDS_REVIEW');self.assertTrue(r.missing_evidence)

    def test_name_registration_and_jurisdiction_conflicts_do_not_publish_verified_details(self):
        for changes in ({'name':'Other GmbH'},{'registration_number':'CONFLICT'},{'register_court':'Other court'}):
            r=self.service.collect(self.request({**self.client(),**changes}))
            self.assertEqual(r.identity_verification_status,'verification_failed');self.assertIsNone(r.verified_legal_name)
            self.assertTrue(r.discrepancies);self.assertIsNone(r.registered_address)

    def test_no_approval_or_missing_cache_gives_limited_assessment_without_network(self):
        r=CorporateIntelligence(self.root,allow_demo=False).collect(self.request())
        self.assertEqual(r.status,'NEEDS_REVIEW')
        request=self.request().model_copy(update={'source_policy':'cache_only'})
        r=self.service.collect(request);self.assertEqual(r.status,'UNAVAILABLE')
        self.assertIn('absence has not been established',' '.join(r.missing_evidence))

    def cached(self,when):
        entry=json.loads(DEMO.read_text())['records']['DEMO-INCEPT-DE']
        from scripts.corporate_cache import captured_record
        value=captured_record('OpenRegister','DEMO-INCEPT-DE',entry['record'])
        value['retrieved_at']=when
        key=UsageTracker.key('OpenRegister','company_details','DEMO-INCEPT-DE')
        JsonCache(self.root).put(key,value)
        return self.request().model_copy(update={'source_policy':'cache_only'})

    def test_stale_cache_is_not_current_verification(self):
        request=self.cached((NOW-timedelta(days=90)).isoformat())
        r=self.service.collect(request);self.assertEqual(r.status,'NEEDS_REVIEW');self.assertEqual(r.sources[0].freshness,'stale')
        self.assertFalse(r.current_registry_verification);self.assertTrue(any('older than 30 days' in g for g in r.missing_evidence))

    def test_provider_exception_is_nonblocking_limited_result(self):
        with patch('scripts.company_service.german_register.get_company',side_effect=TimeoutError('private message must not leak')):
            r=self.service.collect(self.request())
        self.assertEqual(r.status,'UNAVAILABLE');self.assertNotIn('private message',r.model_dump_json());self.assertEqual(r.provider_requests,0)

    def test_budget_and_financial_operations_fail_closed(self):
        r=self.service.collect(self.request(max_cached_operations=1));self.assertEqual(r.cached_operations,1)
        tracker=CacheOnlyTracker({},1,cache_dir=None)
        for provider,op,identity in [('OpenRegister','financials','id'),('Companies House','public_data',{'endpoint':'/company/DEMO0001/financials'}),('OpenAI','legal_analysis','id')]:
            with self.assertRaises(UsageBlocked):tracker.execute(provider,op,identity,lambda: self.fail('Network callback must never run'))

    def test_legacy_idempotency_hash_unchanged(self):
        self.assertEqual(intake_fingerprint(OnboardingRequest.model_validate(self.base)),'93a9d1bcf5a5deee309872c2db62af0616efe6d8334877ea29381eefc2ed2f81')

    def test_http_onboarding_uk_law_has_no_german_reference_guidance(self):
        app=create_app(cache_dir=None,ledger_path=None,onboarding_db=self.root/'preview.sqlite3',corporate_cache_dir=self.root)
        with TestClient(app) as client:
            body=copy.deepcopy(self.base);body['client']=self.client('United Kingdom');body['matter']['governing_law']='United Kingdom'
            r=client.post('/v1/onboarding/preview',json=body);self.assertEqual(r.status_code,200,r.text);bundle=r.json()
            self.assertEqual(bundle['assessment']['guidance'],[]);self.assertFalse(any(s.get('url','') and 'gesetze-im-internet' in s['url'] for s in bundle['assessment']['sources']))
            self.assertTrue(any('NOT VERIFIED' in m for m in bundle['assessment']['missing_information']))
            self.assertEqual(client.post('/v1/onboarding/preview',json=body).json(),bundle)
            self.assertEqual(bundle['advance']['gross_total'],'1487.50')
            r=client.post('/v1/onboarding/corporate-intelligence',json={**self.request(self.client('United Kingdom')).model_dump(mode='json'),'client_id':bundle['client']['client_id'],'matter_id':bundle['matter']['matter_id']})
            self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['provider'],'Companies House')
            forbidden=self.request().model_dump(mode='json');forbidden['max_external_requests']=1
            self.assertEqual(client.post('/v1/onboarding/corporate-intelligence',json=forbidden).status_code,422)

    def test_tavily_failure_preserves_registry_and_redacts_exception(self):
        with patch('scripts.company_service.CompanyService.research',side_effect=TimeoutError('sensitive-provider-detail')):
            r=self.service.collect(self.request())
        self.assertEqual(r.status,'UNVERIFIED');self.assertEqual(r.identity_verification_status,'verified')
        self.assertTrue(r.findings);self.assertTrue(any('registry findings retained' in gap for gap in r.missing_evidence))
        self.assertNotIn('sensitive-provider-detail',r.model_dump_json())

    def test_public_search_lead_dates_urls_and_unrelated_filtering(self):
        from scripts.service_schemas import ResearchResponse,CompanyIdentity,AnnotatedSource,ResearchSource
        company=CompanyIdentity(provider='OpenRegister',name='INCEPT DEMO GmbH',provider_company_id='DEMO-INCEPT-DE',jurisdiction='Germany',registration_number='DEMO-246468')
        def item(name,url,usable,identity):
            return AnnotatedSource(source=ResearchSource(title=name,url=url,content=name,published_date='2026-10-01',retrieved_at='2026-11-11T00:00:00+00:00'),source_type='third_party',identity=identity,freshness='recent',usable=usable,registration_number_match=False,legal_evidence='unverified_search_excerpt',litigation_status='unknown',verified_legal_finding=False)
        response=ResearchResponse(verification_id='a'*32,company=company,sources=[item('INCEPT DEMO GmbH company background','https://example.invalid/company',True,'possible_match'),item('Unrelated entity','https://example.invalid/other',False,'unrelated')],missing_evidence=[],coverage_note='Mocked bounded search',development=True)
        with patch('scripts.company_service.CompanyService.research',return_value=response):r=self.service.collect(self.request())
        self.assertEqual(len(r.background_leads),1);self.assertEqual(r.background_leads[0].category,'UNVERIFIED')
        source=r.sources[-1];self.assertEqual(source.url,'https://example.invalid/company');self.assertEqual(source.retrieved_at,'2026-11-11T00:00:00+00:00');self.assertEqual(source.published_date,'2026-10-01');self.assertEqual(source.freshness,'recent')
        self.assertIn('https://example.invalid/company',r.section_markdown);self.assertNotIn('https://example.invalid/other',r.section_markdown)


    def test_three_result_limit_reaches_existing_research_adapter(self):
        from scripts.company_research import research_company
        from scripts.company_research import build_research_query
        query=build_research_query('INCEPT DEMO GmbH','Germany',registration_number='DEMO-246468',register_court='Synthetic Berlin court')
        key=UsageTracker.key('Tavily','search_basic',{'query':query,'max_results':3})
        response={'company':'INCEPT DEMO GmbH','sources':[{'title':'SYNTHETIC INCEPT DEMO GmbH background','content':'INCEPT DEMO GmbH public information (synthetic test only)','url':'https://example.invalid/company','retrieved_at':'2026-11-11T00:00:00+00:00'}]}
        original=CacheOnlyTracker.__init__
        def seeded(tracker,*args,**kwargs):
            original(tracker,*args,**kwargs);tracker.records[key]=response
        with patch.object(CacheOnlyTracker,'__init__',seeded):
            r=self.service.collect(self.request(max_search_results=3))
        self.assertEqual(len(r.background_leads),1)
        self.assertIn('https://example.invalid/company',r.section_markdown)
        self.assertTrue(r.sources[-1].synthetic)
        self.assertEqual(r.sources[-1].freshness,'unknown')
        self.assertEqual(r.sources[-1].category,'UNVERIFIED')
        self.assertTrue(any('SYNTHETIC' in claim.description for claim in r.background_leads))
        self.assertTrue(all(claim.category=='UNVERIFIED' for claim in r.background_leads))


    def test_source_urls_with_underscores_remain_traceable(self):
        from scripts.corporate_intelligence import CorporateResult,CorporateSource,public_url
        url='https://example.invalid/path/source_with_underscores.pdf'
        r=CorporateResult(client_id='demo',matter_id='demo',status='UNAVAILABLE',identity_verification_status='unverified',sources=[CorporateSource(source_id='web:1',provider='Tavily cached excerpt',source_type='third_party',locator='Synthetic source URL',url=url,category='UNVERIFIED',freshness='unknown',synthetic=True)])
        self.assertIn('[source](<'+url+'>)',self.service.render(r).section_markdown)
        self.assertIsNone(public_url('https://example.invalid/<bad>'))
        self.assertIsNone(public_url('https://example.invalid/\nunsafe'))
