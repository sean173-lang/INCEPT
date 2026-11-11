"""Offline configuration tests; live proof is recorded separately, never mocked here."""
import json
from pathlib import Path
import shutil
import subprocess
from offline_support import OfflineTestCase
from scripts.incept_sheets_workflow import build_workflow,bind_credential


class InceptSheetsWorkflowTests(OfflineTestCase):
    def setUp(self):
        self.workflow=build_workflow();self.nodes={n['name']:n for n in self.workflow['nodes']}

    def code(self,name,items,context=None):
        node=shutil.which('node')
        if not node:self.skipTest('Node.js required for actual n8n selection code checks')
        script="""const fs=require('fs');const x=JSON.parse(fs.readFileSync(0,'utf8'));
const input={first:()=>({json:x.items[0]}),all:()=>x.items.map(json=>({json}))};
const lookup=n=>({first:()=>({json:x.context[n]})});
console.log(JSON.stringify(new Function('$input','$','$execution',x.code)(input,lookup,{id:'offline-only'})));"""
        result=subprocess.run([node,'-e',script],input=json.dumps({'items':items,'context':context or {},'code':self.nodes[name]['parameters']['jsCode']}),text=True,capture_output=True,timeout=10,check=True)
        return json.loads(result.stdout)[0]['json']

    def test_read_only_config_and_sanitized_export(self):
        self.assertFalse(self.workflow['active']);self.assertEqual(len(self.nodes),10)
        path=Path(__file__).resolve().parents[1]/'workflows/incept_google_sheets_read_test.json'
        self.assertEqual(json.loads(path.read_text()),self.workflow)
        for node in self.nodes.values():
            self.assertNotIn('credentials',node);self.assertNotIn('webhookId',node)
            if node['type'].endswith('httpRequest'):
                self.assertEqual(node['parameters']['method'],'GET');self.assertFalse(node['retryOnFail'])
                self.assertIn(node['parameters']['nodeCredentialType'],['googleSheetsOAuth2Api'])
            elif node['type'].endswith('googleSheets'):
                self.assertEqual(node['parameters']['resource'],'sheet');self.assertEqual(node['parameters']['operation'],'read')
                self.assertEqual(node['typeVersion'],4.7);self.assertFalse(node['retryOnFail'])
                self.assertEqual(node['parameters']['options']['dataLocationOnSheet']['values']['range'],'A1:Z101')
        for branch in ('Unique Spreadsheet?','Unique Worksheet?'):
            self.assertEqual(self.workflow['connections'][branch]['main'][1][0]['node'],'Selection Needs Review')

    def test_bind_only_existing_credential_metadata(self):
        c={'id':'synthetic-credential-id','name':'Synthetic Google Sheets credential','type':'googleSheetsOAuth2Api'}
        bound=bind_credential(self.workflow,c)
        for n in bound['nodes']:
            if n['type'].endswith(('httpRequest','googleSheets')):
                self.assertEqual(n['credentials'],{'googleSheetsOAuth2Api':{'id':c['id'],'name':c['name']}})
        self.assertFalse(any(n.get('credentials') for n in self.workflow['nodes']))
        with self.assertRaises(ValueError):bind_credential(self.workflow,{'type':'httpHeaderAuth','id':'wrong','name':'wrong'})

    def test_unique_document_is_from_api_metadata_not_guessed(self):
        file={'id':'returned-by-google','name':'Synthetic test sheet','owners':[{'emailAddress':'ironhackproject3@gmail.com'}]}
        result=self.code('Choose Spreadsheet',[{'statusCode':200,'body':{'files':[file]}}])
        self.assertTrue(result['read_permitted']);self.assertEqual(result['spreadsheet_id'],file['id'])
        for files in ([],[file,dict(file,id='second-sheet')],[dict(file,owners=[{'emailAddress':'other@example.invalid'}])]):
            result=self.code('Choose Spreadsheet',[{'statusCode':200,'body':{'files':files}}])
            self.assertFalse(result['read_permitted'])

    def test_tabs_require_unique_grid_and_preserve_zero_id(self):
        context={'Choose Spreadsheet':{'spreadsheet_id':'synthetic-id','spreadsheet_name':'Synthetic'}}
        prop={'sheetId':0,'title':'Sheet1','sheetType':'GRID'}
        result=self.code('Choose Worksheet',[{'statusCode':200,'body':{'sheets':[{'properties':prop}]}}],context)
        self.assertEqual(result['tab_id'],0);self.assertTrue(result['read_permitted'])
        result=self.code('Choose Worksheet',[{'statusCode':200,'body':{'sheets':[{'properties':prop},{'properties':dict(prop,sheetId=1)}]}}],context)
        self.assertFalse(result['read_permitted'])

    def test_summary_does_not_export_row_values(self):
        context={'Choose Worksheet':{'spreadsheet_id':'synthetic-id','spreadsheet_name':'Synthetic','tab_id':0,'tab_title':'Sheet1'}}
        result=self.code('Sanitized Read Proof',[{'row_number':2,'name':'PRIVATE_VALUE_NOT_FOR_EXPORT'}],context)
        self.assertEqual(result['rows_returned'],1);self.assertEqual(result['column_count'],1)
        self.assertNotIn('PRIVATE_VALUE',json.dumps(result));self.assertEqual(result['spreadsheet_writes'],0)
