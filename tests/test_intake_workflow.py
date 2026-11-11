"""Offline node-code checks against bundles built by real onboarding code."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.intake_workflow import build_workflow
from scripts.http_service import create_app

ROOT=Path(__file__).resolve().parents[1]


class IntakeWorkflowTests(OfflineTestCase):
    def setUp(self):
        self.workflow=build_workflow();self.nodes={n['name']:n for n in self.workflow['nodes']}
        self.body=self.run_code('Fictional Intake',{})[0]['json']

    def run_code(self,name,data,context=None):
        node=shutil.which('node')
        if not node:self.skipTest('Node.js is needed to execute the actual n8n JavaScript validators')
        script="""const fs=require('fs');const e=JSON.parse(fs.readFileSync(0,'utf8'));
const input={first:()=>({json:e.data})};const lookup=name=>({first:()=>({json:e.context[name]})});
const result=new Function('$input','$','$execution',e.code)(input,lookup,{id:'offline-test-only'});
process.stdout.write(JSON.stringify(result));"""
        envelope={'data':data,'code':self.nodes[name]['parameters']['jsCode'],'context':context or {}}
        result=subprocess.run([node,'-e',script],input=json.dumps(envelope),text=True,capture_output=True,check=True,timeout=10)
        return json.loads(result.stdout)

    def bundle(self):
        with tempfile.TemporaryDirectory() as temp:
            app=create_app(cache_dir=None,ledger_path=None,onboarding_db=Path(temp)/'intake.sqlite3')
            with TestClient(app) as client:
                result=client.post('/v1/onboarding/preview',json=self.body)
                self.assertEqual(result.status_code,200)
                return result.json()

    def validate(self,body,status=200):
        return self.run_code('Validate Onboarding Bundle',{'statusCode':status,'body':body},{'Validate Intake':{'intake':self.body}})[0]['json']

    def test_export_is_reproducible_inactive_and_separate(self):
        self.assertFalse(self.workflow['active']);self.assertNotIn('id',self.workflow);self.assertEqual(len(self.nodes),10)
        self.assertFalse(any(n.get('credentials') or n.get('webhookId') for n in self.nodes.values()))
        allowed={'n8n-nodes-base.manualTrigger','n8n-nodes-base.code','n8n-nodes-base.if','n8n-nodes-base.httpRequest'}
        self.assertTrue(all(n['type'] in allowed for n in self.nodes.values()))
        http=self.nodes['POST Onboarding Preview'];self.assertFalse(http['retryOnFail'])
        self.assertEqual(http['parameters']['url'],'http://127.0.0.1:8002/v1/onboarding/preview')
        self.assertEqual(http['onError'],'continueRegularOutput')
        for branch in ('Input Valid?','Bundle Valid?'):
            self.assertEqual(self.workflow['connections'][branch]['main'][1][0]['node'],'Failure Summary')

    def test_real_bundle_runs_all_code_to_summary(self):
        validated=self.run_code('Validate Intake',self.body)[0]['json'];self.assertTrue(validated['valid'])
        checked=self.validate(json.dumps(self.bundle()));self.assertTrue(checked['valid'],checked)
        success=self.run_code('Success Summary',checked)[0]['json']
        summary=self.run_code('Execution Summary',success)[0]['json']
        self.assertEqual(summary['outcome'],'passed');self.assertTrue(summary['business_success'])
        self.assertEqual(summary['advance']['gross_total'],'1487.50');self.assertEqual(summary['validation']['documents'],3)
        self.assertFalse(summary['project3_three_real_integrations_satisfied'])
        self.assertEqual(summary['emails_sent'],0);self.assertEqual(summary['n8n_execution_id'],'offline-test-only')

    def test_invalid_input_stops_before_http(self):
        for path,value in [('synthetic_data',False),('idempotency_key','short')]:
            body=copy.deepcopy(self.body);body[path]=value
            self.assertFalse(self.run_code('Validate Intake',body)[0]['json']['valid'])
        body=copy.deepcopy(self.body);body['client']['email']='real@example.com'
        self.assertFalse(self.run_code('Validate Intake',body)[0]['json']['valid'])

    def test_http_conflicts_validation_and_transport_failures(self):
        for code,reason in ((409,'idempotency_conflict'),(422,'api_input_validation_error'),(503,'api_http_failure'),(401,'api_access_rejected')):
            result=self.validate({'error':{}},code);self.assertFalse(result['valid']);self.assertEqual(result['reasons'],[reason])
            failure=self.run_code('Failure Summary',result)[0]['json'];self.assertFalse(failure['business_success'])
        result=self.run_code('Validate Onboarding Bundle',{'error':'connect failed'},{'Validate Intake':{'intake':self.body}})[0]['json']
        self.assertEqual(result['reasons'],['api_transport_failure'])
        self.assertEqual(self.validate('<html>bad gateway</html>')['reasons'],['unexpected_response_format'])

    def test_unexpected_or_unsafe_bundle_is_rejected(self):
        original=self.bundle()
        mutations=[lambda b:b.update(external_actions_executed=True),lambda b:b.update(paid_api_calls=1),
                   lambda b:b['advance'].update(gross_total='0.00'),lambda b:b['documents'][0].update(state='approved'),
                   lambda b:b['proposed_actions'][0].update(executed=True),lambda b:b['proposed_actions'][0].update(due_date='2026-11-24'),
                   lambda b:b['assessment']['factual_findings'][0].update(status='verified'),lambda b:b['assessment']['guidance'][0].update(source_ids=['missing']),
                   lambda b:b['client'].update(name='another client')]
        for mutate in mutations:
            body=copy.deepcopy(original);mutate(body)
            self.assertFalse(self.validate(body)['valid'])

    def test_unknown_vat_and_decimal_rounding_use_same_server_rules(self):
        for fees in ({'net_hourly_rate':'100','currency':'EUR','vat_mode':'unknown'},
                     {'net_hourly_rate':'150.55','currency':'EUR','vat_mode':'taxable','vat_percent':'19','vat_basis':'synthetic test assumption'}):
            self.body['fees']=fees;self.assertTrue(self.validate(self.bundle())['valid'])

    def test_installed_n8n_text_output_data_field(self):
        result=self.run_code('Validate Onboarding Bundle',{'statusCode':200,'data':json.dumps(self.bundle())},
                             {'Validate Intake':{'intake':self.body}})[0]['json']
        self.assertTrue(result['valid'],result)
