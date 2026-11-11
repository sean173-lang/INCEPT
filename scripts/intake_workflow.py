"""Build a separate inactive manual-trigger onboarding workflow. No network I/O."""
import json
from pathlib import Path
import uuid

ROOT=Path(__file__).resolve().parent.parent

VALIDATE_INPUT=r'''
const intake = $input.first().json;
let reasons = [];
const noControls = s => typeof s === 'string' && s.length > 0 && !/[\x00-\x1f\x7f]/.test(s);
if (intake.synthetic_data !== true) reasons.push('synthetic_data_required');
if (!/^[A-Za-z0-9_-]{8,100}$/.test(intake.idempotency_key || '')) reasons.push('invalid_idempotency_key');
for (const key of ['client','firm']) {
  const x=intake[key];
  if (!x || !noControls(x.name) || !noControls(x.address) || !/^[^\s@]+@[^\s@]+\.invalid$/.test(x.email || '') || x.jurisdiction !== 'Germany') reasons.push('invalid_'+key);
}
if (!noControls(intake.firm?.lawyer_name) || !noControls(intake.matter?.summary) || !noControls(intake.matter?.title) || !noControls(intake.matter?.requested_scope)) reasons.push('invalid_matter_or_lawyer');
if (!/^\d{4}-\d{2}-\d{2}$/.test(intake.draft_date || '') || Number.isNaN(Date.parse(intake.draft_date))) reasons.push('invalid_draft_date');
if (!/^\d{1,5}(\.\d{1,2})?$/.test(intake.fees?.net_hourly_rate || '') || Number(intake.fees?.net_hourly_rate)<=0 || intake.fees?.currency!=='EUR') reasons.push('invalid_fee');
const f=intake.fees || {};
if (!['taxable','exempt','unknown'].includes(f.vat_mode)) reasons.push('invalid_vat_mode');
if (f.vat_mode==='taxable' && (!/^\d{1,3}(\.\d{1,2})?$/.test(f.vat_percent || '') || Number(f.vat_percent)<=0 || Number(f.vat_percent)>100 || !noControls(f.vat_basis))) reasons.push('explicit_vat_required');
if (f.vat_mode==='exempt' && (!noControls(f.vat_basis) || f.vat_percent!=null)) reasons.push('invalid_exemption');
if (f.vat_mode==='unknown' && (f.vat_percent!=null || f.vat_basis!=null)) reasons.push('unknown_vat_must_not_guess');
return [{json:{intake,valid:reasons.length===0,stage:'input_validation',reasons}}];
'''

VALIDATE_BUNDLE=r'''
const response=$input.first().json;
const intake=$('Validate Intake').first().json.intake;
const status=response.statusCode;
let body=response.body ?? response.data;
if (typeof body==='string') {try {body=JSON.parse(body);} catch {body=null;}}
function fail(reason) {return [{json:{valid:false,stage:'response_validation',http_status:Number.isInteger(status)?status:null,reasons:[reason],
  provider_calls:0,external_actions_executed:false}}];}
if (status!==200) return fail(status===409?'idempotency_conflict':status===422?'api_input_validation_error':status===401||status===403?'api_access_rejected':status?'api_http_failure':'api_transport_failure');
if (!body || typeof body!=='object') return fail('unexpected_response_format');
try {
 const check=(ok,reason)=>{if(!ok)throw new Error(reason);};
 check(body.schema_version===1 && body.synthetic_data===true && body.status==='preview_pending_lawyer_approval','unexpected_bundle_status');
 check(body.external_actions_executed===false && body.paid_api_calls===0,'external_action_or_spending_flag');
 const c=body.client,m=body.matter,a=body.advance,r=body.assessment;
 check(c && m && typeof c.client_id==='string' && c.client_id.startsWith('demo-client-') && typeof m.matter_id==='string' && m.matter_id.startsWith('demo-matter-') && m.client_id===c.client_id,'invalid_client_matter_link');
 check(c.name===intake.client.name && c.email===intake.client.email && c.synthetic_data===true && m.title===intake.matter.title && m.summary===intake.matter.summary && m.status==='draft_pending_lawyer_review','intake_identity_mismatch');
 const cents=s=>{check(typeof s==='string' && /^\d+(\.\d{1,2})?$/.test(s),'invalid_money_format');let [i,d='']=s.split('.');return BigInt(i)*100n+BigInt(d.padEnd(2,'0'));};
 const cash=n=>(n/100n).toString()+'.'+(n%100n).toString().padStart(2,'0');
 const net=cents(intake.fees.net_hourly_rate)*5n;
 const vat=intake.fees.vat_mode==='unknown'?null:intake.fees.vat_mode==='exempt'?0n:(net*cents(intake.fees.vat_percent)+5000n)/10000n;
 check(a && a.hours==='5' && a.currency==='EUR' && a.work_performed===false && a.tax_status==='supplied_demo_treatment_unverified','invalid_advance_scope');
 check(a.net_hourly_rate===cash(cents(intake.fees.net_hourly_rate)) && a.net_fee===cash(net) && a.vat_mode===intake.fees.vat_mode && a.vat_percent===(intake.fees.vat_percent??null),'net_or_vat_assumption_mismatch');
 check(a.vat_amount===(vat===null?null:cash(vat)) && a.gross_total===(vat===null?null:cash(net+vat)),'advance_arithmetic_mismatch');
 check(Array.isArray(body.documents) && body.documents.length===3 && new Set(body.documents.map(d=>d.kind)).size===3,'missing_documents');
 check(body.documents.every(d=>['vollmacht','fee_agreement','advance_invoice'].includes(d.kind) && d.state==='pending_lawyer_approval' && typeof d.content_markdown==='string' && d.content_markdown.includes('DEMO') && d.content_markdown.length>100),'unsafe_or_empty_document');
 check(r && r.title==='DEMO Mandate Assessment Report' && r.conclusion==='lawyer_review_required' && r.confidence==='insufficient_for_legal_conclusions' && typeof r.content_markdown==='string' && r.content_markdown.length>100 && typeof r.corpus_version==='string','invalid_assessment');
 check(Array.isArray(r.sources) && r.sources.length>=4 && Array.isArray(r.factual_findings) && r.factual_findings.length>=3 && Array.isArray(r.guidance) && r.guidance.length>=4 && Array.isArray(r.missing_information) && r.missing_information.length>0,'missing_evidence_or_warnings');
 const sources=new Map(r.sources.map(s=>[s.source_id,s]));
 check(sources.size===r.sources.length,'duplicate_source_ids');
 for (const f of [...r.factual_findings,...r.guidance]) {
  check(Array.isArray(f.source_ids) && f.source_ids.length>0 && f.source_ids.every(id=>sources.has(id)),'unresolved_citation');
  check(typeof f.description==='string' && f.description.length>0,'empty_finding');
 }
 check(r.factual_findings.every(f=>f.status==='unverified_intake_statement' && f.source_ids.every(id=>sources.get(id).kind==='synthetic_intake')),'unsupported_verified_fact');
 check(r.guidance.every(f=>f.status==='reference_guidance' && f.source_ids.every(id=>{const s=sources.get(id);return s.kind==='legal_reference' && s.url?.startsWith('https://www.gesetze-im-internet.de/') && typeof s.locator==='string' && typeof s.reviewed_at==='string';})),'invalid_reference_guidance');
 check(Array.isArray(body.proposed_actions) && body.proposed_actions.length>=5,'missing_actions');
 check(body.proposed_actions.every(x=>x.state==='pending_lawyer_approval' && x.executed===false && x.due_date===null && Array.isArray(x.source_ids) && x.source_ids.length>0 && x.source_ids.every(id=>sources.has(id))),'unsafe_action');
 check(['task','potential_deadline','draft_email'].every(k=>body.proposed_actions.some(a=>a.kind===k)),'missing_action_type');
 const email=body.proposed_actions.find(x=>x.kind==='draft_email'),deadline=body.proposed_actions.find(x=>x.kind==='potential_deadline');
 check(email.recipient===intake.client.email && typeof email.body==='string' && email.body.length>0 && typeof email.subject==='string','invalid_email_draft');
 check(deadline.candidate_date===(intake.matter.claimed_deadline??null),'deadline_promoted_or_mismatched');
 return [{json:{valid:true,stage:'response_validation',http_status:status,bundle:body,validation:{documents:3,actions:body.proposed_actions.length,sources:r.sources.length,factual_findings:r.factual_findings.length,all_citations_resolve:true,decimal_arithmetic_valid:true,all_actions_pending_approval:true,no_confirmed_deadlines:true,synthetic_only:true,no_external_actions:true}}}];
} catch(error) {return fail(error.message || 'unexpected_response');}
'''

SUCCESS=r'''
const checked=$input.first().json;
return [{json:{outcome:'passed',business_success:true,http_status:checked.http_status,
  client_id:checked.bundle.client.client_id,matter_id:checked.bundle.matter.matter_id,
  advance:checked.bundle.advance,validation:checked.validation,bundle:checked.bundle}}];
'''
FAILURE=r'''
const checked=$input.first().json;
return [{json:{outcome:'manual_review_required',business_success:false,stage:checked.stage||'unknown',
  http_status:checked.http_status??null,reasons:checked.reasons||['unclassified_failure'],
  external_actions_executed:false,paid_api_calls:0}}];
'''
SUMMARY=r'''
return [{json:{...$input.first().json,workflow_purpose:'fictional_legal_intake_preview',
  n8n_execution_id:String($execution.id),completed_at:new Date().toISOString(),
  lawyer_approval_bypassed:false,emails_sent:0,calendar_events_created:0,invoices_issued:0,
  project3_three_real_integrations_satisfied:false}}];
'''


def build_workflow():
    fixture=json.loads((ROOT/'examples/onboarding_preview.json').read_text())
    fixture['idempotency_key']='fictional-n8n-onboarding-001'
    nodes=[]
    def node(name,kind,version,parameters,x,y=0,**kwargs):
        nodes.append({'id':uuid.uuid5(uuid.NAMESPACE_URL,'legalflow-intake:'+name).hex,'name':name,'type':'n8n-nodes-base.'+kind,
                      'typeVersion':version,'position':[x,y],'parameters':parameters,**kwargs})
    def code(name,body,x,y=0):node(name,'code',2,{'mode':'runOnceForAllItems','jsCode':body},x,y)
    def branch(name,x):node(name,'if',2.2,{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},'conditions':[{'id':uuid.uuid5(uuid.NAMESPACE_URL,name).hex,'leftValue':'={{ $json.valid === true }}','rightValue':True,'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},x)
    node('Manual Intake Trigger','manualTrigger',1,{},0)
    code('Fictional Intake','return [{json:'+json.dumps(fixture,ensure_ascii=False)+'}];',220)
    code('Validate Intake',VALIDATE_INPUT,440)
    branch('Input Valid?',660)
    node('POST Onboarding Preview','httpRequest',4.5,{'method':'POST','url':'http://127.0.0.1:8002/v1/onboarding/preview',
        'sendBody':True,'specifyBody':'json','jsonBody':'={{ JSON.stringify($json.intake) }}',
        'options':{'timeout':15000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'text','outputPropertyName':'body'}}}},880,retryOnFail=False,onError='continueRegularOutput')
    code('Validate Onboarding Bundle',VALIDATE_BUNDLE,1100)
    branch('Bundle Valid?',1320)
    code('Success Summary',SUCCESS,1540)
    code('Failure Summary',FAILURE,1540,260)
    code('Execution Summary',SUMMARY,1760)
    edges={}
    def connect(a,b,output=0):
        rows=edges.setdefault(a,{'main':[]})['main']
        while len(rows)<=output:rows.append([])
        rows[output].append({'node':b,'type':'main','index':0})
    chain=['Manual Intake Trigger','Fictional Intake','Validate Intake','Input Valid?','POST Onboarding Preview','Validate Onboarding Bundle','Bundle Valid?','Success Summary','Execution Summary']
    for a,b in zip(chain,chain[1:]):connect(a,b)
    connect('Input Valid?','Failure Summary',1);connect('Bundle Valid?','Failure Summary',1);connect('Failure Summary','Execution Summary')
    return {'name':'LEGALFLOW — Fictional Legal Intake Preview','active':False,'nodes':nodes,'connections':edges,
            'settings':{'executionOrder':'v1','saveDataSuccessExecution':'all','saveDataErrorExecution':'all','saveManualExecutions':True}}


if __name__=='__main__':
    path=ROOT/'workflows/legal_intake_onboarding.json'
    path.write_text(json.dumps(build_workflow(),indent=2,ensure_ascii=False)+'\n')
    print(path)
