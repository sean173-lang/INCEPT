"""Offline approved-email scenarios; these are NOT evidence of a live email run."""
import base64
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.incept_autonomous_workflow import build_workflow,bind_credentials,MAILBOX,SUBJECT
from scripts.http_service import create_app

ROOT=Path(__file__).resolve().parents[1]


class AutonomousIntakeWorkflowTests(OfflineTestCase):
    def setUp(self):
        self.workflow=build_workflow();self.nodes={n['name']:n for n in self.workflow['nodes']}
        self.message_id='a123456789abcdef'
        self.intake=json.loads((ROOT/'examples/onboarding_preview.json').read_text())
        self.metadata={'id':self.message_id,'labelIds':['INBOX'],'internalDate':'1794340000000','sizeEstimate':12000,
                       'payload':{'headers':[{'name':'From','value':MAILBOX},{'name':'To','value':MAILBOX},{'name':'Subject','value':SUBJECT}]}}

    def code(self,name,data,context=None,binary_content=None):
        node=shutil.which('node')
        if not node:self.skipTest('Node.js required for actual exported validator checks')
        script="""const fs=require('fs');const x=JSON.parse(fs.readFileSync(0,'utf8'));
const items=Array.isArray(x.data)?x.data:[x.data];const input={first:()=>({json:items[0],binary:x.binary_content?{official_source:{data:'managed-binary'}}:undefined}),all:()=>items.map(json=>({json}))};
const lookup=name=>({first:()=>{if(!(name in x.context))throw new Error('not executed');return {json:x.context[name]};}});
const AsyncFunction=Object.getPrototypeOf(async function(){}).constructor;
(async()=>{const out=await new AsyncFunction('$input','$','$execution',x.code).call({helpers:{getBinaryDataBuffer:async()=>Buffer.from(x.binary_content||'','base64')}},input,lookup,{id:'OFFLINE-NOT-LIVE'});console.log(JSON.stringify(out[0].json));})().catch(e=>{console.error(e.message);process.exit(1);});"""
        result=subprocess.run([node,'-e',script],input=json.dumps({'code':self.nodes[name]['parameters']['jsCode'],'data':data,'context':context or {},'binary_content':binary_content}),capture_output=True,text=True,timeout=10,check=True)
        return json.loads(result.stdout)

    def extracted(self,intake=None):
        raw='INCEPT_SYNTHETIC_INTAKE_V1\n'+json.dumps(self.intake if intake is None else intake)
        body={'id':self.message_id,'payload':{'mimeType':'text/plain','body':{'data':base64.urlsafe_b64encode(raw.encode()).decode()}}}
        return self.code('Extract Approved Inquiry',{'statusCode':200,'body':body},{'Validate Approved Metadata':{'message_id':self.message_id}})

    def test_export_guards_body_access_and_has_no_fixture_fallback(self):
        self.assertEqual(json.loads((ROOT/'workflows/incept_autonomous_intake_dev.json').read_text()),self.workflow)
        self.assertFalse(self.workflow['active']);self.assertEqual(len(self.nodes),30)
        self.assertFalse(any(n.get('credentials') or n.get('webhookId') for n in self.nodes.values()))
        for n in self.nodes.values():
            if n['type'].endswith('httpRequest'):
                p=n['parameters'];self.assertFalse(n['retryOnFail'])
                if p['method']=='POST':self.assertIn(p['url'],('http://127.0.0.1:8002/v1/onboarding/preview','http://127.0.0.1:8002/v1/onboarding/research/verify'))
                else:self.assertEqual(p['method'],'GET')
            if n['type'].endswith('googleSheets'):self.assertEqual(n['parameters']['operation'],'read')
        self.assertEqual(self.workflow['connections']['Metadata Approved?']['main'][0][0]['node'],'Read Specific Approved Body')
        self.assertEqual(self.workflow['connections']['Metadata Approved?']['main'][1][0]['node'],'Clean Stop Summary')
        metadata=self.nodes['Read Candidate Headers']['parameters']['queryParameters']['parameters']
        self.assertIn({'name':'format','value':'metadata'},metadata)
        self.assertIn('messages(id)',self.nodes['Find Approved Demo Inquiry']['parameters']['queryParameters']['parameters'][-1]['value'])
        self.assertNotIn('Musterwerk',json.dumps(self.workflow))

    def test_missing_or_ambiguous_email_stops_without_substitution(self):
        result=self.code('Check Demo Search',{'statusCode':200,'body':{'resultSizeEstimate':0}})
        self.assertEqual(result['state'],'NEEDS_DEMO_EMAIL');self.assertFalse(result['ready'])
        final=self.code('Clean Stop Summary',result)
        self.assertFalse(final['fixture_substitution']);self.assertEqual(final['email_bodies_read'],0)
        self.assertFalse(final['sheets_executed']);self.assertFalse(final['documents_generated'])
        result=self.code('Check Demo Search',{'statusCode':200,'body':{'messages':[{'id':self.message_id},{'id':'b123456789abcdef'}]}})
        self.assertEqual(result['state'],'NEEDS_REVIEW')
        self.assertEqual(self.code('Check Demo Search',{'statusCode':403,'body':{}})['state'],'ERROR')

    def test_headers_must_match_before_body_read(self):
        context={'Check Demo Search':{'message_id':self.message_id}}
        self.assertTrue(self.code('Validate Approved Metadata',{'statusCode':200,'body':self.metadata},context)['ready'])
        for mutate in (lambda m:m['payload']['headers'][0].update(value='other@example.invalid'),
                       lambda m:m['payload']['headers'][2].update(value='Unapproved inquiry'),
                       lambda m:m.update(id='other'),lambda m:m.update(sizeEstimate=100000),lambda m:m.update(labelIds=['TRASH'])):
            metadata=copy.deepcopy(self.metadata);mutate(metadata)
            result=self.code('Validate Approved Metadata',{'statusCode':200,'body':metadata},context)
            self.assertFalse(result['ready']);self.assertEqual(result['email_bodies_read'],0)

    def test_extraction_keeps_uncertainty_and_derives_idempotency(self):
        result=self.extracted();self.assertTrue(result['ready'])
        self.assertEqual(result['intake']['client'],self.intake['client'])
        self.assertEqual(result['intake']['idempotency_key'],'incept-gmail-'+self.message_id)
        self.assertFalse(result['provenance']['fixture_substitution'])
        self.assertTrue(result['missing_fields'])
        missing=copy.deepcopy(self.intake);missing['client'].pop('address')
        result=self.extracted(missing);self.assertFalse(result['ready']);self.assertIn('client.address',result['missing_fields'])
        self.assertFalse(self.extracted({'synthetic_data':False})['ready'])

    def test_unstructured_body_never_falls_back_to_fixture(self):
        data=base64.urlsafe_b64encode(b'Ordinary personal email. Do not substitute a fictional intake.').decode()
        result=self.code('Extract Approved Inquiry',{'statusCode':200,'body':{'id':self.message_id,'payload':{'mimeType':'text/plain','body':{'data':data}}}},
                         {'Validate Approved Metadata':{'message_id':self.message_id}})
        self.assertEqual(result['state'],'NEEDS_INTAKE_INFORMATION');self.assertNotIn('intake',result)

    def test_sheet_lookup_does_not_claim_absence_or_name_verified_identity(self):
        context={'Validate Intake':{'intake':self.intake}}
        result=self.code('Assess Existing Matter Lookup',[{'client_name':self.intake['client']['name'],'matter_id':'synthetic-id','status':'DEMO'}],context)
        self.assertEqual(result['candidate_count'],1);self.assertIn('name_only',result['certainty'])
        self.assertNotIn('synthetic-id',json.dumps(result))
        result=self.code('Assess Existing Matter Lookup',[{}],context)
        self.assertEqual(result['rows_read'],0);self.assertIn('not proof of absence',result['limitation'])
        self.assertFalse(self.code('Assess Existing Matter Lookup',[{'error':'failed'}],context)['ready'])

    def test_calendar_check_is_not_availability_or_deadline_verification(self):
        result=self.code('Check Calendar Metadata',{'statusCode':200,'body':{'kind':'calendar#calendarList','items':[{'primary':True}]}})
        self.assertTrue(result['ready']);self.assertFalse(result['availability_verified']);self.assertFalse(result['event_data_read'])
        self.assertFalse(self.code('Check Calendar Metadata',{'statusCode':403,'body':{}})['ready'])

    def test_offline_full_path_uses_real_onboarding_and_replays_one_matter(self):
        extracted=self.extracted();valid=self.code('Validate Intake',extracted);self.assertTrue(valid['valid'])
        with tempfile.TemporaryDirectory() as tmp:
            app=create_app(cache_dir=None,ledger_path=None,onboarding_db=Path(tmp)/'demo.sqlite3')
            with TestClient(app) as client:
                r=client.post('/v1/onboarding/preview',json=valid['intake']);self.assertEqual(r.status_code,200)
                self.assertEqual(client.post('/v1/onboarding/preview',json=valid['intake']).json(),r.json())
            checked=self.code('Validate Onboarding Bundle',{'statusCode':200,'body':r.json()},{'Validate Intake':valid})
        self.assertTrue(checked['valid'],checked)
        result=self.code('Integrated Onboarding Report',checked,{'Validate Onboarding Bundle':checked,'Extract Approved Inquiry':extracted,
                         'Assess Existing Matter Lookup':{'lookup_status':'offline synthetic lookup','limitation':'bounded lookup'},
                         'Check Calendar Metadata':{'calendar_count':1,'availability_verified':False}})
        self.assertEqual(result['state'],'PREVIEW_READY_FOR_LAWYER_REVIEW')
        self.assertFalse(result['autonomous_research']);self.assertFalse(result['source_grounded_live_case_research_performed'])
        self.assertEqual(result['external_writes'],0);self.assertEqual(len(result['bundle']['documents']),3)
        self.assertEqual(result['bundle']['advance']['gross_total'],'1487.50')

    def test_credentials_cannot_be_swapped_between_services(self):
        metadata={k:{'type':k,'id':'synthetic-'+k,'name':'synthetic metadata'} for k in ('gmailOAuth2','googleSheetsOAuth2Api','googleCalendarOAuth2Api')}
        bound=bind_credentials(metadata);self.assertTrue(bound['nodes'][1].get('credentials'))
        metadata['gmailOAuth2']['type']='googleSheetsOAuth2Api'
        with self.assertRaises(ValueError):bind_credentials(metadata)

    def test_review_summary_does_not_erase_already_executed_stages(self):
        result=self.code('Clean Stop Summary',{'state':'NEEDS_REVIEW','stage':'validation'},
                         {'Read Specific Approved Body':{'statusCode':200},'Assess Existing Matter Lookup':{'rows_read':1},'Check Calendar Metadata':{'calendar_count':1}})
        self.assertEqual(result['email_bodies_read'],1);self.assertTrue(result['sheets_executed']);self.assertTrue(result['calendar_executed'])

    def test_one_case_relevant_source_action_is_allowlisted(self):
        context={'Validate Intake':{'intake':self.intake}}
        plan=self.code('Plan Bounded Primary Research',{},context)
        self.assertTrue(plan['relevant']);self.assertEqual(plan['max_source_requests'],1)
        self.assertEqual(plan['source_url'],'https://www.gesetze-im-internet.de/bgb/__286.html')
        source=self.nodes['Retrieve Official Provision']
        self.assertEqual(source['parameters']['url'],plan['source_url']);self.assertFalse(source['retryOnFail'])
        self.assertFalse(source['parameters']['options']['redirect']['redirect']['followRedirects'])
        self.assertNotIn('credentials',source)
        self.assertEqual(self.workflow['connections']['Research Relevant?']['main'][1][0]['node'],'Research Not Applicable')
        self.assertEqual(self.workflow['connections']['Research Not Applicable']['main'][0][0]['node'],'Primary Research Result')
        unrelated=copy.deepcopy(self.intake);unrelated['matter'].update(title='Employment dispute',summary='Dismissal question only.',requested_scope='Review dismissal documents.')
        self.assertFalse(self.code('Plan Bounded Primary Research',{}, {'Validate Intake':{'intake':unrelated}})['relevant'])

    def test_research_helper_failure_never_invents_a_verified_claim_or_date(self):
        context={'Validate Intake':{'intake':self.intake}}
        for response in ({'statusCode':503,'body':{}},{'statusCode':200,'body':{'status':'verified'}},{'research_not_applicable':True}):
            result=self.code('Primary Research Result',response,context)
            self.assertIn(result['status'],('unavailable','not_applicable'))
            self.assertEqual(result['verified_rules'],[])
            self.assertIsNone(result['potential_deadline_analysis']['confirmed_deadline'])
            self.assertIsNone(result['potential_deadline_analysis']['calculated_deadline'])

    def test_source_enrichment_flows_into_final_report_offline(self):
        from datetime import datetime,timezone
        from scripts.primary_research import PrimaryResearchRequest,verify_research,SOURCE_URL
        from scripts.onboarding_schemas import OnboardingBundle
        extracted=self.extracted();valid=self.code('Validate Intake',extracted)
        with tempfile.TemporaryDirectory() as tmp:
            with TestClient(create_app(cache_dir=None,ledger_path=None,onboarding_db=Path(tmp)/'demo.sqlite3')) as client:
                response=client.post('/v1/onboarding/preview',json=valid['intake']);self.assertEqual(response.status_code,200)
        checked=self.code('Validate Onboarding Bundle',{'statusCode':200,'body':response.json()},{'Validate Intake':valid})
        source=(ROOT/'tests/fixtures/bgb286_sanitized.html').read_text()
        request=PrimaryResearchRequest(synthetic_data=True,matter=valid['intake']['matter'],bundle=OnboardingBundle.model_validate(response.json()),source_url=SOURCE_URL,retrieved_at=datetime.now(timezone.utc).isoformat(),http_status=200,source_html=source)
        research=verify_research(request).model_dump(mode='json')
        normalized=self.code('Primary Research Result',{'statusCode':200,'body':research},{'Validate Intake':valid})
        self.assertEqual(normalized['status'],'verified')
        final=self.code('Integrated Onboarding Report',normalized,{'Validate Onboarding Bundle':checked,'Extract Approved Inquiry':extracted,'Assess Existing Matter Lookup':{'limitation':'bounded offline lookup'},'Check Calendar Metadata':{'availability_verified':False},'Primary Research Result':normalized})
        self.assertEqual(len(final['bundle']['assessment']['sources']),12)
        self.assertIn('Potential Deadline Analysis',final['bundle']['assessment']['content_markdown'])
        self.assertIsNone(final['potential_deadline_analysis']['confirmed_deadline'])
        self.assertTrue(final['source_grounded_live_case_research_performed'])
        self.assertEqual(final['research_method'],'one_bounded_rule_selected_primary_source_check')

    def test_approved_email_plain_text_linewraps_are_audited_not_fixture_replaced(self):
        raw='INCEPT_SYNTHETIC_INTAKE_V1\n'+json.dumps(self.intake,ensure_ascii=False)
        raw=raw.replace('verlangt Zahlung aus','verlangt Zahlung\naus')
        self.assertIn('Zahlung\naus',raw)
        data=base64.urlsafe_b64encode(raw.encode()).decode()
        response={'statusCode':200,'body':{'id':self.message_id,'payload':{'mimeType':'text/plain','body':{'data':data}}}}
        result=self.code('Extract Approved Inquiry',response,{'Validate Approved Metadata':{'message_id':self.message_id}})
        self.assertTrue(result['ready']);self.assertEqual(result['intake']['matter'],self.intake['matter'])
        self.assertEqual(result['provenance']['normalized_quoted_linewraps'],1)
        self.assertTrue(result['provenance']['normalization_requires_review'])
        self.assertTrue(result['provenance']['source_message_unchanged'])
        self.assertFalse(result['provenance']['fixture_substitution'])
        response['body']['payload']['body']['data']=base64.urlsafe_b64encode((raw+' Copy code').encode()).decode()
        result=self.code('Extract Approved Inquiry',response,{'Validate Approved Metadata':{'message_id':self.message_id}})
        self.assertFalse(result['ready'])

    def test_source_preparation_preserves_binary_bytes(self):
        raw=b'<html><meta charset="ISO-8859-1"><h1>B\xfcrgerliches Gesetzbuch</h1></html>'
        context={'Validate Intake':{'intake':self.intake},'Validate Onboarding Bundle':{'bundle':{'synthetic_data':True}}}
        result=self.code('Prepare Primary Research Input',{'statusCode':200,'headers':{'content-type':'text/html'}},context,binary_content=base64.b64encode(raw).decode())
        self.assertEqual(base64.b64decode(result['source_bytes_base64']),raw)
        self.assertEqual(result['source_html'],'');self.assertIsNone(result['retrieval_error'])
