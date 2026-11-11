"""Offline tests for the real deterministic demo path and explicit fallback labels."""
import copy,json,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
from offline_support import OfflineTestCase
from scripts.demo_workflow import build_workflow,INTAKE,SAVED_BUNDLE
from scripts.demo_runtime import validate_bundle,check_workflow,load_saved,DemoRunner,DemoError
from scripts.gradio_app import DemoUI,display
from scripts.http_service import create_app
from scripts.ai_synthesis import SynthesisService,AIConfig

class GradioDemoTests(OfflineTestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
 def test_saved_backend_fixture_has_three_v2_drafts_five_pending_actions_and_advance(self):
  b=load_saved();self.assertEqual(len(b.documents),3);self.assertEqual(len(b.proposed_actions),5);self.assertEqual(b.advance.gross_total,'1487.50')
  values=DemoUI().saved();self.assertEqual(len(values),8);self.assertIn('SAVED SYNTHETIC DEMO FIXTURE',values[0]);self.assertIsNone(values[-1]['execution_id']);self.assertIn('NOT_READY_FOR_ISSUANCE',values[5])
 def test_actual_backend_response_renders_all_documents_and_missing_information(self):
  app=create_app(cache_dir=None,ledger_path=None,onboarding_db=self.root/'backend.sqlite3',ai_service=SynthesisService(AIConfig()))
  with TestClient(app) as client:r=client.post('/v1/onboarding/preview',json=json.loads(INTAKE.read_text()))
  self.assertEqual(r.status_code,200);b=validate_bundle(r.json());before=b.model_dump_json()
  result=display(b,{'mode':'saved_demo_fixture','execution_id':None})
  self.assertEqual(result[1],b.assessment.content_markdown)
  for d,index in [('vollmacht',2),('fee_agreement',3),('advance_invoice',4)]:self.assertEqual(result[index],next(x.content_markdown for x in b.documents if x.kind==d))
  self.assertIn('pending_lawyer_approval',result[6]);self.assertEqual(b.model_dump_json(),before)
 def test_unsafe_actions_and_invoice_status_are_rejected(self):
  raw=json.loads(SAVED_BUNDLE.read_text())
  for mutate in (lambda b:b['proposed_actions'][0].update(executed=True),lambda b:b['documents'][0].update(legally_approved=True),lambda b:b['advance'].update(gross_total='0.00'),lambda b:b['client'].update(name='An unrelated client')):
   bad=copy.deepcopy(raw);mutate(bad)
   with self.assertRaises((DemoError,ValidationError)):validate_bundle(bad)
 def test_failure_shows_fixture_without_claiming_execution_success(self):
  runner=MagicMock();runner.run.side_effect=DemoError('Local n8n is unavailable.')
  result=DemoUI(runner).run();self.assertIn('n8n run unavailable',result[0]);self.assertIn('SAVED SYNTHETIC',result[0]);self.assertIsNone(result[-1]['execution_id']);self.assertFalse(result[-1]['business_success'])
 def test_only_exact_inactive_manual_workflow_can_run(self):
  w=build_workflow();check_workflow(w);self.assertEqual(len(w['nodes']),10);self.assertFalse(w['active'])
  for mutate in (lambda g:g.update(active=True),lambda g:g['nodes'][4]['parameters'].update(url='https://gmail.googleapis.com/gmail/v1/users/me/messages/send'),lambda g:g['nodes'][1]['parameters'].update(jsCode='return []'),lambda g:g['nodes'][4].update(retryOnFail=True)):
   bad=copy.deepcopy(w);mutate(bad)
   with self.assertRaises(DemoError):check_workflow(bad)
  self.assertEqual(json.loads(Path('workflows/incept_gradio_demo.json').read_text()),w)
 def test_actual_reused_n8n_validators_accept_real_v2_backend_bundle(self):
  from test_intake_workflow import IntakeWorkflowTests
  self.nodes={n['name']:n for n in build_workflow()['nodes']};run=IntakeWorkflowTests.run_code
  payload=json.loads(INTAKE.read_text());checked=run(self,'Validate Intake',payload)[0]['json'];self.assertTrue(checked['valid'])
  app=create_app(cache_dir=None,ledger_path=None,onboarding_db=self.root/'n8n.sqlite3')
  with TestClient(app) as client:bundle=client.post('/v1/onboarding/preview',json=payload).json()
  result=run(self,'Validate Onboarding Bundle',{'statusCode':200,'body':json.dumps(bundle)},{'Validate Intake':checked})[0]['json'];self.assertTrue(result['valid'])
  result['bundle']['documents'][0]['template_version']='OLD'
  failed=run(self,'Validate Onboarding Bundle',{'statusCode':200,'body':json.dumps(result['bundle'])},{'Validate Intake':checked})[0]['json'];self.assertFalse(failed['valid'])
 def test_real_execution_trace_required_and_side_effect_metadata_checked(self):
  runner=DemoRunner(runtime=self.root);runner.session.get=MagicMock(return_value=SimpleNamespace(status_code=200,headers={'X-INCEPT-Demo-Profile':'structured-preview-v1'}));runner.ensure_workflow=MagicMock(return_value='OFFLINE_WORKFLOW');runner.command=MagicMock(return_value=['offline-no-command']);runner.execute=MagicMock(return_value=SimpleNamespace(returncode=0,stdout='',stderr=''))
  runner.request=MagicMock(side_effect=[{'data':[{'id':'old'}]},{'data':[{'id':'old'}]}])
  with self.assertRaisesRegex(DemoError,'No new n8n execution'):runner.run()
 def test_double_run_blocked_and_no_arbitrary_workflow_input(self):
  runner=DemoRunner(runtime=self.root);runner.lock.acquire()
  try:
   with self.assertRaisesRegex(DemoError,'already running'):runner.run()
  finally:runner.lock.release()
 def test_gradio_ui_builds_with_two_safe_no_input_actions(self):
  import asyncio
  from scripts.gradio_app import build_app
  async def check():
   app=build_app(MagicMock())
   try:
    apis={d.get('api_name') for d in app.config['dependencies']};self.assertTrue({'run_demo','load_saved'}<=apis)
    for d in app.config['dependencies']:
     if d.get('api_name') in ('run_demo','load_saved'):self.assertEqual(d['inputs'],[])
   finally:app.close()
  asyncio.run(check())
