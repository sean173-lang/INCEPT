"""Four system-generated offline intake scenarios. Never a live registry demonstration."""
from pathlib import Path
import copy
import json
import socket
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
from scripts.http_service import create_app

ROOT=Path(__file__).resolve().parent.parent


def scenarios():
    base=json.loads((ROOT/'examples/onboarding_preview.json').read_text())
    result={}
    individual=copy.deepcopy(base);individual['client'].update(client_type='individual',name='DEMO Individual (fictional)')
    individual['matter'].update(governing_law='Germany',title='DEMO individual service dispute',summary='Synthetic individual requests review of an alleged private service-contract payment demand. Original contract and receipt evidence are missing.');individual['idempotency_key']='corporate-demo-individual-01';result['individual']=individual
    for kind,country,name,id,number,court,law in [('germany_company','Germany','INCEPT DEMO GmbH','DEMO-INCEPT-DE','DEMO-246468','Synthetic Berlin court','Germany'),
         ('uk_company','United Kingdom','INCEPT DEMO LTD','DEMO0001','DEMO0001',None,'United Kingdom')]:
        body=copy.deepcopy(base);body['idempotency_key']='corporate-demo-'+kind
        body['client'].update(client_type='company',name=name,jurisdiction=country,registration_number=number,approved_provider_id=id,register_court=court,register_type='HRB' if court else None)
        body['matter'].update(governing_law=law,title='DEMO corporate mandate — '+kind)
        if kind=='uk_company':
            body['matter'].update(summary='Synthetic UK company disputes a consultancy invoice under an alleged English-law agreement. The original agreement, invoice and payment terms have not been reviewed.',requested_scope='Review the consultancy dispute evidence; no verified UK liability conclusion or deadline calculation.')
        result[kind]=body
    ambiguous=copy.deepcopy(base);ambiguous['client'].update(client_type='unknown',jurisdiction='unknown');ambiguous['matter']['governing_law']='unknown'
    ambiguous['idempotency_key']='corporate-demo-ambiguous-01';result['ambiguous']=ambiguous
    return result


def generate(output=None):
    output=Path(output) if output else ROOT/'reports/incept_corporate_demo';output.mkdir(parents=True,exist_ok=True)
    summary={}
    with tempfile.TemporaryDirectory() as temp,patch.object(socket.socket,'connect',side_effect=AssertionError('Offline demonstration: external calls prohibited')):
        app=create_app(development=True,allow_paid=False,cache_dir=None,ledger_path=None,onboarding_db=Path(temp)/'demo.sqlite3',corporate_cache_dir=Path(temp)/'cache')
        with TestClient(app) as client:
            for name,body in scenarios().items():
                folder=output/name;folder.mkdir(exist_ok=True)
                corporate=None
                if name=='ambiguous':
                    response=client.post('/v1/onboarding/corporate-intelligence',json={'synthetic_data':True,'client_id':'unresolved-intake','matter_id':body['idempotency_key'],'client':body['client'],'source_policy':'approved_demo_fixture','max_external_requests':0})
                    assert response.status_code==200;corporate=response.json();assert corporate['status']=='NEEDS_REVIEW'
                    report='# DEMO — unresolved intake\n\nNEEDS_REVIEW / INSUFFICIENT_IDENTITY. No speculative registry lookup, onboarding record or legal analysis performed.\n\n'+ '\n'.join(corporate['missing_evidence'])
                    bundle=None
                else:
                    response=client.post('/v1/onboarding/preview',json=body);assert response.status_code==200,response.text;bundle=response.json()
                    assert client.post('/v1/onboarding/preview',json=body).json()==bundle
                    if body['client']['client_type']=='company':
                        response=client.post('/v1/onboarding/corporate-intelligence',json={'synthetic_data':True,'client_id':bundle['client']['client_id'],'matter_id':bundle['matter']['matter_id'],'client':body['client'],'source_policy':'approved_demo_fixture','max_external_requests':0})
                        assert response.status_code==200,response.text;corporate=response.json()
                        bundle['assessment']['content_markdown']+=corporate['section_markdown']
                    report=bundle['assessment']['content_markdown']
                    (folder/'bundle.json').write_text(json.dumps(bundle,indent=2,ensure_ascii=False))
                    for doc in bundle['documents']:(folder/(doc['kind']+'.md')).write_text(doc['content_markdown'])
                    assert bundle['advance']['gross_total']=='1487.50'
                (folder/'mandate_assessment.md').write_text(report)
                if corporate:(folder/'corporate_intelligence.json').write_text(json.dumps(corporate,indent=2,ensure_ascii=False))
                summary[name]={'source_mode':'explicit_synthetic_offline_fixture_not_live_provider','business_state':'NEEDS_REVIEW' if name=='ambiguous' else 'PREVIEW_READY_FOR_LAWYER_REVIEW',
                    'provider':corporate['provider'] if corporate else None,'identity_status':corporate['identity_verification_status'] if corporate else 'not_requested',
                    'corporate_section_included':name in ('germany_company','uk_company'),'governing_law':body['matter']['governing_law'],
                    'german_bgb_applied_to_uk':False,'external_calls':0,'financial_requests':0,'external_actions':0,'n8n_execution_id':None,'report':str(folder/'mandate_assessment.md')}
    (output/'scenario_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    for name,result in generate().items():print(name,result['business_state'],result['provider'],result['identity_status'])
