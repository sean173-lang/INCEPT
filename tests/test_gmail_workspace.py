"""Offline selected-message, document-release and one-send safety regressions."""
import base64,copy,json,tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.gmail_workspace import GmailWorkspace,decode_message,DemoError,Store,address
from scripts.workspace_workflow import analysis_graph,check_graph,send_graph,inbox_graph
from scripts.http_service import create_app
from scripts.ai_synthesis import AIConfig,SynthesisService


def message(mid='abcdef123456',body='Dies ist eine fiktive Testanfrage der Beispiel GmbH. Wir bitten um Prüfung einer Rechnung über 18.750 Euro. Leistungen und Fälligkeit sind streitig.'):
 return {'id':mid,'threadId':'112233aabbcc','payload':{'mimeType':'text/plain','headers':[{'name':k,'value':v} for k,v in [('From','project@example.invalid'),('To','project@example.invalid'),('Subject','Fiktive Rechnungsanfrage'),('Message-ID','<source@example.invalid>')]],'body':{'data':base64.urlsafe_b64encode(body.encode()).decode()}}}

class Transport:
 def __init__(self,root):self.calls=[];self.root=root
 def binding(self):return {'id':'OFFLINE_ONLY','name':'offline OAuth reference'}
 def run_graph(self,g,allow_send=False):
  check_graph(g,allow_send);self.calls.append((g,allow_send))
  if allow_send:name='Send Confirmed Gmail Reply';value={'statusCode':200,'body':{'id':'abcdef112233','threadId':'112233aabbcc'}}
  else:
   validation=next(n for n in g['nodes'] if n['name'] in ('Validate Selected Message and Intake','Validate Selected Message and Document Intake'))
   js=validation['parameters']['jsCode']
   payload=json.loads(js.split('return [{json:',1)[1].rsplit('}];',1)[0])
   assessment=any(n['name']=='Validate Selected Assessment' for n in g['nodes'])
   app=create_app(cache_dir=None,ledger_path=None,onboarding_db=self.root/'backend.sqlite3',ai_service=SynthesisService(AIConfig(),ledger_path=self.root/'ai.sqlite3'))
   with TestClient(app) as c:r=c.post('/v1/onboarding/assessment' if assessment else '/v1/onboarding/preview',json=payload)
   assert r.status_code==200,r.text
   if assessment:
    ai=c.post('/v1/onboarding/synthesis',json={'contract_version':'2.0','bundle':r.json()});assert ai.status_code==200,ai.text
    a=ai.json();bundle=r.json();bundle['assessment']=a['assessment']
    meta={k:a.get(k) for k in ('status','model_used','live_request','execution_mode','model','reason','contract_version','cache_hit','evidence_fingerprint','usage','input_token_upper_bound','output_token_limit','cost_display')};meta['billing_confirmed']=False
    name='Workspace Case Result';value={'bundle':bundle,'legal_research':[],'ai_synthesis':meta,'ai_analysis':a.get('synthesis'),'documents_generated':False}
   else:name='Validate Optional Document Drafts';value={'bundle':r.json()}
  return {'id':'offline-test-only','workflowId':'offline-workflow-only','data':{'resultData':{'runData':{name:[{'data':{'main':[[{'json':value}]]}}]}}}}

class GmailWorkspaceTests(OfflineTestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.transport=Transport(self.root);self.ws=GmailWorkspace(self.root/'workspace',self.transport)
  self.msg=decode_message(message());self.ws.store.put('message:'+self.msg['id'],self.msg);self.ws.store.put('account','project@example.invalid')
  self.profile={'name':'Beispiel GmbH (fiktiv)','client_type':'company','jurisdiction':'Germany','governing_law':'Germany','scope':'Prüfung der fiktiven Rechnungsforderung und Unterlagen.','counterparty':'Fiktiver Vertragspartner GmbH','address':'','sender_role':''}
  self.patch=patch('scripts.gmail_workspace.DOWNLOADS',self.root/'downloads');self.patch.start();self.addCleanup(self.patch.stop)
 def case(self,complete=False):
  p=copy.deepcopy(self.profile)
  if complete:p.update(address='Fiktive Straße 1, 00000 Demoort',firm_name='Fiktive DEMO Kanzlei',firm_address='Erfundener Kanzleiplatz 1, 00000 Demoort',lawyer_name='DEMO Anwältin Beispiel (fiktiv)',place='Demoort',representative_name='DEMO Vertreter (fiktiv)',representative_role='Geschäftsführung laut synthetischem Nachweis',authority_reference='Fiktiver Nachweis von der Testanwältin manuell geprüft',authority_checked=True)
  return self.ws.analyze(self.msg['id'],p,True)
 def test_real_ids_and_body_decoding_no_fabricated_contact_or_authority(self):
  self.assertEqual(self.msg['id'],'abcdef123456');self.assertIn('18.750 Euro',self.msg['body']);self.assertEqual(self.ws.prefill(self.msg)['name'],'')
  raw=message();raw['payload']={'mimeType':'text/html','headers':raw['payload']['headers'],'body':{'data':base64.urlsafe_b64encode(b'<p>Inquiry</p><script>secret()</script>').decode()}}
  self.assertNotIn('secret',decode_message(raw)['body'])
 def test_selected_email_controls_backend_result_and_duplicate_prevention(self):
  case=self.case();self.assertEqual(case['bundle']['matter']['summary'],self.msg['body']);self.assertIn('Beispiel GmbH',case['bundle']['client']['name']);self.assertEqual(case['bundle']['documents'],[])
  repeated=self.case();self.assertFalse(repeated['reused']);self.assertEqual(len(self.transport.calls),2)
  self.assertIn('contact-not-provided@workspace.invalid',case['payload']['client']['email']);self.assertNotEqual(case['payload']['client']['email'],self.msg['from'])
 def test_cached_case_without_current_report_version_forces_fresh_synthesis_and_preserves_history(self):
  old=self.case();old.update(execution_id='59',workflow_id='historical-workflow-59',report_version=None,assessment_mode='deterministic; no new paid AI request')
  self.ws.store.put('case-'+self.msg['id'],old)
  fresh=self.case()
  self.assertFalse(fresh['reused']);self.assertEqual(len(self.transport.calls),2)
  self.assertEqual(fresh['report_version'],'selected-mandate-de-v4')
  self.assertIn('/v1/onboarding/synthesis',str(self.transport.calls[-1][0]))
  archived=self.ws.store.get('case-history:'+self.msg['id']+':59')
  self.assertEqual(archived['execution_id'],'59');self.assertIsNone(archived['report_version'])
 def test_analysis_and_optional_document_generation_use_separate_backend_actions(self):
  case=self.case();self.assertEqual(len(self.transport.calls),1)
  self.assertIn('/v1/onboarding/assessment',str(self.transport.calls[0][0]))
  self.assertIn('/v1/onboarding/synthesis',str(self.transport.calls[0][0]))
  self.assertNotIn('/v1/onboarding/preview',str(self.transport.calls[0][0]))
  self.assertEqual(case['ai_synthesis']['contract_version'],'2.0');self.assertFalse(case['ai_synthesis']['model_used'])
  self.assertIn('Deterministischer Fallback — keine KI-Analyse akzeptiert',case['bundle']['assessment']['content_markdown'])
  self.assertIn('ai_not_authorized_or_configured',case['bundle']['assessment']['content_markdown'])
  generated=self.ws.generate_documents(case['id'])
  self.assertEqual(len(self.transport.calls),2);self.assertIn('/v1/onboarding/preview',str(self.transport.calls[1][0]))
  self.assertEqual(len(generated['bundle']['documents']),3);self.assertTrue(generated['documents_generated'])
 def test_assessment_graph_checks_all_relevant_bgb_wording_without_touching_legacy_flow(self):
  from scripts.workspace_workflow import analysis_graph
  graph=analysis_graph(self.msg,self.ws.payload(self.msg,self.profile,True),self.transport.binding())
  nodes={n['name']:n for n in graph['nodes']}
  for provision in ('611','614','631','633','634','640','641','632a','320'):
   retrieve=nodes['Retrieve Official BGB '+provision]
   self.assertEqual(retrieve['parameters']['url'],'https://www.gesetze-im-internet.de/bgb/__'+provision+'.html')
   self.assertEqual(retrieve['parameters']['options']['response']['response']['responseFormat'],'file')
   prepare=nodes['Prepare Source Check '+provision]['parameters']['jsCode']
   self.assertIn("provision:'"+provision+"'",prepare);self.assertIn('source_bytes_base64',prepare)
  synth=nodes['POST Source-Exact AI Mandate Synthesis']
  self.assertEqual(synth['parameters']['url'],'http://127.0.0.1:8003/v1/onboarding/synthesis')
  self.assertIn("contract_version:'2.0'",synth['parameters']['jsonBody'])
  self.assertFalse(synth.get('retryOnFail'));self.assertEqual(synth['parameters']['options']['timeout'],65000)
  self.assertIn('factual_excerpt_selection_mismatch',nodes['Validate Source-Exact AI Synthesis']['parameters']['jsCode'])
 def test_nonpayment_intake_does_not_retrieve_or_receive_payment_template(self):
  other=decode_message(message('112233445577','Die Gegenseite bestreitet die Kündigung des Beratungsvertrags. Wir haben eine Fristsetzung erhalten.'));other['subject']='Fiktive Vertragskündigung'
  payload=self.ws.payload(other,{**self.profile,'scope':'Prüfung der Vertragskündigung','governing_law':'Germany'},True)
  graph=analysis_graph(other,payload,self.transport.binding())
  names={n['name'] for n in graph['nodes']}
  self.assertNotIn('Retrieve Official BGB 611',names);self.assertIn('POST Source-Exact AI Mandate Synthesis',names)
  self.assertNotIn('payment-bgb',json.dumps(graph))
 def test_missing_identity_or_non_test_message_cannot_be_processed(self):
  with self.assertRaises(DemoError):self.ws.analyze(self.msg['id'],self.profile,False)
  with self.assertRaises(DemoError):self.ws.analyze(self.msg['id'],{},True)
  self.assertEqual(self.transport.calls,[])
 def test_corrections_regenerate_backend_and_invalidate_previous_revision(self):
  a=self.case();p=copy.deepcopy(self.profile);p['address']='Supplied fictional address, Demoort';b=self.ws.analyze(self.msg['id'],p,True)
  self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['revision'],b['revision']);self.assertEqual(b['bundle']['client']['address'],p['address']);self.assertEqual(len(self.transport.calls),2)
 def test_pdf_download_comes_from_current_generated_document(self):
  case=self.ws.generate_documents(self.case()['id'])
  for kind in ('vollmacht','fee_agreement','advance_invoice'):
   path=Path(self.ws.document(case['id'],kind));self.assertTrue(path.read_bytes().startswith(b'%PDF'));self.assertIn(case['revision'],str(path));self.assertIn('DRAFT',path.name)
 def test_blocked_drafts_cannot_be_released_or_attached(self):
  case=self.ws.generate_documents(self.case()['id'])
  for kind in ('vollmacht','fee_agreement','advance_invoice'):
   with self.assertRaises(DemoError):self.ws.release(case['id'],[kind],'DEMO lawyer',True)
   with self.assertRaises(DemoError):self.ws.preview(case['id'],'project@example.invalid','Test','Fictional self test',[kind])
 def test_complete_drafts_require_named_explicit_review_and_revision_bound_release(self):
  case=self.ws.generate_documents(self.case(True)['id'])
  for kind in ('vollmacht','fee_agreement'):self.assertTrue(self.ws.eligible(case,kind)[0])
  with self.assertRaises(DemoError):self.ws.release(case['id'],['vollmacht'],'DEMO lawyer',False)
  self.ws.release(case['id'],['vollmacht'],'DEMO lawyer',True);self.assertEqual(self.ws.released(case),['vollmacht'])
  changed=copy.deepcopy(case);changed['revision']='new-revision';self.assertEqual(self.ws.released(changed),[])
  self.assertFalse(self.ws.eligible(case,'advance_invoice')[0])
 def test_exact_preview_no_automatic_send_and_external_recipient_blocked(self):
  case=self.case()
  with self.assertRaises(DemoError):self.ws.preview(case['id'],'external@company.invalid','Test','Fictional self test',[])
  token,proof=self.ws.preview(case['id'],'project@example.invalid','Test','Fictional self test',[])
  calls=len(self.transport.calls)
  with self.assertRaises(DemoError):self.ws.send(token,case['id'],'project@example.invalid','Test','Fictional self test',[],False)
  with self.assertRaises(DemoError):self.ws.send(token,case['id'],'project@example.invalid','Test','Edited after preview',[],True)
  self.assertEqual(len(self.transport.calls),calls);self.assertEqual(proof['attachments'],[])
 def test_confirmed_mock_send_records_id_and_prevents_duplicate_sends(self):
  case=self.case();token,_=self.ws.preview(case['id'],'project@example.invalid','Test','Fictional self test',[])
  result=self.ws.send(token,case['id'],'project@example.invalid','Test','Fictional self test',[],True);self.assertEqual(result['gmail_message_id'],'abcdef112233')
  calls=len(self.transport.calls);again=self.ws.send(token,case['id'],'project@example.invalid','Test','Fictional self test',[],True);self.assertTrue(again['duplicate_prevented']);self.assertEqual(len(self.transport.calls),calls)
  self.assertIn('threadId',self.transport.calls[-1][0]['nodes'][-1]['parameters']['jsonBody'])
 def test_send_address_injection_and_unconfirmed_graph_are_blocked(self):
  for bad in ('a@example.invalid,b@example.invalid','x@example.invalid\r\nBcc:evil@example.invalid'):
   with self.assertRaises(DemoError):address(bad)
  with self.assertRaises(ValueError):check_graph(send_graph('RAW'),False)
 def test_failed_send_is_uncertain_and_never_retried(self):
  case=self.case();token,_=self.ws.preview(case['id'],'project@example.invalid','Test','Fictional self test',[])
  original=self.transport.run_graph;self.transport.run_graph=lambda *a,**k:(_ for _ in ()).throw(DemoError('HTTP 403 insufficient scope'))
  with self.assertRaises(DemoError):self.ws.send(token,case['id'],'project@example.invalid','Test','Fictional self test',[],True)
  self.transport.run_graph=original
  with self.assertRaisesRegex(DemoError,'prior send'):self.ws.send(token,case['id'],'project@example.invalid','Test','Fictional self test',[],True)
 def test_workspace_ui_has_real_actions_and_separate_demo_fallback(self):
  import asyncio
  from scripts.workspace_ui import build_workspace_app
  async def check():
   app=build_workspace_app(self.ws)
   try:
    names={d.get('api_name') for d in app.config['dependencies']}
    self.assertTrue({'refresh_inbox','select_message','analyze_mandate','regenerate_mandate','generate_documents','preview_reply','send_reply','run_demo','load_saved'}<=names)
   finally:app.close()
  asyncio.run(check())

 def test_company_country_never_establishes_matter_law(self):
  profile=copy.deepcopy(self.profile);profile['governing_law']='unknown'
  payload=self.ws.payload(self.msg,profile,True);self.assertEqual(payload['client']['jurisdiction'],'Germany');self.assertEqual(payload['matter']['governing_law'],'unknown')
 def test_different_selected_message_does_not_receive_previous_case(self):
  first=self.case();second=decode_message(message('112233445566','Dies ist eine andere fiktive Anfrage. Ein anderer Vertrag soll geprüft werden. Keine Rechnungsdaten angegeben.'))
  self.ws.store.put('message:'+second['id'],second);profile=copy.deepcopy(self.profile);profile.update(name='Andere Testmandantschaft',counterparty='Andere Gegenpartei')
  case=self.ws.analyze(second['id'],profile,True)
  self.assertNotEqual(first['id'],case['id']);self.assertEqual(case['bundle']['matter']['summary'],second['body']);self.assertNotIn('18.750',case['bundle']['matter']['summary'])
 def test_empty_release_does_not_claim_approval(self):
  case=self.case(True)
  with self.assertRaises(DemoError):self.ws.release(case['id'],[],'Demo reviewer',True)
  self.assertEqual(self.ws.released(case),[])
 def test_only_released_complete_pdf_enters_mime_attachment(self):
  from email.parser import BytesParser
  from email import policy
  case=self.ws.generate_documents(self.case(True)['id']);self.ws.release(case['id'],['vollmacht'],'DEMO reviewer',True)
  token,_=self.ws.preview(case['id'],'project@example.invalid','Test','Fictional self test',['vollmacht'])
  self.ws.send(token,case['id'],'project@example.invalid','Test','Fictional self test',['vollmacht'],True)
  expr=self.transport.calls[-1][0]['nodes'][-1]['parameters']['jsonBody'];payload=json.loads(expr.split('JSON.stringify(',1)[1].rsplit(') }}',1)[0])
  mime=BytesParser(policy=policy.default).parsebytes(base64.urlsafe_b64decode(payload['raw']))
  attachments=list(mime.iter_attachments());self.assertEqual(len(attachments),1);self.assertEqual(attachments[0].get_filename(),'vollmacht_DRAFT.pdf');self.assertEqual(attachments[0].get_content_type(),'application/pdf');self.assertEqual(mime['To'],'project@example.invalid')
  self.assertFalse(case['bundle']['documents'][0]['legally_approved'])
 def test_new_day_draft_date_gets_new_idempotency_key_without_inventing_case_dates(self):
  with patch('scripts.gmail_workspace.datetime') as clock:
   clock.now.return_value.date.return_value.isoformat.return_value='2026-11-11';a=self.ws.payload(self.msg,self.profile,True)
   clock.now.return_value.date.return_value.isoformat.return_value='2026-11-12';b=self.ws.payload(self.msg,self.profile,True)
  self.assertEqual(b['draft_date'],'2026-11-12');self.assertNotEqual(a['idempotency_key'],b['idempotency_key']);self.assertIsNone(b['matter']['claimed_deadline'])
 def test_deterministic_fallback_is_not_reused_as_a_current_analysis(self):
  first=self.case();calls=len(self.transport.calls)
  with patch('scripts.gmail_workspace.datetime') as clock:
   clock.now.return_value.date.return_value.isoformat.return_value='2026-11-12';same=self.case()
  self.assertFalse(same['reused']);self.assertEqual(len(self.transport.calls),calls+1);self.assertEqual(same['ai_synthesis']['live_request'],False)
 def test_only_accepted_live_v2_analysis_may_be_reused(self):
  case=self.case();case['ai_synthesis']={'status':'completed','model_used':True,'execution_mode':'live','contract_version':'2.0'}
  self.ws.store.put('case-'+self.msg['id'],case)
  same=self.case();self.assertTrue(same['reused']);self.assertEqual(len(self.transport.calls),1)
 def ui_callbacks(self):
  import asyncio
  from scripts.workspace_ui import build_workspace_app
  async def build():
   app=build_workspace_app(self.ws)
   try:return {f.fn.__name__:f.fn for f in app.fns.values() if f.fn is not None},app.config
   finally:app.close()
  return asyncio.run(build())
 def analyze_values(self):
  from scripts.workspace_ui import FIELDS
  return [self.profile.get(k,False if k=='authority_checked' else 'unknown' if k in ('client_type','jurisdiction','governing_law') else '') for k,_ in FIELDS]
 def test_analyze_ack_failure_is_persistent_and_not_a_toast_or_fixture(self):
  callbacks,_=self.ui_callbacks();result=callbacks['analyze'](self.msg['id'],self.msg['id'],False,False,*self.analyze_values())
  self.assertTrue(result[0].startswith('Analysis failed:'));self.assertIn('Tick',result[0]);self.assertEqual(result[12],'');self.assertEqual(result[7:10],(None,None,None));self.assertEqual(self.transport.calls,[])
 def test_analyze_selection_readiness_and_backend_failures_are_actionable(self):
  callbacks,_=self.ui_callbacks()
  result=callbacks['analyze'](self.msg['id'],'different-selected-message',True,False,*self.analyze_values());self.assertIn('still loading',result[0]);self.assertEqual(self.transport.calls,[])
  with patch.object(self.ws,'analyze',side_effect=DemoError('Local n8n unavailable; check service on 5678.')):
   result=callbacks['analyze'](self.msg['id'],self.msg['id'],True,False,*self.analyze_values())
  self.assertIn('Analysis failed: Local n8n unavailable',result[0]);self.assertEqual(result[12],'')
 def test_progress_success_and_cache_status_are_distinct(self):
  case=self.case();callbacks,_=self.ui_callbacks()
  self.assertIn('Analyzing',callbacks['begin']()[0])
  with patch.object(self.ws,'analyze',return_value={**case,'reused':False}):result=callbacks['analyze'](self.msg['id'],self.msg['id'],True,False,*self.analyze_values())
  self.assertIn('Assessment completed',result[0]);self.assertIn('OpenAI called this run: no',result[0]);self.assertIn('model: not configured/unknown (used: no)',result[0]);self.assertIn('source-exact v2 validation: not accepted',result[0]);self.assertIn('deterministic fallback: yes',result[0]);self.assertEqual(result[-1]['selected'],'analysis')
  with patch.object(self.ws,'analyze',return_value={**case,'reused':True}):result=callbacks['analyze'](self.msg['id'],self.msg['id'],True,False,*self.analyze_values())
  self.assertIn('No new n8n execution ran',result[0]);self.assertNotIn('Assessment completed',result[0])
 def test_new_selection_clears_old_case_results_and_confirmation(self):
  self.case();callbacks,_=self.ui_callbacks();other=decode_message(message('112233445566','Another fictional test email with no previously generated case.'))
  for msg in (self.msg,other):
   with patch.object(self.ws,'select',return_value=(msg,'offline-read-only',self.profile)):
    result=callbacks['select'](msg['id'])
   self.assertEqual(result[1],msg['body']);self.assertEqual(result[-2],'');self.assertIs(result[-15],False)
   view_start=len(result)-14;self.assertEqual(result[view_start+7:view_start+10],(None,None,None))
 def test_render_failure_is_not_misreported_as_processing_success(self):
  case=self.ws.generate_documents(self.case()['id']);callbacks,_=self.ui_callbacks()
  with patch.object(self.ws,'analyze',return_value=case),patch.object(self.ws,'document',side_effect=OSError('private path must not be exposed')) as render_pdf:
   result=callbacks['analyze'](self.msg['id'],self.msg['id'],True,False,*self.analyze_values())
  render_pdf.assert_not_called();self.assertIn('Assessment completed',result[0]);self.assertIn('excluded from Analyze',result[3]);self.assertNotIn('private path',result[0]);self.assertEqual(result[12],case['id'])
 def test_only_three_primary_workspace_tabs(self):
  _,config=self.ui_callbacks();tabs=[c['props'].get('label') for c in config['components'] if c['type']=='tabitem' and c['props'].get('id') in ('inbox','analysis','reply')]
  self.assertEqual(tabs,['INBOX','ANALYSIS','REPLY'])
