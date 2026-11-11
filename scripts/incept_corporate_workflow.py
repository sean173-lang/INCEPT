"""Separate INCEPT corporate-intake development graph; never overwrite the proven flow."""
import copy
import uuid
from scripts.incept_autonomous_workflow import build_workflow as base_workflow

ROUTE=r'''
const intake=JSON.parse(JSON.stringify($('Validate Intake').first().json.intake));
const type=intake.client.client_type||'unknown';
const jurisdiction=intake.client.jurisdiction;
const company=type==='company';
const supported=['Germany','UK','United Kingdom'].includes(jurisdiction);
const ready=type==='individual'||(company&&supported);
// Governing law is independent of the register jurisdiction; never infer it.
intake.matter.governing_law=intake.matter.governing_law||'unknown';
return [{json:{ready,intake,client_type:type,company,jurisdiction,
 state:ready?'intake_routed':'NEEDS_REVIEW',stage:'client_type_and_jurisdiction',
 reason:ready?null:type==='unknown'?'INSUFFICIENT_IDENTITY: explicit client type required':'INSUFFICIENT_IDENTITY: supported company jurisdiction required',
 substantive_law_status:intake.matter.governing_law==='Germany'?'explicit_German_law':intake.matter.governing_law==='United Kingdom'?'UK_NOT_VERIFIED_REQUIRES_LAWYER_REVIEW':'governing_law_unresolved'}}];
'''
CORPORATE_RESULT=r'''
const response=$input.first().json;
const result=response.statusCode===200&&response.body&&['CACHED','UNVERIFIED','UNAVAILABLE','NEEDS_REVIEW'].includes(response.body.status)?response.body:null;
return [{json:result||{status:'UNAVAILABLE',identity_verification_status:'verification_failed',provider_requests:0,financial_requests:0,
 missing_evidence:['Corporate helper unavailable or unsupported; ordinary preview remains available.'],sources:[],
 warnings:[{warning_id:'corporate:provider_failure:helper_unavailable',category:'provider_failure',message:'Corporate helper unavailable or unsupported; ordinary preview remains available.',source_ids:[]}],
 section_markdown:'\n## Corporate Client Intelligence\n\nUNAVAILABLE / NEEDS_REVIEW. Corporate evidence could not be retrieved; this does not establish that the company does not exist. Lawyer verification required.\n'}}];
'''
ENRICH=r'''
const base=$input.first().json;
const route=$('Route Client Type and Law').first().json;
let corporate=null;
if(route.company) {
 try{corporate=$('Corporate Intelligence Result').first().json;}catch{corporate={status:'UNAVAILABLE',warnings:[{warning_id:'corporate:provider_failure:result_missing',category:'provider_failure',message:'Corporate result was not available; lawyer verification required.',source_ids:[]}],section_markdown:'\n## Corporate Client Intelligence\n\nUNAVAILABLE. Lawyer review required.\n'};}
 base.bundle.assessment.content_markdown+=corporate.section_markdown||'\n## Corporate Client Intelligence\n\nUNAVAILABLE.\n';
 const assessment=base.bundle.assessment;
 const unique=items=>[...new Set(items)];
 // Older helper responses retain their warning text without claiming verification.
 const warnings=Array.isArray(corporate.warnings)?corporate.warnings:
  (corporate.missing_evidence||[]).map(message=>({warning_id:'corporate:legacy:'+message,category:'missing_information',message,source_ids:[]}));
 const existing=assessment.review_warnings||[];
 const seen=new Set(existing.map(w=>w.warning_id));
 assessment.review_warnings=[...existing,...warnings.filter(w=>{if(seen.has(w.warning_id))return false;seen.add(w.warning_id);return true;})];
 assessment.missing_information=unique([...(assessment.missing_information||[]),...warnings.filter(w=>w.category==='missing_information').map(w=>w.message)]);
 base.uncertainty=unique([...(base.uncertainty||[]),...warnings.map(w=>w.message)]);

 const sourceIds=new Set(assessment.sources.map(s=>s.source_id));
 for(const source of corporate.sources||[]) {
  if(sourceIds.has(source.source_id))continue;
  sourceIds.add(source.source_id);
  base.bundle.assessment.sources.push({source_id:source.source_id,kind:source.provider==='Tavily cached excerpt'?'public_search_lead':'corporate_record',
   locator:source.locator,content:source.category+'; provider '+source.provider+'; retrieved '+String(source.retrieved_at)+'; freshness '+source.freshness+'; synthetic '+source.synthetic,
   url:source.url||null,reviewed_at:null,document_date:null});
 }
}
return [{json:{...base,product:'INCEPT',workflow_variant:'optional_corporate_intelligence',
 corporate_client_intelligence:corporate,client_type:route.client_type,company_jurisdiction:route.jurisdiction,
 governing_law:route.intake.matter.governing_law,substantive_law_status:route.substantive_law_status,
 financial_requests:0,corporate_provider_requests:0,
 corporate_case_findings:corporate?.status||'not_applicable',
 all_external_actions_pending_lawyer_approval:true}}];
'''


def build_workflow():
    w=copy.deepcopy(base_workflow());w['name']='INCEPT — Corporate Client Intelligence Development'
    nodes=w['nodes'];lookup={n['name']:n for n in nodes};edges=w['connections']
    for n in nodes:n['id']=uuid.uuid5(uuid.NAMESPACE_URL,'incept-corporate:'+n['name']).hex
    def add(name,kind,version,parameters,x,y=1500,**kw):
        nodes.append({'id':uuid.uuid5(uuid.NAMESPACE_URL,'incept-corporate:'+name).hex,'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[x,y],'parameters':parameters,**kw})
    def code(name,script,x):add(name,'code',2,{'mode':'runOnceForAllItems','jsCode':script},x)
    def gate(name,field,x):
        template=copy.deepcopy(lookup['Intake Valid?']);template.update(id=uuid.uuid5(uuid.NAMESPACE_URL,name).hex,name=name,position=[x,1500]);template['parameters']['conditions']['conditions'][0]['leftValue']='={{ $json.'+field+' === true }}';nodes.append(template)
    def edge(a,b,index=0):
        outputs=edges.setdefault(a,{'main':[]})['main']
        while len(outputs)<=index:outputs.append([])
        outputs[index]=[{'node':b,'type':'main','index':0}]
    # Preserve the old workflow and old validator. Only this new copy accepts UK companies.
    js=lookup['Validate Intake']['parameters']['jsCode']
    js=js.replace("x.jurisdiction !== 'Germany'", "(key==='firm'?x.jurisdiction!=='Germany':!['Germany','United Kingdom','UK','unknown','unsupported'].includes(x.jurisdiction))")
    lookup['Validate Intake']['parameters']['jsCode']=js
    validator=lookup['Validate Onboarding Bundle']['parameters']['jsCode']
    validator=validator.replace('r.guidance.length>=4', "r.guidance.length>=(intake.matter.governing_law==='Germany'?4:0)")
    lookup['Validate Onboarding Bundle']['parameters']['jsCode']=validator
    code('Route Client Type and Law',ROUTE,0);gate('Identity Routing Ready?','ready',240)
    edge('Intake Valid?','Route Client Type and Law');edge('Route Client Type and Law','Identity Routing Ready?');edge('Identity Routing Ready?','Read Existing Matters');edge('Identity Routing Ready?','Clean Stop Summary',1)
    lookup['POST Real Onboarding Preview']['parameters']['jsonBody']="={{ JSON.stringify($('Route Client Type and Law').first().json.intake) }}"
    plan=lookup['Plan Bounded Primary Research']['parameters']['jsCode']
    plan=plan.replace("const intake=$('Validate Intake').first().json.intake;", "const intake=$('Route Client Type and Law').first().json.intake;")
    plan=plan.replace("const relevant=/vertrag|liefer|contract/.test(scope)", "const relevant=intake.matter.governing_law==='Germany' && /vertrag|liefer|contract/.test(scope)")
    lookup['Plan Bounded Primary Research']['parameters']['jsCode']=plan
    code('Company Client?',"return [{json:{company:$('Route Client Type and Law').first().json.company}}];",480);gate('Corporate Intelligence Required?','company',720)
    request="={{ JSON.stringify({synthetic_data:true,client_id:$('Validate Onboarding Bundle').first().json.bundle.client.client_id,matter_id:$('Validate Onboarding Bundle').first().json.bundle.matter.matter_id,client:$('Route Client Type and Law').first().json.intake.client,source_policy:'cache_only',max_external_requests:0,max_cached_operations:3}) }}"
    add('Get Corporate Intelligence','httpRequest',4.5,{'method':'POST','url':'http://127.0.0.1:8002/v1/onboarding/corporate-intelligence','sendBody':True,'specifyBody':'json','jsonBody':request,
        'options':{'timeout':15000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}},960,retryOnFail=False,onError='continueRegularOutput')
    code('Corporate Intelligence Result',CORPORATE_RESULT,1200);code('Unified Corporate Mandate Report',ENRICH,1440)
    edge('Bundle Valid?','Company Client?');edge('Company Client?','Corporate Intelligence Required?')
    edge('Corporate Intelligence Required?','Get Corporate Intelligence');edge('Corporate Intelligence Required?','Plan Bounded Primary Research',1)
    edge('Get Corporate Intelligence','Corporate Intelligence Result');edge('Corporate Intelligence Result','Plan Bounded Primary Research')
    edge('Integrated Onboarding Report','Unified Corporate Mandate Report')
    for node in nodes:
        url=node['parameters'].get('url')
        if isinstance(url,str) and url.startswith('http://127.0.0.1:8002/'):
            node['parameters']['url']=url.replace(':8002/',':8003/',1)
    return w


def bind_credentials(metadata):
    w=build_workflow()
    for n in w['nodes']:
        kind=n['parameters'].get('nodeCredentialType')
        if n['type']=='n8n-nodes-base.googleSheets':kind='googleSheetsOAuth2Api'
        if kind:
            c=metadata.get(kind,{})
            if c.get('type')!=kind or not c.get('id') or not c.get('name'):raise ValueError('Compatible existing credential metadata required')
            n['credentials']={kind:{'id':c['id'],'name':c['name']}}
    return w
