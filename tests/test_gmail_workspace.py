"""Offline selected-message, document-release and one-send safety regressions."""
import base64,copy,json,tempfile
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.gmail_workspace import GmailWorkspace,decode_message,DemoError,Store,address
from scripts.workspace_workflow import analysis_graph,check_graph,send_graph,inbox_graph
from scripts.http_service import create_app


def message(mid='abcdef123456',body='Dies ist eine fiktive Testanfrage der Beispiel GmbH. Wir bitten um Prüfung einer Rechnung über 18.750 Euro. Leistungen und Fälligkeit sind streitig.'):
 return {'id':mid,'threadId':'112233aabbcc','payload':{'mimeType':'text/plain','headers':[{'name':k,'value':v} for k,v in [('From','project@example.invalid'),('To','project@example.invalid'),('Subject','Fiktive Rechnungsanfrage'),('Message-ID','<source@example.invalid>')]],'body':{'data':base64.urlsafe_b64encode(body.encode()).decode()}}}

class Transport:
 def __init__(self,root):self.calls=[];self.root=root
 def binding(self):return {'id':'OFFLINE_ONLY','name':'offline OAuth reference'}
 def run_graph(self,g,allow_send=False):
  check_graph(g,allow_send);self.calls.append((g,allow_send))
  if allow_send:name='Send Confirmed Gmail Reply';value={'statusCode':200,'body':{'id':'abcdef112233','threadId':'112233aabbcc'}}
  else:
   js=next(n['parameters']['jsCode'] for n in g['nodes'] if n['name']=='Validate Selected Message and Intake')
   payload=json.loads(js.split('return [{json:',1)[1].rsplit('}];',1)[0])
   app=create_app(cache_dir=None,ledger_path=None,onboarding_db=self.root/'backend.sqlite3')
   with TestClient(app) as c:r=c.post('/v1/onboarding/preview',json=payload)
   assert r.status_code==200,r.text
   name='Workspace Case Result';value={'bundle':r.json(),'legal_research':[]}
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
  case=self.case();self.assertEqual(case['bundle']['matter']['summary'],self.msg['body']);self.assertIn('Beispiel GmbH',case['bundle']['client']['name'])
  repeated=self.case();self.assertTrue(repeated['reused']);self.assertEqual(len(self.transport.calls),1)
  self.assertIn('contact-not-provided@workspace.invalid',case['payload']['client']['email']);self.assertNotEqual(case['payload']['client']['email'],self.msg['from'])
 def test_missing_identity_or_non_test_message_cannot_be_processed(self):
  with self.assertRaises(DemoError):self.ws.analyze(self.msg['id'],self.profile,False)
  with self.assertRaises(DemoError):self.ws.analyze(self.msg['id'],{},True)
  self.assertEqual(self.transport.calls,[])
 def test_corrections_regenerate_backend_and_invalidate_previous_revision(self):
  a=self.case();p=copy.deepcopy(self.profile);p['address']='Supplied fictional address, Demoort';b=self.ws.analyze(self.msg['id'],p,True)
  self.assertEqual(a['id'],b['id']);self.assertNotEqual(a['revision'],b['revision']);self.assertEqual(b['bundle']['client']['address'],p['address']);self.assertEqual(len(self.transport.calls),2)
 def test_pdf_download_comes_from_current_generated_document(self):
  case=self.case()
  for kind in ('vollmacht','fee_agreement','advance_invoice'):
   path=Path(self.ws.document(case['id'],kind));self.assertTrue(path.read_bytes().startswith(b'%PDF'));self.assertIn(case['revision'],str(path));self.assertIn('DRAFT',path.name)
 def test_blocked_drafts_cannot_be_released_or_attached(self):
  case=self.case()
  for kind in ('vollmacht','fee_agreement','advance_invoice'):
   with self.assertRaises(DemoError):self.ws.release(case['id'],[kind],'DEMO lawyer',True)
   with self.assertRaises(DemoError):self.ws.preview(case['id'],'project@example.invalid','Test','Fictional self test',[kind])
 def test_complete_drafts_require_named_explicit_review_and_revision_bound_release(self):
  case=self.case(True)
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
    self.assertTrue({'refresh_inbox','select_message','analyze_mandate','regenerate_mandate','preview_reply','send_reply','run_demo','load_saved'}<=names)
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
  case=self.case(True);self.ws.release(case['id'],['vollmacht'],'DEMO reviewer',True)
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
 def test_next_day_does_not_reprocess_unchanged_message_without_explicit_reanalysis(self):
  self.case();calls=len(self.transport.calls)
  with patch('scripts.gmail_workspace.datetime') as clock:
   clock.now.return_value.date.return_value.isoformat.return_value='2026-11-12';same=self.case()
  self.assertTrue(same['reused']);self.assertEqual(len(self.transport.calls),calls)
