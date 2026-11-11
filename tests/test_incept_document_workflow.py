"""Offline checkpoint graph validation; never runs n8n or Google APIs."""
import json
from pathlib import Path
from offline_support import OfflineTestCase
from scripts.incept_document_workflow import build_workflow,PROJECT_ACCOUNT,SPREADSHEET,V2_CHECK

class DocumentWorkflowTests(OfflineTestCase):
    def test_export_reproducible_inactive_and_sanitized(self):
        graph=build_workflow();saved=json.loads((Path(__file__).resolve().parents[1]/'workflows/incept_live_documents_v2.json').read_text())
        self.assertEqual(saved,graph);self.assertFalse(graph['active']);self.assertEqual(len(graph['nodes']),37)
        serialized=json.dumps(graph);self.assertIn(PROJECT_ACCOUNT,serialized);self.assertIn(SPREADSHEET,serialized)
        from scripts.incept_corporate_workflow import build_workflow as base
        actual_sheet=next(n['parameters']['documentId']['value'] for n in base()['nodes'] if n['name']=='Read Existing Matters')
        self.assertNotIn(actual_sheet,serialized)
        for n in graph['nodes']:
            self.assertNotIn('credentials',n);self.assertNotIn('webhookId',n)
        self.assertNotIn('pinData',graph)

    def test_only_manual_trigger_and_read_only_external_operations(self):
        graph=build_workflow()
        for node in graph['nodes']:
            kind=node['type'].split('.')[-1];p=node['parameters']
            self.assertIn(kind,('manualTrigger','if','code','httpRequest','googleSheets'))
            if kind=='googleSheets':self.assertEqual(p['operation'],'read')
            if kind=='httpRequest':
                if p['method']=='POST':self.assertTrue(p['url'].startswith('http://127.0.0.1:8003/v1/onboarding/'))
                else:self.assertEqual(p['method'],'GET')
                self.assertNotIn('financial',p['url']);self.assertNotIn('tavily',p['url'])
                self.assertFalse(node.get('retryOnFail'))
            if node['name']=='Get Corporate Intelligence':
                self.assertIn("source_policy:'cache_only'",p['jsonBody']);self.assertIn('max_external_requests:0',p['jsonBody'])

    def test_v2_checks_accept_only_pending_nonissued_documents(self):
        graph=build_workflow();js=next(n['parameters']['jsCode'] for n in graph['nodes'] if n['name']=='Validate Onboarding Bundle')
        self.assertIn(V2_CHECK,js);self.assertIn("d.template_version==='2.0.0'",js)
        self.assertIn('d.ready_for_issuance===false',js);self.assertIn('d.legally_approved===false',js)
        self.assertNotIn("'GENERATION_FAILED'].includes",V2_CHECK)

    def test_binding_parameters_cannot_inject_code_or_urls(self):
        for account in ['a@example.invalid\nX','x\"; throw Error()']:
            with self.assertRaises(ValueError):build_workflow(account)
        with self.assertRaises(ValueError):build_workflow(spreadsheet_id='https://example.invalid')
        graph=build_workflow('synthetic-project@example.invalid','DEMO_SPREADSHEET_ONLY')
        self.assertNotIn(PROJECT_ACCOUNT,json.dumps(graph));self.assertNotIn(SPREADSHEET,json.dumps(graph))
