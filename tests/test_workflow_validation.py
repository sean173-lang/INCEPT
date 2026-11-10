"""Regression for falsely treating old/partial n8n successes as full passes."""
from offline_support import OfflineTestCase
from scripts.workflow_validation import validate_execution


class ExecutionValidationTests(OfflineTestCase):
    def test_phase1_success_is_not_phase2_success(self):
        execution={'id':'old-fixture','status':'success','finished':True,'data':{'resultData':{
            'lastNodeExecuted':'Verified Company','runData':{'Verified Company':[{'data':{'main':[[{'json':{'status':'verified'}}]]}}]}}}}
        result=validate_execution(execution)
        self.assertFalse(result['passed'])
        self.assertIn('phase2_nodes_executed',result['failed_checks'])
        self.assertIn('exactly_two_tool_executions',result['failed_checks'])

    def test_successful_review_branch_does_not_count_as_report_pass(self):
        execution={'status':'success','finished':True,'data':{'resultData':{'lastNodeExecuted':'Verification Needs Review',
            'runData':{'Verification Needs Review':[{'data':{'main':[[{'json':{'status':'ambiguous'}}]]}}]}}}}
        result=validate_execution(execution)
        self.assertFalse(result['passed'])
        self.assertIn('structured_report_valid',result['failed_checks'])


class CompleteExecutionEvidenceTests(OfflineTestCase):
    def fixture(self):
        # This constructs evidence for testing the validator, not a real n8n run.
        from fastapi.testclient import TestClient
        from scripts.http_service import create_app
        app=create_app(cache_dir=None,ledger_path=None)
        with TestClient(app) as client:
            verified=client.post('/v1/company/verify',json={'company_name':'LEGALFLOW DEMO GmbH','jurisdiction':'Germany','provider_company_id':'DEMO'}).json()
            initial=client.post('/v1/research/runs',json={'verification_id':verified['verification_id']}).json()
            plan=initial
            steps=[]
            for _ in range(2):
                plan=client.post('/v1/research/runs/'+plan['run_id']+'/tools',json={'tool':plan['next_tool'],'plan_token':plan['plan_token']}).json()
                steps.append(plan)
            report=client.post('/v1/research/runs/'+plan['run_id']+'/report').json()
        def node(value):return {'executionStatus':'success','data':{'main':[[{'json':value}]]}}
        return {'id':'synthetic-validator-fixture','status':'success','finished':True,'data':{'resultData':{
            'lastNodeExecuted':'Due Diligence Report','runData':{
                'Verified Company':[node({'company':verified['company']})],
                'FastAPI Create Research Run':[node({'statusCode':200,'body':initial})],
                'FastAPI Research Tool':[node({'statusCode':200,'body':v}) for v in steps],
                'FastAPI Research Report':[node({'statusCode':200,'body':report})],
                'Due Diligence Report':[node(report)],
            }}}}

    def test_complete_evidence_is_accepted(self):
        self.assertTrue(validate_execution(self.fixture())['passed'])

    def test_duplicate_or_missing_tool_execution_is_rejected(self):
        fixture=self.fixture()
        fixture['data']['resultData']['runData']['FastAPI Research Tool'].pop()
        result=validate_execution(fixture)
        self.assertFalse(result['passed'])
        self.assertIn('exactly_two_tool_executions',result['failed_checks'])

    def test_tampered_source_and_missing_warnings_are_rejected(self):
        fixture=self.fixture()
        report=fixture['data']['resultData']['runData']['Due Diligence Report'][0]['data']['main'][0][0]['json']
        report['sections'][0]['references'][0]['source_url']='https://unrelated.example'
        report['sections'][1]['missing_data']=[]
        result=validate_execution(fixture)
        self.assertFalse(result['passed'])
        self.assertIn('references_attributable',result['failed_checks'])
        self.assertIn('missing_data_and_document_requests',result['failed_checks'])

    def test_report_for_wrong_company_is_rejected(self):
        fixture=self.fixture()
        fixture['data']['resultData']['runData']['Verified Company'][0]['data']['main'][0][0]['json']['company']['provider_company_id']='OTHER'
        self.assertIn('report_matches_verified_company',validate_execution(fixture)['failed_checks'])
