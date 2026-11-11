"""Adversarial release regressions: all input and model responses are synthetic."""
import copy
import json
from pathlib import Path
import tempfile
from offline_support import OfflineTestCase
from scripts.ai_synthesis import AISynthesis,evidence_packet,validate_synthesis
from scripts.ai_synthesis_demo import requests_for_demo,mock_response


class OriginalAuditExploits(OfflineTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.cases=requests_for_demo(self.root/'matters.sqlite3',self.root/'cache')

    def test_reject_fixture_relabeled_as_cached(self):
        request=self.cases['germany_company'].model_copy(deep=True)
        request.corporate_result.synthetic_evidence=False;request.corporate_result.status='CACHED'
        for source in request.corporate_result.sources:
            source.synthetic=False;source.category='CACHED';source.verification_status='provider_reported_unverified'
        with self.assertRaises(ValueError):evidence_packet(request)

    def test_reject_future_legal_review_date(self):
        request=self.cases['individual'].model_copy(deep=True)
        next(s for s in request.bundle.assessment.sources if s.kind=='legal_reference').reviewed_at='2099-01-01'
        with self.assertRaises(ValueError):evidence_packet(request)

    def test_reject_approval_assertion_disguised_as_question(self):
        packet=evidence_packet(self.cases['individual']);raw=json.loads(mock_response(packet)[0])
        raw['proposed_next_steps'][0]['statement']='The mandate is approved and the invoice should be issued immediately?'
        with self.assertRaises(ValueError):validate_synthesis(AISynthesis.model_validate(raw),packet)

    def test_reject_fraud_with_genuine_but_unrelated_citations(self):
        packet=evidence_packet(self.cases['individual']);raw=json.loads(mock_response(packet)[0])
        raw['source_supported_analysis'][0]['statement']='If the client transfers the assets, the company may conceal fraud and evade creditors.'
        with self.assertRaises(ValueError):validate_synthesis(AISynthesis.model_validate(raw),packet)

    def service(self,transport=None,resolver=None):
        from scripts.ai_synthesis import AIConfig,SynthesisService
        return SynthesisService(AIConfig(enabled=True,billing_verified=True,approval_id='offline-audit-only',model='MOCK',
            max_requests=20,max_input_tokens=100000,max_output_tokens=3000,max_total_tokens=2000000),
            ledger_path=self.root/'ai.sqlite3',transport=transport or mock_response,resolver=resolver)

    def allegation(self,summary):
        from scripts.incept_corporate_demo import scenarios
        from scripts.onboarding import OnboardingService
        from scripts.onboarding_schemas import OnboardingRequest
        from scripts.ai_synthesis import SynthesisRequest
        data=scenarios()['individual'];data['idempotency_key']='synthetic-audit-allegation'
        data['matter']['summary']=summary
        return SynthesisRequest(bundle=OnboardingService(self.root/'allegations.sqlite3').preview(OnboardingRequest.model_validate(data)))

    def official(self,days=0):
        from datetime import datetime,timezone,timedelta
        from unittest.mock import patch
        from scripts import companies_house
        from scripts.api_usage import UsageTracker,use_tracker,JsonCache
        from scripts.corporate_intelligence import CorporateIntelligence,CorporateRequest
        from scripts.ai_evidence import EvidenceResolver
        request=self.cases['uk_company'].model_copy(deep=True)
        request.bundle.client.approved_provider_id='00000099';request.bundle.client.registration_number='00000099'
        cache=self.root/'official-cache'
        raw={'company_name':'INCEPT DEMO LTD','company_number':'00000099','company_status':'liquidation'}
        with use_tracker(UsageTracker(cache_dir=cache)),patch.object(companies_house,'_api_request',return_value=raw) as call:
            companies_house.get_company_profile('00000099')
        call.assert_called_once()
        key=UsageTracker.key('Companies House','public_data',{'endpoint':'/company/00000099','params':None})
        if days:
            value=json.loads((cache/(key+'.json')).read_text())['value']
            value['retrieved_at']=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
            JsonCache(cache).put(key,value)
        request.corporate_result=CorporateIntelligence(cache).collect(CorporateRequest(synthetic_data=True,client=request.bundle.client,
            client_id=request.bundle.client.client_id,matter_id=request.bundle.matter.matter_id))
        return request,EvidenceResolver(cache,self.root/'receipts',allow_demo=False)

    def test_caller_flags_dates_freshness_and_source_ids_cannot_override_fixture(self):
        variants=[lambda c:setattr(c.sources[0],'verification_status','verified'),
                  lambda c:setattr(c.sources[0],'retrieved_at','2099-01-01T00:00:00+00:00'),
                  lambda c:setattr(c.sources[0],'freshness','fresh_official_verification'),
                  lambda c:setattr(c.sources[0],'source_id','forged-source'),
                  lambda c:setattr(c,'identity_verification_status','freshly_verified')]
        for mutate in variants:
            request=self.cases['germany_company'].model_copy(deep=True);mutate(request.corporate_result)
            with self.assertRaises(ValueError):evidence_packet(request)

    def test_all_known_legal_metadata_is_compared_to_server_record(self):
        for field,value in [('reviewed_at','2025-01-01'),('document_date','2026-01-01'),('url','https://example.invalid/fake'),('locator','Wrong provision'),('source_id','forged-source')]:
            request=self.cases['individual'].model_copy(deep=True)
            setattr(next(s for s in request.bundle.assessment.sources if s.kind=='legal_reference'),field,value)
            with self.assertRaises(ValueError):evidence_packet(request)
        self.assertTrue(evidence_packet(self.cases['individual'])['sources'])

    def test_authentic_shape_server_cache_supports_attributed_official_status(self):
        request,resolver=self.official();packet=evidence_packet(request,resolver)
        raw=json.loads(mock_response(packet)[0]);support=packet['issue_support']['corporate_record_status']['evidence'][0]
        raw['corporate_intelligence_observations'].append({'statement':support['quote'],'evidence_status':'official_record_reported',
            'issue_category':'corporate_record_status','assertion_type':'source_excerpt','action_state':'not_performed_pending_lawyer_approval',
            'source_ids':[support['source_id']],'evidence_quotes':[{'source_id':support['source_id'],'quote':support['quote']}]})
        validate_synthesis(AISynthesis.model_validate(raw),packet)
        result=self.service(lambda p:(json.dumps(raw),None),resolver).run(request)
        self.assertEqual(result.status,'completed');self.assertIn('HISTORICAL OFFICIAL RECORD',result.assessment.content_markdown)
        self.assertFalse(request.corporate_result.current_registry_verification)
        self.assertNotIn('insolvency_misconduct_allegation',packet['issue_support'])

    def test_stale_server_cache_is_retained_as_stale_not_promoted(self):
        request,resolver=self.official(days=90)
        before=request.model_dump_json();packet=evidence_packet(request,resolver)
        self.assertEqual(request.corporate_result.status,'NEEDS_REVIEW')
        self.assertTrue(any(s.get('freshness')=='stale' for s in packet['sources'].values()))
        result=self.service(resolver=resolver).run(request)
        self.assertEqual(result.status,'completed');self.assertIn('older than 30 days',result.assessment.content_markdown)
        self.assertEqual(before,request.model_dump_json())
        request.corporate_result.sources[0].freshness='recent_cache_not_current_verification'
        with self.assertRaises(ValueError):evidence_packet(request,resolver)

    def test_missing_legacy_provenance_cannot_be_filled_from_caller_flags(self):
        from scripts.api_usage import UsageTracker,JsonCache
        request,resolver=self.official()
        key=UsageTracker.key('Companies House','public_data',{'endpoint':'/company/00000099','params':None})
        value=json.loads((resolver.cache_dir/(key+'.json')).read_text())['value']
        JsonCache(resolver.cache_dir).put(key,{'payload':value['payload'],'retrieved_at':value['retrieved_at']})
        with self.assertRaises(ValueError):evidence_packet(request,resolver)
        self.assertEqual(self.service(resolver=resolver).run(request).reason,'evidence_provenance_rejected')

    def test_english_german_completed_assertions_are_rejected_in_question_fields(self):
        packet=evidence_packet(self.cases['individual']);original=json.loads(mock_response(packet)[0])
        values=['The mandate is approved.','The mandate is approved and the invoice should be issued immediately?',
                'The client has been accepted.','Die Mandatsannahme ist bereits erfolgt.',
                'Die Rechnung wurde freigegeben.','Die Vorschussrechnung ist sofort auszustellen.',
                'How has the client been accepted?','Ist die Rechnung bereits ausgestellt?']
        for value in values:
            raw=copy.deepcopy(original);raw['proposed_next_steps'][0]['statement']=value
            with self.assertRaises(ValueError):validate_synthesis(AISynthesis.model_validate(raw),packet)

    def test_legitimate_lawyer_review_requests_remain_allowed(self):
        packet=evidence_packet(self.cases['individual']);original=json.loads(mock_response(packet)[0])
        for text in ['Should the lawyer approve the proposed mandate?',
                     'Ist vor einer Mandatsannahme eine Interessenkollisionsprüfung erforderlich?',
                     'Soll die Vorschussanforderung nach Ergänzung der Pflichtangaben zur Freigabe vorgelegt werden?']:
            raw=copy.deepcopy(original);raw['proposed_next_steps'][0]['statement']=text
            validate_synthesis(AISynthesis.model_validate(raw),packet)

    def test_structured_performed_states_and_assertion_types_are_not_model_writable(self):
        packet=evidence_packet(self.cases['individual']);original=json.loads(mock_response(packet)[0])
        for field in ('mandate_accepted','documents_approved','invoice_issued','external_actions_executed'):
            with self.assertRaises(ValueError):AISynthesis.model_validate({**original,field:True})
        raw=copy.deepcopy(original);raw['proposed_next_steps'][0]['action_state']='executed'
        with self.assertRaises(ValueError):AISynthesis.model_validate(raw)
        raw=copy.deepcopy(original);raw['proposed_next_steps'][0]['assertion_type']='conditional_analysis'
        with self.assertRaises(ValueError):validate_synthesis(AISynthesis.model_validate(raw),packet)

    def test_client_fraud_allegation_is_allowed_only_with_explicit_attribution(self):
        request=self.allegation('The client expressly alleges fraud by the opposing party, but no supporting documents have been reviewed.')
        packet=evidence_packet(request);raw=json.loads(mock_response(packet)[0])
        output=validate_synthesis(AISynthesis.model_validate(raw),packet)
        self.assertEqual(output.mandate_summary.evidence_status,'client_alleged')
        result=self.service().run(request)
        self.assertEqual(result.status,'completed');self.assertIn('CLIENT-ALLEGED',result.assessment.content_markdown)
        raw['mandate_summary']['evidence_status']='official_record_reported'
        with self.assertRaises(ValueError):validate_synthesis(AISynthesis.model_validate(raw),packet)

    def test_unrelated_quote_cannot_support_an_available_adverse_category(self):
        request=self.allegation('The client alleges fraud by the opposing party.')
        packet=evidence_packet(request);raw=json.loads(mock_response(packet)[0])
        item=raw['questions_requiring_lawyer_review'][0]
        item.update(issue_category='fraud_allegation',statement='What original evidence supports the disputed fraud allegation?')
        with self.assertRaises(ValueError):validate_synthesis(AISynthesis.model_validate(raw),packet)

    def test_plain_late_payment_cannot_escalate_to_intentional_creditor_evasion(self):
        packet=evidence_packet(self.cases['individual']);raw=json.loads(mock_response(packet)[0])
        raw['source_supported_analysis'][0].update(issue_category='creditor_evasion_allegation',
            statement='If payment is late, the client may deliberately evade creditors.')
        with self.assertRaises(ValueError):validate_synthesis(AISynthesis.model_validate(raw),packet)
        self.assertNotIn('creditor_evasion_allegation',packet['issue_support'])

    def test_contradiction_requires_both_sources_and_explicit_uncertainty(self):
        request=self.allegation('The client alleges fraud by the opposing party. The opposing party denies fraud.')
        packet=evidence_packet(request);raw=json.loads(mock_response(packet)[0])
        validate_synthesis(AISynthesis.model_validate(raw),packet)
        raw['uncertainties_and_limitations']=[item for item in raw['uncertainties_and_limitations'] if item['issue_category']!='fraud_allegation']
        with self.assertRaises(ValueError):validate_synthesis(AISynthesis.model_validate(raw),packet)

    def test_no_fraud_statement_does_not_create_positive_allegation_support(self):
        request=self.allegation('The client reports no evidence of fraud. The invoice amount remains disputed.')
        packet=evidence_packet(request)
        self.assertNotIn('fraud_allegation',packet['issue_support'])

    def test_outside_taxonomy_stops_without_model_call(self):
        from unittest.mock import MagicMock
        request=self.allegation('The client requests a patent infringement opinion concerning a fictional product.')
        call=MagicMock(side_effect=AssertionError('No model work for unsupported scope'))
        result=self.service(call).run(request)
        self.assertEqual(result.status,'unavailable');self.assertIn('outside_controlled_taxonomy',result.reason)
        call.assert_not_called()

    def test_rejected_content_keeps_documents_amounts_and_five_actions_unchanged(self):
        request=self.cases['individual'];before=request.model_dump_json()
        def bad(packet):
            raw=json.loads(mock_response(packet)[0]);raw['proposed_next_steps'][0]['statement']='The mandate is approved?'
            return json.dumps(raw),None
        result=self.service(bad).run(request)
        self.assertEqual(result.reason,'approval_or_issuance_language_rejected')
        self.assertIsNone(result.synthesis);self.assertFalse(result.model_used)
        self.assertEqual(before,request.model_dump_json());self.assertEqual(request.bundle.advance.gross_total,'1487.50')
        self.assertEqual(len(request.bundle.proposed_actions),5)
        self.assertTrue(all(a.state=='pending_lawyer_approval' and not a.executed for a in request.bundle.proposed_actions))
        self.assertTrue(all(not d.ready_for_issuance and not d.legally_approved for d in request.bundle.documents))

    def test_primary_dates_and_ids_need_server_receipts_bound_to_this_case(self):
        from datetime import datetime,timezone
        from scripts.primary_research import PrimaryResearchRequest,verify_research,SOURCE_URL
        from scripts.onboarding_schemas import MatterInput
        from scripts.ai_evidence import EvidenceResolver
        request=self.cases['individual'].model_copy(deep=True)
        matter=MatterInput.model_validate(request.bundle.matter.model_dump(exclude={'matter_id','client_id','status'}))
        now=datetime.now(timezone.utc)
        primary=verify_research(PrimaryResearchRequest(synthetic_data=True,matter=matter,bundle=request.bundle,
            source_url=SOURCE_URL,retrieved_at=now.isoformat(),http_status=200,source_html=Path('tests/fixtures/bgb286_sanitized.html').read_text()),now=now)
        resolver=EvidenceResolver(self.root/'cache',self.root/'receipts')
        request.bundle.assessment=primary.enriched_assessment;request.primary_research=primary
        with self.assertRaises(ValueError):evidence_packet(request,resolver)
        primary=resolver.record_primary(primary,request.bundle);request.primary_research=primary
        self.assertTrue(evidence_packet(request,resolver)['sources'])
        for field,value in [('retrieved_at','2099-01-01T00:00:00+00:00'),('receipt_id','0'*64),('source_sha256','f'*64)]:
            altered=request.model_copy(deep=True);setattr(altered.primary_research,field,value)
            with self.assertRaises(ValueError):evidence_packet(altered,resolver)
        altered=request.model_copy(deep=True);altered.bundle.client.client_id='different-case';altered.bundle.matter.client_id='different-case'
        with self.assertRaises(ValueError):evidence_packet(altered,resolver)
