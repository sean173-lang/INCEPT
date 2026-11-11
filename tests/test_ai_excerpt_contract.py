"""No sockets, model inference or live workflows: v2 selected-excerpt regressions."""
import copy,json,tempfile
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.ai_synthesis import (AIConfig,AISynthesis,SynthesisService,evidence_packet,parse_provider_output,validate_synthesis)
from scripts.ai_synthesis_demo import requests_for_demo,mock_response
from scripts.ai_excerpt_demo import mock_excerpt_response
from scripts.ai_excerpt_contract import ExcerptSynthesis,expand_selection,FACT_SECTIONS,build_excerpts
from scripts.http_service import create_app

class ExcerptContractTests(OfflineTestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.cases=requests_for_demo(self.root/'db.sqlite3',self.root/'cache')
  for request in self.cases.values():request.contract_version='2.0'
 def packet(self,kind='germany_company'):return evidence_packet(self.cases[kind])
 def proposal(self,packet):return json.loads(mock_excerpt_response(packet)[0])
 def service(self,transport=mock_excerpt_response):
  return SynthesisService(AIConfig(enabled=True,billing_verified=True,approval_id='offline-excerpts',model='MOCK',max_requests=4,max_input_tokens=200000,max_output_tokens=3000,max_total_tokens=800000),ledger_path=self.root/'ai.sqlite3',transport=transport)
 def test_34_failure_distinguishes_unsupported_inference_paraphrase_and_wrong_quote(self):
  fixture=json.loads(Path('tests/fixtures/synthesis34_sanitized.json').read_text())
  for item in fixture['items'][:2]:
   self.assertIn(item['quote'],fixture['sources'][item['source_id']]);self.assertNotEqual(item['statement'],item['quote'])
  self.assertNotIn(fixture['items'][2]['quote'],fixture['sources'][fixture['items'][2]['source_id']])
  request=self.cases['germany_company'].model_copy(update={'contract_version':'1.0'})
  packet=evidence_packet(request);raw=json.loads(mock_response(packet)[0]);item=fixture['items'][0]
  raw['factual_background'][0].update(statement=item['statement'],source_ids=[item['source_id']],evidence_quotes=[{'source_id':item['source_id'],'quote':item['quote']}])
  with self.assertRaisesRegex(ValueError,'Factual statements must be extractive'):validate_synthesis(AISynthesis.model_validate(raw),packet)
 def test_valid_selections_expand_to_exact_server_text_with_provenance_and_roles(self):
  packet=self.packet();proposal=ExcerptSynthesis.model_validate(self.proposal(packet));output,proof=expand_selection(proposal,packet)
  for field in FACT_SECTIONS:
   values=[output.mandate_summary] if field=='mandate_summary' else getattr(output,field)
   for statement,ref in zip(values,proof[field]):
    e=packet['excerpts'][ref['excerpt_id']];self.assertEqual(statement.statement,e['text']);self.assertEqual(statement.evidence_status,e['classification']);self.assertEqual(statement.source_ids,[e['source_id']]);self.assertIn('role',e);self.assertIn('provenance',e)
  self.assertNotIn('mit Sitz in Deutschland',output.model_dump_json());self.assertEqual(output.factual_background[0].statement,'INCEPT DEMO GmbH')
 def test_stable_ids_case_bound_and_modified_catalog_rejected(self):
  packet=self.packet();self.assertEqual(build_excerpts(packet),packet['excerpts'])
  reversed_packet=copy.deepcopy(packet);reversed_packet['sources']=dict(reversed(list(packet['sources'].items())));self.assertEqual(build_excerpts(reversed_packet),packet['excerpts'])
  matter=json.loads(packet['sources']['synthesis:intake:matter']['content'])['summary']
  if len(matter)>len(matter.split('. ')):
   self.assertFalse(any(e['text']==matter and 'mandate_summary' in e['allowed_sections'] for e in packet['excerpts'].values()))
  proposal=self.proposal(packet);bad=copy.deepcopy(packet);bad['excerpts'][proposal['mandate_summary']['excerpt_id']]['text']='Fabricated claim'
  with self.assertRaises(ValueError):expand_selection(ExcerptSynthesis.model_validate(proposal),bad)
 def test_fabricated_excerpt_wrong_source_and_wrong_role_rejected(self):
  packet=self.packet();raw=self.proposal(packet)
  variants=[lambda r:r['mandate_summary'].update(excerpt_id='excerpt:fake'),lambda r:r['mandate_summary'].update(source_id='synthesis:intake:client'),lambda r:r.update(mandate_summary=r['factual_background'][0])]
  for mutate in variants:
   bad=copy.deepcopy(raw);mutate(bad)
   with self.assertRaises(ValueError):expand_selection(ExcerptSynthesis.model_validate(bad),packet)
 def test_model_cannot_supply_factual_text_or_classification(self):
  for key,value in [('statement','The company committed fraud.'),('classification','verified'),('evidence_status','cached_report')]:
   raw=self.proposal(self.packet());raw['factual_background'][0][key]=value
   with self.assertRaises(ValueError):ExcerptSynthesis.model_validate(raw)
 def test_coverage_or_law_cannot_become_a_corporate_fact(self):
  packet=self.packet()
  for e in packet['excerpts'].values():
   if e['role'] not in ('coverage_limitation','legal_reference_not_case_finding'):continue
   raw=self.proposal(packet);raw['corporate_intelligence_observations']=[{'source_id':e['source_id'],'excerpt_id':e['excerpt_id']}]
   with self.assertRaises(ValueError):expand_selection(ExcerptSynthesis.model_validate(raw),packet)
 def test_unrelated_legal_only_analysis_and_adverse_escalation_fail(self):
  packet=self.packet();raw=self.proposal(packet)
  bad=copy.deepcopy(raw);item=bad['source_supported_analysis'][0];item['evidence_references']=item['evidence_references'][1:]
  with self.assertRaises(ValueError):expand_selection(ExcerptSynthesis.model_validate(bad),packet)
 def test_german_conditional_analysis_is_supported_without_weakening_deadline_guards(self):
  packet=self.packet();raw=self.proposal(packet)
  self.assertIn('clear professional German',__import__('scripts.ai_synthesis',fromlist=['system_prompt']).system_prompt('2.0'))
  item=raw['source_supported_analysis'][0]
  item['statement']='Wenn der Vertrag einen konkreten Erfolg verspricht, könnte die Abnahme nach den belegten Vertragsbedingungen für die Fälligkeit entscheidend sein.'
  expanded,_=expand_selection(ExcerptSynthesis.model_validate(raw),packet)
  self.assertEqual(expanded.source_supported_analysis[0].statement,item['statement'])
  bad=copy.deepcopy(raw);bad['source_supported_analysis'][0]['statement']='Wenn der Vertrag gilt, könnte die Vergütung innerhalb von zwei Wochen fällig werden.'
  with self.assertRaisesRegex(ValueError,'deadline period forbidden'):expand_selection(ExcerptSynthesis.model_validate(bad),packet)
  bad=copy.deepcopy(raw);bad['source_supported_analysis'][0].update(statement='If payment is disputed, the company may deliberately evade creditors.',issue_category='creditor_evasion_allegation')
  with self.assertRaises(ValueError):expand_selection(ExcerptSynthesis.model_validate(bad),packet)
 def test_approval_and_issue_states_remain_prohibited(self):
  packet=self.packet();raw=self.proposal(packet)
  for mutate in (lambda r:r.update(invoice_issued=True),lambda r:r['proposed_next_steps'][0].update(statement='The mandate is approved and the invoice should be issued immediately?')):
   bad=copy.deepcopy(raw);mutate(bad)
   with self.assertRaises(ValueError):expand_selection(ExcerptSynthesis.model_validate(bad),packet)
 def test_forged_corporate_provenance_blocks_before_mock_model(self):
  request=self.cases['germany_company'].model_copy(deep=True);request.corporate_result.synthetic_evidence=False
  call=MagicMock();result=self.service(call).run(request);self.assertEqual(result.reason,'evidence_provenance_rejected');call.assert_not_called()
 def test_missing_sources_have_explicit_uncertainty_and_no_analysis(self):
  request=self.cases['germany_company'].model_copy(deep=True);request.corporate_result=None;request.bundle.assessment.sources=[s for s in request.bundle.assessment.sources if s.kind!='legal_reference']
  result=self.service().run(request);self.assertEqual(result.status,'completed');self.assertEqual(result.synthesis.source_supported_analysis,[])
  self.assertIn('Applicable legal source evidence is unavailable',result.assessment.content_markdown);self.assertIn('Corporate record evidence is unavailable',result.assessment.content_markdown)
 def test_all_cases_http_schema_fallback_and_immutable_documents(self):
  app=create_app(service_token='offline-key',ai_service=self.service(),cache_dir=None,ledger_path=None,onboarding_db=self.root/'http.sqlite3')
  with TestClient(app) as client:
   for kind,request in self.cases.items():
    before=request.bundle.model_dump_json();r=client.post('/v1/onboarding/synthesis',json=request.model_dump(mode='json'),headers={'X-LEGALFLOW-Service-Key':'offline-key'});self.assertEqual(r.status_code,200)
    body=r.json();self.assertEqual(body['contract_version'],'2.0');self.assertEqual(body['status'],'unavailable' if kind=='ambiguous' else 'completed');self.assertEqual(before,request.bundle.model_dump_json())
    if kind!='ambiguous':self.assertTrue(body['excerpt_catalog']);self.assertTrue(body['factual_references'])
 def test_invalid_output_keeps_deterministic_fallback_and_persistent_no_retry(self):
  def bad(packet):
   raw=self.proposal(packet);raw['mandate_summary']['excerpt_id']='fake';return json.dumps(raw),None
  call=MagicMock(side_effect=bad);service=self.service(call);request=self.cases['individual'];first=service.run(request);second=service.run(request)
  self.assertEqual(first.status,'unavailable');self.assertEqual(second.reason,'previous_attempt_failed_or_uncertain_no_retry');call.assert_called_once()
  self.assertEqual(first.assessment.factual_findings,request.bundle.assessment.factual_findings)

 def test_v2_cache_rehydrates_ids_without_retry_or_state_changes(self):
  call=MagicMock(side_effect=mock_excerpt_response);request=self.cases['individual']
  a=self.service(call).run(request);b=self.service(call).run(request)
  self.assertEqual(a.status,'completed');self.assertTrue(b.cache_hit);call.assert_called_once()
  self.assertEqual(a.synthesis,b.synthesis);self.assertEqual(a.factual_references,b.factual_references)

 def test_client_allegation_and_denial_remain_attributed_and_uncertain(self):
  from scripts.incept_corporate_demo import scenarios
  from scripts.onboarding import OnboardingService
  from scripts.onboarding_schemas import OnboardingRequest
  from scripts.ai_synthesis import SynthesisRequest
  body=scenarios()['individual'];body['matter']['summary']='The client alleges fraud by the opposing party. The opposing party denies fraud.';body['idempotency_key']='excerpt-allegations-offline'
  request=SynthesisRequest(contract_version='2.0',bundle=OnboardingService(self.root/'alleged.sqlite3').preview(OnboardingRequest.model_validate(body)))
  packet=evidence_packet(request);raw=self.proposal(packet)
  e=next(e for e in packet['excerpts'].values() if e['classification']=='client_alleged' and 'mandate_summary' in e['allowed_sections'])
  raw['mandate_summary']={'source_id':e['source_id'],'excerpt_id':e['excerpt_id']}
  output,proof=expand_selection(ExcerptSynthesis.model_validate(raw),packet);self.assertEqual(output.mandate_summary.evidence_status,'client_alleged')
  raw['uncertainties_and_limitations']=[i for i in raw['uncertainties_and_limitations'] if i['issue_category']!='fraud_allegation']
  with self.assertRaises(ValueError):expand_selection(ExcerptSynthesis.model_validate(raw),packet)

 def test_n8n_validates_v2_http_response_and_rejects_changed_fact_or_proof(self):
  from scripts.incept_ai_workflow import build_workflow
  from test_incept_autonomous_workflow import AutonomousIntakeWorkflowTests
  self.nodes={n['name']:n for n in build_workflow()['nodes']};run=AutonomousIntakeWorkflowTests.code
  request=self.cases['germany_company'];result=self.service().run(request).model_dump(mode='json');base={'bundle':request.bundle.model_dump(mode='json'),'uncertainty':[]}
  actual=run(self,'Validate AI Synthesis Response',{'statusCode':200,'body':result},{'Unified Corporate Mandate Report':base})
  self.assertEqual(actual['ai_synthesis']['status'],'completed');self.assertEqual(actual['bundle']['documents'],base['bundle']['documents'])
  for mutate in (lambda r:r['synthesis']['factual_background'][0].update(statement='A paraphrase slipped into the normalized response.'),lambda r:r['factual_references']['mandate_summary'][0].update(excerpt_id='fabricated'),lambda r:r.update(excerpt_catalog={})):
   bad=copy.deepcopy(result);mutate(bad)
   rejected=run(self,'Validate AI Synthesis Response',{'statusCode':200,'body':bad},{'Unified Corporate Mandate Report':base})
   self.assertEqual(rejected['ai_synthesis']['status'],'unavailable')
  self.assertIn("contract_version:'2.0'",self.nodes['POST AI Mandate Synthesis']['parameters']['jsonBody'])

 def test_actual_sdk_v2_wire_uses_selection_schema_without_factual_prose(self):
  import httpx,os
  from unittest.mock import patch
  packet=self.packet();raw=self.proposal(packet)
  payload={'id':'resp_offline','object':'response','created_at':1,'status':'completed','model':'MOCK','output':[{'id':'msg_offline','type':'message','status':'completed','role':'assistant','content':[{'type':'output_text','text':json.dumps(raw),'annotations':[]}]}],'usage':{'input_tokens':100,'output_tokens':100,'total_tokens':200}}
  captured=[]
  def respond(transport,request):captured.append(json.loads(request.content));return httpx.Response(200,json=payload,request=request)
  service=self.service();service.mocked=False;service.transport=service.openai_call
  with patch.dict(os.environ,{'OPENAI_API_KEY':'offline-placeholder'}),patch.object(httpx.HTTPTransport,'handle_request',respond):result=service.run(self.cases['germany_company'])
  self.assertEqual(result.status,'completed');self.assertEqual(len(captured),1)
  schema=captured[0]['text']['format']['schema'];self.assertEqual(set(schema['$defs']['ExcerptSelection']['properties']),{'source_id','excerpt_id'})
  self.assertFalse(schema['$defs']['ExcerptSelection']['additionalProperties'])
  supplied=json.loads(captured[0]['input'][1]['content']);self.assertEqual(supplied['excerpts'],packet['excerpts'])

 def test_http_cannot_supply_its_own_catalogue_and_v2_cannot_downgrade(self):
  app=create_app(cache_dir=None,ledger_path=None,onboarding_db=self.root/'request.sqlite3')
  with TestClient(app) as client:
   body=self.cases['individual'].model_dump(mode='json');body['excerpt_catalog']={'fake':{'text':'Trusted'}}
   self.assertEqual(client.post('/v1/onboarding/synthesis',json=body).status_code,422)
  packet=self.packet();legacy=json.loads(mock_response(packet)[0])
  with self.assertRaises(ValueError):parse_provider_output(json.dumps(legacy),packet,'2.0')

 def test_complete_offline_demo_has_cited_conditional_analysis_and_unchanged_documents(self):
  from scripts.ai_excerpt_demo import generate
  folder=self.root/'reports';summary=generate(folder)
  self.assertEqual(summary['german_payment_dispute']['status'],'completed');self.assertEqual(summary['ambiguous']['status'],'unavailable')
  sample=json.loads((folder/'german_payment_dispute/synthesis_response.json').read_text());report=(folder/'german_payment_dispute/mandate_assessment.md').read_text()
  self.assertFalse(sample['model_used']);self.assertFalse(sample['live_request']);self.assertIn('MOCK OUTPUT',report)
  self.assertIn('server-populated exact excerpt',report);self.assertIn('Conditional AI analysis',report);self.assertIn('Offline mock demonstration',report)
  self.assertIn('SYNTHETIC',report)
  for provision in ('611','320','641'):self.assertIn('https://www.gesetze-im-internet.de/bgb/__'+provision+'.html',report)
  self.assertTrue(summary['german_payment_dispute']['documents_unchanged']);self.assertTrue(summary['german_payment_dispute']['all_five_actions_pending']);self.assertEqual(summary['german_payment_dispute']['advance_gross'],'1487.50')
  uk=json.loads((folder/'uk_company/synthesis_response.json').read_text());self.assertEqual(uk['synthesis']['source_supported_analysis'],[])

 def test_new_version_cannot_silently_reuse_old_live_approval_policy(self):
  request=self.cases['individual'].model_copy(update={'contract_version':'1.0'})
  call=MagicMock(side_effect=mock_response);self.assertEqual(self.service(call).run(request).status,'completed')
  result=self.service(call).run(self.cases['individual']);self.assertEqual(result.reason,'approval_policy_changed');call.assert_called_once()
