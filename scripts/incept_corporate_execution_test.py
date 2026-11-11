"""Isolated n8n test copies: real helper calls, explicitly substituted ingress/Google data."""
import copy,json
from scripts.incept_corporate_workflow import build_workflow
from scripts.incept_corporate_demo import scenarios


def build_test_workflow(case):
    intake=copy.deepcopy(scenarios()[case]);intake['idempotency_key']='incept-n8n-corporate-test-'+case
    w=build_workflow();w['name']='INCEPT isolated corporate test — '+case
    def code(n,script):
        n['type']='n8n-nodes-base.code';n['typeVersion']=2;n['parameters']={'mode':'runOnceForAllItems','jsCode':script}
        for key in ('credentials','alwaysOutputData','onError'):n.pop(key,None)
    for n in w['nodes']:
        name=n['name'];p=n['parameters']
        if name=='Extract Approved Inquiry':code(n,'return [{json:{ready:true,intake:'+json.dumps(intake)+',missing_fields:["Synthetic offline execution; no Gmail was read."],provenance:{origin:"explicit_synthetic_test_fixture",fixture_substitution:true}}}];')
        elif name=='Read Existing Matters':code(n,'return [{json:{client_name:"Unrelated synthetic fixture",matter_id:"demo-fixture"}}];')
        elif name=='Read Accessible Calendars':code(n,'return [{json:{statusCode:200,body:{kind:"calendar#calendarList",items:[]}}}];')
        elif name=='Retrieve Official Provision':code(n,'return [{json:{statusCode:503,fixture_source_unavailable:true}}];')
        elif n['type'].endswith('httpRequest'):
            url=p.get('url','')
            if 'gmail' in url:code(n,'throw new Error("Gmail disabled in isolated test");')
            elif url.startswith('http://127.0.0.1:8003/'):
                p['url']=url.replace(':8003/',':8004/')
                if name=='Get Corporate Intelligence':p['jsonBody']=p['jsonBody'].replace("'cache_only'","'approved_demo_fixture'")
        if name=='Integrated Onboarding Report':
            p=n['parameters'];p['jsCode']=p['jsCode'].replace('approved_live_email_processed:true','approved_live_email_processed:false').replace('fixture_substitution:false,email_bodies_read:1','fixture_substitution:true,email_bodies_read:0').replace('source_grounded_live_case_research_performed:researched','source_grounded_live_case_research_performed:false')
    w['connections']['Manual Integrated Intake']['main']=[[{'node':'Extract Approved Inquiry','type':'main','index':0}]]
    assert len(w['nodes'])==37 and not w['active']
    for n in w['nodes']:
        assert not n.get('credentials')
        if n['type'].endswith('httpRequest'):assert n['parameters']['url'].startswith('http://127.0.0.1:8004/v1/onboarding/')
    return w
