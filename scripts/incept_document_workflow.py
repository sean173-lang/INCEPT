"""Reproduce execution-28 development graph without exporting account bindings."""
import json
from pathlib import Path
import re
import uuid
from scripts.incept_corporate_workflow import build_workflow as corporate_workflow

PROJECT_ACCOUNT='REPLACE_WITH_AUTHORIZED_PROJECT_GMAIL'
SPREADSHEET='REPLACE_WITH_DEMO_SPREADSHEET_ID'
SUBJECT='[INCEPT DEMO APPROVED] German corporate onboarding v2'
V2_CHECK=" check(body.documents.every(d=>d.document_version===2 && d.template_version==='2.0.0' && typeof d.source_version==='string' && d.ready_for_issuance===false && d.legally_approved===false && Array.isArray(d.validation_issues) && Array.isArray(d.missing_information) && ['DRAFT_COMPLETE_FOR_LAWYER_REVIEW','MISSING_INFORMATION','LEGAL_REVIEW_REQUIRED','NOT_READY_FOR_ISSUANCE'].includes(d.completeness_status)), 'v2_document_metadata_or_generation_failure');\n"


def build_workflow(project_account=PROJECT_ACCOUNT,spreadsheet_id=SPREADSHEET):
    if project_account!=PROJECT_ACCOUNT and not re.fullmatch(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',project_account):
        raise ValueError('A single authorized project account is required')
    if not re.fullmatch(r'[A-Za-z0-9_-]{10,150}',spreadsheet_id):raise ValueError('Invalid spreadsheet identifier')
    workflow=corporate_workflow()
    workflow['name']='INCEPT — German corporate onboarding v2 live document test (manual)'
    # The base export already has no OAuth credentials; replace its non-secret
    # project account/spreadsheet identifiers in this checkpoint export as well.
    lookup={n['name']:n for n in workflow['nodes']}
    sheet=lookup['Read Existing Matters']['parameters']['documentId']['value']
    query=lookup['Find Approved Demo Inquiry']['parameters']['queryParameters']['parameters'][0]['value']
    old_account=re.search(r'from:\(([^)]+)\)',query).group(1)
    for node in workflow['nodes']:
        node['id']=uuid.uuid5(uuid.NAMESPACE_URL,'incept-live-documents-v2:'+node['name']).hex
        parameters=json.dumps(node['parameters'],ensure_ascii=False)
        node['parameters']=json.loads(parameters.replace(old_account,project_account).replace(sheet,spreadsheet_id))
        p=node['parameters']
        if node['name']=='Find Approved Demo Inquiry':
            p['queryParameters']['parameters'][0]['value']='in:inbox from:('+project_account+') to:('+project_account+') subject:"INCEPT DEMO APPROVED" subject:"German corporate onboarding v2" -in:trash -in:spam'
        if node['name']=='Validate Approved Metadata':p['jsCode']=p['jsCode'].replace('[INCEPT DEMO APPROVED] Fictional intake v1',SUBJECT)
        if node['name']=='Validate Onboarding Bundle':
            at=p['jsCode'].index(' check(r && r.title')
            p['jsCode']=p['jsCode'][:at]+V2_CHECK+p['jsCode'][at:]
    return workflow


if __name__=='__main__':
    target=Path(__file__).resolve().parents[1]/'workflows/incept_live_documents_v2.json'
    target.write_text(json.dumps(build_workflow(),indent=2,ensure_ascii=False)+'\n')
