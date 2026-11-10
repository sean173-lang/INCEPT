"""Offline workflow generation and JavaScript contract tests; no n8n mutation."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
from offline_support import OfflineTestCase
from scripts import n8n_workflow as wf


def original():
    return {'id':'fixture-workflow','name':'LEGALFLOW fixture','active':False,'settings':{'executionOrder':'v1'},
            'nodes':[{'id':'form','name':'On form submission','type':'n8n-nodes-base.formTrigger','parameters':{'formFields':{'values':[{'fieldLabel':'Company Name'},{'fieldLabel':'Jurisdiction'},{'fieldLabel':'Include Financial Analysis'}]}}},
                     {'id':'fields','name':'Edit Fields','type':'n8n-nodes-base.set','parameters':{'assignments':{}}},
                     {'id':'search','name':'OpenRegister Company Search','type':'n8n-nodes-base.httpRequest','typeVersion':4.5,'parameters':{'url':'https://api.openregister.de/v1/autocomplete/company'},'credentials':{'httpHeaderAuth':{'id':'private-reference','name':'old credential'}}}]}


class WorkflowTests(OfflineTestCase):
    def js(self, code, item, references=None):
        if not shutil.which('node'):
            self.skipTest('Node.js is required for exported code-node contract tests')
        program = "const x=JSON.parse(require('fs').readFileSync(0,'utf8')); const fn=new Function('$','$input',x.code); const out=fn(n=>({first:()=>({json:x.refs[n]})}),{first:()=>({json:x.item})}); process.stdout.write(JSON.stringify(out[0].json));"
        result = subprocess.run(['node','-e',program],input=json.dumps({'code':code,'item':item,'refs':references or {}}),text=True,capture_output=True,check=True)
        return json.loads(result.stdout)

    def context(self, country='Germany'):
        return self.js(wf.PREPARE, {'company_name':'Real company must never be queried','jurisdiction':country,'include_financials':True})

    def candidate(self, identifier='DEMO'):
        return {'provider_company_id':identifier,'name':'LEGALFLOW DEMO GmbH','jurisdiction':'Germany',
                'registration_number':'DEMO-1','register_court':'Synthetic court'}

    def test_form_fields_credential_reference_and_inactive_state_preserved(self):
        source=original();before=copy.deepcopy(source)
        built=wf.build_workflow(source)
        self.assertEqual(source,before)
        self.assertNotIn('active',built)
        for name in ('On form submission','Edit Fields'):
            self.assertEqual(next(n for n in built['nodes'] if n['name']==name),next(n for n in source['nodes'] if n['name']==name))
        archive=next(n for n in built['nodes'] if n.get('disabled'))
        self.assertEqual(archive['credentials'],source['nodes'][-1]['credentials'])
        self.assertNotIn(archive['name'],built['connections'])
        self.assertFalse(any(c['node']==archive['name'] for outputs in built['connections'].values() for branch in outputs['main'] for c in branch))
        for node in built['nodes']:
            if node['type'].endswith('httpRequest') and not node.get('disabled'):
                self.assertTrue(node['parameters']['url'].startswith(wf.BASE_URL))
                self.assertFalse(node['retryOnFail'])
                self.assertNotIn('credentials',node)
                self.assertNotIn('financials',node['parameters']['url'])

    def test_all_connections_and_required_branches_resolve(self):
        built=wf.build_workflow(original())
        names={n['name'] for n in built['nodes']}
        for source,outputs in built['connections'].items():
            self.assertIn(source,names)
            for branch in outputs['main']:
                for link in branch:self.assertIn(link['node'],names)
        for gate in ('Input Valid?','Development Ready?','Candidate Selected?','Candidate Selection Required?','Selection Valid?','Company Verified?'):
            self.assertEqual(len(built['connections'][gate]['main']),2)

    def test_active_workflow_cannot_be_rebuilt(self):
        source=original();source['active']=True
        with self.assertRaises(ValueError):wf.build_workflow(source)

    def test_real_form_name_and_financial_opt_in_are_never_forwarded(self):
        for country,name in [('Germany','LEGALFLOW DEMO GmbH'),('UK','LEGALFLOW DEMO LTD')]:
            result=self.context(country)
            self.assertEqual(result['company_name'],name)
            self.assertFalse(result['include_financials'])
            self.assertFalse(result['financial_requests_enabled'])
            self.assertTrue(result['ready'])
        for data in ({},{'company_name':'x','jurisdiction':'US'},{'company_name':'','jurisdiction':'UK'}):
            self.assertFalse(self.js(wf.PREPARE,data)['ready'])

    def test_health_guard_rejects_live_and_network_failure(self):
        refs={'Prepare Development Input':self.context()}
        for item in ({'statusCode':200,'body':{'status':'ok','development':False}},{'error':'connection failed'}):
            result=self.js(wf.HEALTH,item,refs)
            self.assertFalse(result['ready'])
        self.assertTrue(self.js(wf.HEALTH,{'statusCode':200,'body':{'status':'ok','development':True}},refs)['ready'])

    def test_selected_candidate_is_not_verified_by_name(self):
        result=self.js(wf.CANDIDATES,{'statusCode':200,'body':{'status':'candidates_found','development':True,'candidates':[self.candidate()]}},
                       {'Prepare Development Input':self.context()})
        self.assertEqual(result['status'],'selected')
        self.assertEqual(result['verification_request']['provider_company_id'],'DEMO')
        self.assertNotIn('verification_id',result)

    def test_ambiguous_candidates_require_validated_form_selection(self):
        context=self.js(wf.CANDIDATES,{'statusCode':200,'body':{'status':'candidates_found','development':True,'candidates':[self.candidate(),self.candidate('DEMO-ALT')]}},
                        {'Prepare Development Input':self.context()})
        self.assertEqual(context['status'],'ambiguous')
        selected=self.js(wf.SELECTION,{'Company Candidate':context['candidate_options'][1]['option']},{'Prepare Company Candidates':context})
        self.assertEqual(selected['verification_request']['provider_company_id'],'DEMO-ALT')
        invalid=self.js(wf.SELECTION,{'Company Candidate':'fake id'},{'Prepare Company Candidates':context})
        self.assertEqual(invalid['status'],'verification_failed')

    def test_missing_failed_and_non_synthetic_results_stop(self):
        refs={'Prepare Development Input':self.context()}
        for body,expected in [({'status':'not_found','development':True,'candidates':[]},'not_found'),
                              ({'status':'candidates_found','development':False,'candidates':[self.candidate()]},'verification_failed'),
                              ({'status':'candidates_found','development':True,'candidates':[{**self.candidate(),'provider_company_id':'DE-REAL'}]},'verification_failed')]:
            self.assertEqual(self.js(wf.CANDIDATES,{'statusCode':200,'body':body},refs)['status'],expected)
        self.assertEqual(self.js(wf.CANDIDATES,{'error':'network failed'},refs)['status'],'verification_failed')

    def test_verified_response_requires_detail_checks_and_scope(self):
        refs={'Prepare Development Input':self.context()}
        body={'status':'verified','development':True,'verification_scope':'provider_record_identity',
              'verification_id':'a'*32,'company':self.candidate(),
              'checks':{'name':True,'provider_id':True,'registration':True}}
        self.assertEqual(self.js(wf.CHECK_VERIFY,{'statusCode':200,'body':body},refs)['status'],'verified')
        for change in ({'checks':{'name':True}}, {'verification_scope':'name_only'}, {'development':False}, {'verification_id':None}):
            self.assertEqual(self.js(wf.CHECK_VERIFY,{'statusCode':200,'body':{**body,**change}},refs)['status'],'verification_failed')


if __name__=='__main__':
    import unittest
    unittest.main()


class ResearchWorkflowTests(OfflineTestCase):
    js = WorkflowTests.js
    def test_research_branch_preserves_phase1_and_unresolved_routes(self):
        phase1=wf.build_workflow(original())
        phase1['active']=False
        phase2=wf.extend_research_workflow(phase1)
        self.assertEqual(len(phase2['nodes']),len(phase1['nodes'])+9)
        for node in phase1['nodes']:
            self.assertEqual(node,next(n for n in phase2['nodes'] if n['name']==node['name']))
        self.assertEqual(phase1['connections']['Company Verified?'],phase2['connections']['Company Verified?'])
        self.assertNotIn('Verification Needs Review',phase2['connections'])
        for node in phase2['nodes']:
            if node['type'].endswith('httpRequest') and not node.get('disabled'):
                self.assertNotIn('/financial',node['parameters']['url'])
                self.assertFalse(node['retryOnFail'])

    def test_research_plan_guard_rejects_unapproved_tools_and_high_iterations(self):
        context={'development':True,'company':{'provider_company_id':'DEMO'}}
        body={'development':True,'run_id':'a'*32,'iteration':0,'max_iterations':2,'state':'ready',
              'next_tool':'retrieve_references','plan_token':'b'*64}
        refs={'Verified Company':context}
        self.assertTrue(self.js(wf.RESEARCH_PLAN,{'statusCode':200,'body':body},refs)['ready'])
        for change in ({'next_tool':'financials'},{'iteration':3},{'max_iterations':20},{'development':False}):
            self.assertFalse(self.js(wf.RESEARCH_PLAN,{'statusCode':200,'body':{**body,**change}},refs)['ready'])
        self.assertFalse(self.js('const $runIndex=3;\n'+wf.RESEARCH_PLAN,{'statusCode':200,'body':body},refs)['ready'])
