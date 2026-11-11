"""German document quality regressions; primary sources are frozen local snapshots."""
import copy,json,tempfile
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.document_examples import scenarios,generate
from scripts.onboarding_schemas import OnboardingRequest,ClientRecord,MatterRecord
from scripts.onboarding import advance,intake_fingerprint
from scripts.document_schemas import DocumentOptions
from scripts.legal_documents import DocumentContext,DocumentRules,generate_documents,validate_vollmacht,validate_fee_agreement,validate_advance_invoice,cross_validate,NOTICE
from scripts.http_service import create_app
from scripts.report_renderer import text as escaped

class LegalDocumentTests(OfflineTestCase):
    def context(self,name='individual',body=None):
        request=OnboardingRequest.model_validate(body or scenarios()[name])
        client=ClientRecord(**request.client.model_dump(),client_id='demo-client-'+name)
        matter=MatterRecord(**request.matter.model_dump(),client_id=client.client_id,matter_id='DEMO-AKTE-'+name)
        return DocumentContext(request,client,matter,advance(request.fees))
    def docs(self,ctx):return {d.kind:d for d in generate_documents(ctx.request,ctx.client,ctx.matter,ctx.advance)}
    def errors(self,items):return {i.code for i in items if i.severity=='error'}

    def test_two_complete_draft_sets_and_no_approval(self):
        for name in scenarios():
            ctx=self.context(name);docs=self.docs(ctx)
            self.assertEqual(docs['vollmacht'].completeness_status,'DRAFT_COMPLETE_FOR_LAWYER_REVIEW')
            self.assertEqual(docs['fee_agreement'].completeness_status,'DRAFT_COMPLETE_FOR_LAWYER_REVIEW')
            self.assertEqual(docs['advance_invoice'].completeness_status,'NOT_READY_FOR_ISSUANCE')
            self.assertFalse(cross_validate(list(docs.values()),ctx))
            for doc in docs.values():
                self.assertFalse(doc.legally_approved);self.assertFalse(doc.ready_for_issuance)
                self.assertEqual(doc.document_version,2);self.assertEqual(doc.state,'pending_lawyer_approval');self.assertEqual(doc.template_version,'2.0.0')
                self.assertTrue(doc.legal_source_ids);self.assertIn(ctx.matter.matter_id,doc.content_markdown)
                self.assertNotIn('"vat_mode":',doc.content_markdown);self.assertNotIn('None',doc.content_markdown)

    def test_primary_rules_are_verified_integrity_checked_and_exactly_scoped(self):
        rules=DocumentRules();self.assertEqual(len(rules.rag.documents),32)
        for kind in ('vollmacht','fee_agreement','advance_invoice'):
            selected=rules.select(kind)
            self.assertTrue(all(kind in r['document_types'] and r['verification_status']=='source_text_checked' for r in selected))
            self.assertTrue(all(r['source_url'].startswith(('https://www.gesetze-im-internet.de/','https://www.bundesfinanzministerium.de/')) for r in selected))
        self.assertNotIn('ustg-14',{r['id'] for r in rules.select('vollmacht')})
        self.assertNotIn('bgb-165',{r['id'] for r in rules.select('fee_agreement')})

    def test_vollmacht_has_no_fee_terms_or_default_extra_powers(self):
        ctx=self.context();text=self.docs(ctx)['vollmacht'].content_markdown
        self.assertNotIn('250,00',text);self.assertNotIn(NOTICE,text)
        self.assertIn('nicht zum Vergleichsabschluss',text);self.assertIn('Eine Prozessvollmacht wird',text)
        self.assertIn(escaped(ctx.matter.opposing_parties[0]),text);self.assertIn('Unterschrift',text)
        self.assertFalse(self.errors(validate_vollmacht(text,ctx)))

    def test_corporate_principal_and_representative_distinguished(self):
        ctx=self.context('corporate');text=self.docs(ctx)['vollmacht'].content_markdown
        self.assertIn(escaped(ctx.client.name),text);self.assertIn(escaped(ctx.options.representative.name),text)
        self.assertIn('keine reale Bestätigung',text);self.assertIn('DEMO-GESCHAEFTSFUEHRUNGSBESCHLUSS',text)
        body=scenarios()['corporate'];body['document_options'].pop('representative')
        doc=self.docs(self.context('corporate',body))['vollmacht']
        self.assertEqual(doc.completeness_status,'MISSING_INFORMATION');self.assertIn('document_options.representative',doc.missing_information)

    def test_missing_and_unapproved_scope_cannot_grant_broad_powers(self):
        body=scenarios()['individual'];body['document_options'].update(representation_scope='both',requested_ancillary_powers=['settlement','self_dealing'])
        doc=self.docs(self.context(body=body))['vollmacht'];self.assertEqual(doc.completeness_status,'LEGAL_REVIEW_REQUIRED')
        self.assertTrue({'procedural_scope','extra_powers'}<={i.code for i in doc.validation_issues})
        self.assertIn('noch keine freigegebene Ermächtigung',doc.content_markdown)

    def test_mutated_principal_and_added_authority_rejected(self):
        ctx=self.context();body=self.docs(ctx)['vollmacht'].content_markdown
        wrong=body.replace(escaped(ctx.client.name),'DEMO Other Principal')
        self.assertIn('identity_client',self.errors(validate_vollmacht(wrong,ctx)))
        self.assertIn('template_integrity',self.errors(validate_vollmacht(body+'\nUneingeschränkte Untervollmacht wird erteilt.',ctx)))
        self.assertIn('fee_in_power',self.errors(validate_vollmacht(body+'\nVorgesehener Stundensatz 999 EUR',ctx)))

    def test_mandatory_notice_and_fee_tampering_detected(self):
        ctx=self.context();body=self.docs(ctx)['fee_agreement'].content_markdown
        self.assertIn('mandatory_notice',self.errors(validate_fee_agreement(body.replace(NOTICE,''),ctx)))
        self.assertIn('template_integrity',self.errors(validate_fee_agreement(body.replace('250,00','350,00'),ctx)))
        self.assertIn('template_integrity',self.errors(validate_fee_agreement(body+'\nMindestabrechnung eine Stunde.',ctx)))

    def test_invoice_arithmetic_and_invented_identifiers_detected(self):
        ctx=self.context();body=self.docs(ctx)['advance_invoice'].content_markdown
        for amount in ['1.250,00','1.487,50']:
            # German formatting uses deterministic grouping, independent of host locale.
            self.assertIn(amount,body)
        self.assertIn('237,50',body)
        self.assertIn('template_integrity',self.errors(validate_advance_invoice(body.replace('1.487,50','1.499,00'),ctx)))
        self.assertIn('template_integrity',self.errors(validate_advance_invoice(body+'\nIBAN DE00 DEMO',ctx)))
        self.assertIn('EINMALIGE RECHNUNGSNUMMER',body);self.assertIn('STEUERNUMMER ODER UST-IDNR.',body)
        self.assertIn('invoice_invoice_number',{i.code for i in self.docs(ctx)['advance_invoice'].validation_issues})

    def test_unknown_tax_does_not_default_to_19_percent_or_zero_tax(self):
        body=scenarios()['individual'];body['fees']={'net_hourly_rate':'250.00','currency':'EUR','vat_mode':'unknown'}
        ctx=self.context(body=body);doc=self.docs(ctx)['advance_invoice']
        self.assertIsNone(ctx.advance.gross_total);self.assertIsNone(ctx.advance.vat_amount)
        self.assertIn('[BRUTTOBETRAG – OFFEN]',doc.content_markdown);self.assertNotIn('19 %',doc.content_markdown)
        self.assertIn('fees.vat_mode',doc.missing_information)

    def test_policy_rate_disagreement_is_generation_failure(self):
        body=scenarios()['individual'];body['document_options']['firm_policy']['net_hourly_rate']='300.00'
        docs=self.docs(self.context(body=body))
        for kind in ('fee_agreement','advance_invoice'):
            self.assertEqual(docs[kind].completeness_status,'GENERATION_FAILED')
            self.assertIn('abgebrochen',docs[kind].content_markdown)

    def test_cross_matter_leakage_and_arithmetic_context_rejected(self):
        a=self.context();b=self.context('corporate');mixed=list(self.docs(a).values());mixed[0]=self.docs(b)['vollmacht']
        self.assertTrue(cross_validate(mixed,a))
        wrong=a.advance.model_copy(update={'gross_total':'999.00'})
        ctx=DocumentContext(a.request,a.client,a.matter,wrong)
        self.assertIn('arithmetic_mismatch',self.errors(validate_advance_invoice(self.docs(a)['advance_invoice'].content_markdown,ctx)))
        matter=a.matter.model_copy(update={'requested_scope':'Other matter data'})
        ctx=DocumentContext(a.request,a.client,matter,a.advance)
        self.assertIn('context_mismatch',self.errors(validate_vollmacht(self.docs(a)['vollmacht'].content_markdown,ctx)))

    def test_einvoice_scope_is_not_format_compliance(self):
        from scripts.legal_documents import einvoice_assessment
        self.assertIn('Privatmandat',einvoice_assessment(self.context()))
        self.assertIn('B2B',einvoice_assessment(self.context('corporate')))
        for year,needle in [(2027,'800.000'),(2028,'abgelaufen'),(2024,'vor 2025')]:
            body=scenarios()['corporate'];body['draft_date']=str(year)+'-11-11'
            self.assertIn(needle,einvoice_assessment(self.context('corporate',body)))

    def test_invalid_options_and_approval_injection_are_rejected(self):
        from pydantic import ValidationError
        for opts in [{'ready_for_issuance':True},{'representation_scope':'all'},{'firm_policy':{'policy_id':'Demo','net_hourly_rate':'250','billing_method':'specified_increment'}},{'representative':{'name':'DEMO Signer','role':'Director','authority_status':'synthetic_evidence_checked'}}]:
            with self.assertRaises(ValidationError):DocumentOptions.model_validate(opts)

    def test_source_or_template_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'corpus.json';path.write_text('{}')
            with patch('scripts.legal_documents.CORPUS',path):
                with self.assertRaises(ValueError):DocumentRules()
        rules=DocumentRules()
        with patch.object(Path,'read_bytes',return_value=b'modified template'):
            with self.assertRaises(ValueError):rules.template('vollmacht')

    def test_http_metadata_and_idempotency_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            app=create_app(cache_dir=None,ledger_path=None,onboarding_db=Path(temp)/'demo.sqlite3')
            with TestClient(app) as client:
                body=scenarios()['individual'];r=client.post('/v1/onboarding/preview',json=body)
                self.assertEqual(r.status_code,200,r.text);self.assertEqual(client.post('/v1/onboarding/preview',json=body).json(),r.json())
                self.assertEqual(r.json()['advance']['gross_total'],'1487.50');self.assertEqual(r.json()['documents'][2]['completeness_status'],'NOT_READY_FOR_ISSUANCE')
                self.assertFalse(r.json()['external_actions_executed']);self.assertTrue(all(a['state']=='pending_lawyer_approval' for a in r.json()['proposed_actions']))

    def test_example_artifacts_are_system_generated_and_complete(self):
        with tempfile.TemporaryDirectory() as temp:
            summary=generate(temp);self.assertEqual(set(summary),{'individual','corporate'})
            for case in summary:
                for file in ('vollmacht.md','fee_agreement.md','advance_invoice.md','validation.json','review_checklist.md','input.json'):
                    self.assertTrue((Path(temp)/case/file).exists())


    def test_future_payment_date_is_not_a_received_advance(self):
        body=scenarios()['individual'];body['document_options']['payment_received_date']='2027-01-01'
        doc=self.docs(self.context(body=body))['advance_invoice']
        self.assertEqual(doc.completeness_status,'GENERATION_FAILED')
        self.assertIn('future_receipt',{i.code for i in doc.validation_issues})

    def test_persisted_legacy_bundle_is_not_silently_upgraded(self):
        import sqlite3
        from scripts.onboarding import OnboardingService
        with tempfile.TemporaryDirectory() as temp:
            db_path=Path(temp)/'legacy.sqlite3';service=OnboardingService(db_path)
            request=OnboardingRequest.model_validate(json.loads((Path(__file__).resolve().parents[1]/'examples/onboarding_preview.json').read_text()))
            first=service.preview(request);payload=first.model_dump()
            for doc in payload['documents']:
                keep={k:doc[k] for k in ('kind','state','content_markdown')};doc.clear();doc.update(keep)
                doc['content_markdown']='# DEMO historical '+doc['kind']+'\n\nOriginal historical draft retained; this content must not be replaced by a later template.'
            payload.pop('document_generation_context',None)
            with closing(sqlite3.connect(db_path)) as db:
                db.execute('UPDATE previews SET bundle=?',(json.dumps(payload),));db.commit()
            replay=service.preview(request)
            self.assertTrue(all(doc.document_version==1 and doc.template_version is None for doc in replay.documents))
            self.assertTrue(all('Original historical draft' in doc.content_markdown for doc in replay.documents))
            self.assertEqual(first.matter.matter_id,replay.matter.matter_id)


    def test_validation_issue_citations_are_in_document_rule_scope(self):
        cases=[scenarios()['individual'],scenarios()['corporate']]
        missing=copy.deepcopy(scenarios()['corporate']);missing['document_options']={};missing['fees']={'net_hourly_rate':'250.00','currency':'EUR','vat_mode':'unknown'};cases.append(missing)
        for body in cases:
            for doc in self.docs(self.context(body=body)).values():
                self.assertTrue(all(set(issue.source_ids)<=set(doc.legal_source_ids) for issue in doc.validation_issues))

    def test_document_failure_never_approves_matter_or_actions(self):
        with tempfile.TemporaryDirectory() as temp:
            app=create_app(cache_dir=None,ledger_path=None,onboarding_db=Path(temp)/'failure.sqlite3')
            with TestClient(app) as client:
                body=scenarios()['individual'];body['document_options']['firm_policy']['net_hourly_rate']='300.00'
                r=client.post('/v1/onboarding/preview',json=body);self.assertEqual(r.status_code,200,r.text);bundle=r.json()
                self.assertEqual(bundle['status'],'preview_pending_lawyer_approval')
                self.assertEqual(bundle['matter']['status'],'draft_pending_lawyer_review')
                self.assertTrue(all(d['completeness_status']=='GENERATION_FAILED' for d in bundle['documents'] if d['kind']!='vollmacht'))
                self.assertTrue(all(not d['legally_approved'] and not d['ready_for_issuance'] for d in bundle['documents']))
                self.assertTrue(all(a['state']=='pending_lawyer_approval' and not a['executed'] for a in bundle['proposed_actions']))
                for path in ('approve','issue','send'):
                    self.assertEqual(client.post('/v1/onboarding/'+path,json={'matter_id':bundle['matter']['matter_id']}).status_code,404)
                body['document_options']['ready_for_issuance']=True
                self.assertEqual(client.post('/v1/onboarding/preview',json=body).status_code,422)
