"""Offline guard checks, distinct from actual n8n/Google execution evidence."""
import json
from pathlib import Path
import shutil
import subprocess
from offline_support import OfflineTestCase
from scripts.incept_google_read_workflows import build_workflow,bind_credential,summary_code,OPERATIONS


class GoogleReadWorkflowTests(OfflineTestCase):
    def run_code(self,kind,body,status=200):
        node=shutil.which('node')
        if not node:self.skipTest('Node.js needed to execute exported validation code')
        script="""const fs=require('fs');const x=JSON.parse(fs.readFileSync(0,'utf8'));
try {const out=new Function('$input','$execution',x.code)({first:()=>({json:x.response})},{id:'offline-only'});console.log(JSON.stringify({ok:true,value:out[0].json}));}
catch(e) {console.log(JSON.stringify({ok:false,error:e.message}));}"""
        r=subprocess.run([node,'-e',script],input=json.dumps({'code':summary_code(kind),'response':{'statusCode':status,'body':body}}),text=True,capture_output=True,check=True,timeout=10)
        return json.loads(r.stdout)

    def test_exports_are_inactive_get_only_and_credential_free(self):
        root=Path(__file__).resolve().parents[1]
        for kind,op in OPERATIONS.items():
            workflow=build_workflow(kind)
            self.assertEqual(json.loads((root/'workflows'/('incept_'+kind+'_read_test.json')).read_text()),workflow)
            self.assertFalse(workflow['active']);self.assertEqual(len(workflow['nodes']),3)
            http=workflow['nodes'][1]
            self.assertEqual(http['parameters']['method'],'GET');self.assertEqual(http['parameters']['url'],op['url'])
            self.assertEqual(http['parameters']['nodeCredentialType'],op['credential_type']);self.assertFalse(http['retryOnFail'])
            self.assertFalse(http['parameters']['options']['redirect']['redirect']['followRedirects'])
            self.assertFalse(any('credentials' in n or 'webhookId' in n for n in workflow['nodes']))
            fields=op['query']['fields']
            for forbidden in ('emailAddress','description','snippet','summary','payload','messages','body'):
                self.assertNotIn(forbidden,fields)

    def test_compatible_metadata_only_binding(self):
        for kind,op in OPERATIONS.items():
            meta={'id':'synthetic-id','name':'synthetic name','type':op['credential_type']}
            workflow=bind_credential(kind,meta)
            self.assertEqual(workflow['nodes'][1]['credentials'],{op['credential_type']:{'id':'synthetic-id','name':'synthetic name'}})
            with self.assertRaises(ValueError):bind_credential(kind,{**meta,'type':'googleSheetsOAuth2Api'})

    def test_counts_do_not_export_personal_content(self):
        samples={'gmail':{'labels':[{'type':'system','name':'DO_NOT_EXPORT'},{'type':'user','name':'PRIVATE'}]},
                 'calendar':{'kind':'calendar#calendarList','items':[{'accessRole':'owner','summary':'PRIVATE','id':'personal@example.invalid'}]}}
        for kind,body in samples.items():
            result=self.run_code(kind,body);self.assertTrue(result['ok'])
            value=result['value'];self.assertEqual(value['response_count'],len(body[OPERATIONS[kind]['array']]))
            self.assertNotIn('PRIVATE',json.dumps(value));self.assertNotIn('personal@',json.dumps(value))
            self.assertEqual(value['emails_sent'],0);self.assertEqual(value['email_bodies_read'],0);self.assertEqual(value['calendar_events_created'],0)

    def test_http_failure_never_yields_pass(self):
        for kind in OPERATIONS:
            for status in (401,403,429,500):self.assertFalse(self.run_code(kind,{},status)['ok'])
            for body in (None,'unexpected',{'error':'bad'}):self.assertFalse(self.run_code(kind,body)['ok'])

    def test_pagination_and_empty_calendar_are_honest(self):
        result=self.run_code('calendar',{'kind':'calendar#calendarList','items':[],'nextPageToken':'PRIVATE_TOKEN'})
        self.assertTrue(result['ok']);self.assertEqual(result['value']['response_count'],0)
        self.assertTrue(result['value']['has_more']);self.assertNotIn('PRIVATE_TOKEN',json.dumps(result))
        self.assertEqual(result['value']['count_scope'],'first_page_up_to_100')
