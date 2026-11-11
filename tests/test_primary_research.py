"""Offline primary-source support checks; fixtures are not live execution proof."""
from datetime import datetime,timezone,timedelta
from pathlib import Path
import tempfile
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.primary_research import PrimaryResearchRequest,verify_research,SOURCE_URL
from scripts.http_service import create_app
from scripts.onboarding import build_bundle,CORPUS
from scripts.onboarding_schemas import OnboardingRequest
from scripts.local_rag import LocalRAG

ROOT=Path(__file__).resolve().parents[1]
NOW=datetime(2026,11,11,8,tzinfo=timezone.utc)


class PrimaryResearchTests(OfflineTestCase):
    def setUp(self):
        self.intake=OnboardingRequest.model_validate_json((ROOT/'examples/onboarding_preview.json').read_text())
        self.html=(ROOT/'tests/fixtures/bgb286_sanitized.html').read_text()
        self.bundle=build_bundle(self.intake,LocalRAG(CORPUS))

    def request(self,**kw):
        return PrimaryResearchRequest(**{'synthetic_data':True,'matter':self.intake.matter,'bundle':self.bundle,'source_url':SOURCE_URL,
            'retrieved_at':NOW.isoformat(),'http_status':200,'source_html':self.html,**kw})

    def test_verified_rule_sources_and_enriched_report_are_not_case_findings(self):
        result=verify_research(self.request(),now=NOW)
        self.assertEqual(result.status,'verified');self.assertEqual(len(result.verified_rules),2)
        self.assertEqual([r.provision for r in result.verified_rules],['BGB §286(1)','BGB §286(4)'])
        self.assertTrue(all(r.evidence_status=='verified_source_rule_not_case_finding' for r in result.verified_rules))
        self.assertFalse(result.case_findings_verified);self.assertFalse(result.helper_performed_network_io)
        self.assertEqual(result.max_external_requests,1);self.assertEqual(len(result.source_sha256),64)
        report=result.enriched_assessment
        ids={s.source_id for s in report.sources}
        self.assertTrue(all(set(f.source_ids)<=ids for f in report.guidance+report.factual_findings))
        self.assertEqual(len(report.guidance),6);self.assertEqual(len(report.sources),12)
        self.assertIn('Potential Deadline Analysis',report.content_markdown)
        self.assertEqual(len(self.bundle.assessment.guidance),4)
        self.assertEqual(report.confidence,'insufficient_for_legal_conclusions')

    def test_no_confirmed_deadline_from_candidate_or_missing_dates(self):
        for candidate in ('2026-11-24',None):
            matter=self.intake.matter.model_copy(update={'claimed_deadline':candidate,'deadline_source':'synthetic statement' if candidate else None})
            result=verify_research(self.request(matter=matter,bundle=None),now=NOW)
            deadline=result.potential_deadline_analysis
            self.assertEqual(deadline.candidate_date,candidate)
            self.assertIsNone(deadline.confirmed_deadline);self.assertIsNone(deadline.calculated_deadline)
            self.assertFalse(deadline.trigger_dates_verified);self.assertEqual(deadline.state,'pending_lawyer_approval')
            self.assertTrue(deadline.missing_trigger_evidence)

    def test_changed_source_withholds_only_unsupported_claim(self):
        result=verify_research(self.request(source_html=self.html.replace('Fälligkeit','anderer Voraussetzung')),now=NOW)
        self.assertEqual(result.status,'partially_verified');self.assertEqual(len(result.verified_rules),1)
        self.assertEqual(result.verified_rules[0].provision,'BGB §286(4)')
        self.assertTrue(result.unresolved_research)

    def test_wrong_page_unrelated_url_or_hidden_text_is_not_evidence(self):
        for kwargs in ({'source_html':self.html.replace('§ 286','§ 999')},
                       {'source_url':'https://unrelated.example.invalid/source'},
                       {'source_html':'<h1>Bürgerliches Gesetzbuch § 286 Verzug des Schuldners</h1><script>'+self.html+'</script>'},
                       {'source_html':'<h1>Unavailable</h1>'}):
            with self.subTest(kwargs=kwargs):
                result=verify_research(self.request(**kwargs),now=NOW)
                self.assertEqual(result.status,'unavailable');self.assertFalse(result.verified_rules)
        malformed=self.html.replace('class="jurAbsatz"','class')
        self.assertEqual(verify_research(self.request(source_html=malformed),now=NOW).status,'unavailable')

    def test_http_network_and_stale_date_unavailable_without_fallback(self):
        for kwargs in ({'http_status':404},{'http_status':None,'retrieval_error':'network_or_http_failure'},
                       {'retrieval_error':'oversized_response'}, {'retrieved_at':'not-a-timestamp'},
                       {'retrieved_at':(NOW-timedelta(days=2)).isoformat()}, {'retrieved_at':(NOW+timedelta(hours=1)).isoformat()}):
            result=verify_research(self.request(**kwargs),now=NOW)
            self.assertEqual(result.status,'unavailable');self.assertFalse(result.verified_rules)
            self.assertTrue(result.enriched_assessment.missing_information)

    def test_unrelated_matter_is_not_applicable(self):
        matter=self.intake.matter.model_copy(update={'title':'DEMO workplace question','summary':'Synthetic employment dismissal question without any payment allegations.','requested_scope':'Review dismissal evidence.'})
        result=verify_research(self.request(matter=matter,bundle=None),now=NOW)
        self.assertEqual(result.status,'not_applicable');self.assertFalse(result.verified_rules)

    def test_bundle_context_mismatch_rejected(self):
        with self.assertRaises(ValueError):verify_research(self.request(matter=self.intake.matter.model_copy(update={'title':'Different synthetic matter'})),now=NOW)

    def test_http_helper_no_network_and_live_mode_guard(self):
        request=self.request(retrieved_at=datetime.now(timezone.utc).isoformat()).model_dump(mode='json')
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(cache_dir=None,ledger_path=None,onboarding_db=Path(tmp)/'preview.sqlite3')
            app.state.ai_synthesis.resolver.receipt_dir=Path(tmp)/'receipts'
            with TestClient(app) as client:
                result=client.post('/v1/onboarding/research/verify',json=request)
                self.assertEqual(result.status_code,200,result.text);self.assertEqual(result.json()['status'],'verified')
                request['synthetic_data']=False;self.assertEqual(client.post('/v1/onboarding/research/verify',json=request).status_code,422)
            self.assertFalse((Path(tmp)/'preview.sqlite3').exists())
            app=create_app(development=False,service_token='test-only',cache_dir=None,ledger_path=None,onboarding_db=Path(tmp)/'live.sqlite3')
            request['synthetic_data']=True
            with TestClient(app) as client:self.assertEqual(client.post('/v1/onboarding/research/verify',json=request,headers={'X-LEGALFLOW-Service-Key':'test-only'}).status_code,403)

    def test_original_source_bytes_honor_declared_iso_charset(self):
        import base64,hashlib
        html=self.html.replace('<html>','<html><head><meta charset="ISO-8859-1"></head>')
        raw=html.encode('iso-8859-1')
        result=verify_research(self.request(source_html='',source_bytes_base64=base64.b64encode(raw).decode(),source_content_type='text/html'),now=NOW)
        self.assertEqual(result.status,'verified');self.assertEqual(result.source_encoding,'iso8859-1')
        self.assertEqual(result.source_sha256,hashlib.sha256(raw).hexdigest())
        conflict=verify_research(self.request(source_html='',source_bytes_base64=base64.b64encode(raw).decode(),source_content_type='text/html; charset=utf-8'),now=NOW)
        self.assertEqual(conflict.status,'unavailable')
        corrupt=verify_research(self.request(source_html=self.html.replace('Bürgerliches','B\ufffdrgerliches')),now=NOW)
        self.assertEqual(corrupt.status,'unavailable')
