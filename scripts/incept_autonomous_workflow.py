"""Integrated read-only development intake; no fixture fallback or side-effect nodes."""
import copy
import uuid
from scripts.intake_workflow import VALIDATE_INPUT, VALIDATE_BUNDLE

MAILBOX='project-demo@example.invalid'
SUBJECT='[INCEPT DEMO APPROVED] Fictional intake v1'
QUERY='in:inbox from:('+MAILBOX+') to:('+MAILBOX+') subject:"INCEPT DEMO APPROVED" subject:"Fictional intake v1" -in:trash -in:spam'
# Internal builder/test placeholder; canonical export requires local account bindings.
SHEET_ID='DEMO_SHEET_DEFAULT_001'

SEARCH_CHECK=r'''
const r=$input.first().json;
if(r.statusCode!==200) return [{json:{state:'ERROR',stage:'gmail_search',reason:'gmail_search_http_failure',http_status:r.statusCode??null,ready:false}}];
const b=r.body;
if(!b || typeof b!=='object' || (b.messages!==undefined && !Array.isArray(b.messages))) return [{json:{state:'ERROR',stage:'gmail_search',reason:'unsupported_search_response',ready:false}}];
const messages=b.messages||[];
if(messages.length===0) return [{json:{state:'NEEDS_DEMO_EMAIL',stage:'gmail_search',reason:'no_approved_fictional_inquiry_found',candidate_count:0,gmail_http_status:200,email_bodies_read:0,ready:false}}];
if(messages.length!==1 || b.nextPageToken) return [{json:{state:'NEEDS_REVIEW',stage:'gmail_search',reason:'ambiguous_demo_messages',candidate_count:messages.length,email_bodies_read:0,ready:false}}];
if(typeof messages[0].id!=='string' || !/^[a-fA-F0-9]{8,64}$/.test(messages[0].id)) return [{json:{state:'ERROR',reason:'invalid_message_id',stage:'gmail_search',ready:false}}];
return [{json:{state:'candidate_metadata_only',message_id:messages[0].id,ready:true}}];
'''
METADATA_CHECK=r'''
const r=$input.first().json,b=r.body,selected=$('Check Demo Search').first().json;
const stop=reason=>[{json:{state:'NEEDS_REVIEW',stage:'gmail_metadata',reason,email_bodies_read:0,ready:false}}];
if(r.statusCode!==200 || !b || b.id!==selected.message_id) return stop('message_metadata_unavailable_or_mismatched');
const headers=b.payload?.headers;
if(!Array.isArray(headers) || !Array.isArray(b.labelIds) || !b.labelIds.includes('INBOX') || b.labelIds.some(x=>['SPAM','TRASH','DRAFT'].includes(x))) return stop('message_not_approved_inbox_inquiry');
function header(name) {const values=headers.filter(h=>h.name?.toLowerCase()===name);return values.length===1?values[0].value:null;}
function address(value) {if(typeof value!=='string'||/[\r\n]/.test(value))return null;const match=value.match(/^(?:[^<>]*<)?([A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+)>?$/);return match?.[1].toLowerCase();}
if(address(header('from'))!=='project-demo@example.invalid' || address(header('to'))!=='project-demo@example.invalid' || header('subject')!=='[INCEPT DEMO APPROVED] Fictional intake v1') return stop('sender_recipient_or_exact_approval_subject_mismatch');
if(typeof b.sizeEstimate!=='number' || b.sizeEstimate>65536 || !/^\d+$/.test(b.internalDate||'')) return stop('message_size_or_date_requires_review');
return [{json:{state:'approved_demo_metadata',message_id:b.id,internal_date:b.internalDate,ready:true}}];
'''
EXTRACT=r'''
const r=$input.first().json,b=r.body,approved=$('Validate Approved Metadata').first().json;
function stop(reason,missing=[]) {return [{json:{ready:false,state:'NEEDS_INTAKE_INFORMATION',stage:'intake_extraction',reason,missing_fields:missing}}];}
if(r.statusCode!==200 || b?.id!==approved.message_id) return stop('approved_body_unavailable_or_mismatched');
const parts=[b.payload,...(b.payload?.parts||[])].filter(p=>p?.mimeType==='text/plain' && typeof p.body?.data==='string');
if(parts.length!==1) return stop('one_unambiguous_plain_text_body_required');
const encoded=parts[0].body.data;
if(!/^[A-Za-z0-9_-]*={0,2}$/.test(encoded) || encoded.length>90000) return stop('invalid_or_oversized_body');
let content;try {content=Buffer.from(encoded,'base64url').toString('utf8');} catch {return stop('invalid_body_encoding');}
const prefix='INCEPT_SYNTHETIC_INTAKE_V1\n';
content=content.replace(/\r\n/g,'\n').trim();
if(!content.startsWith(prefix)) return stop('explicit_synthetic_payload_marker_required');
const raw=content.slice(prefix.length);
let intake,wraps=0;
try {intake=JSON.parse(raw);} catch {
 // Email plain-text transport can insert line wraps inside otherwise valid JSON
 // strings. Normalize those whitespace characters only; never repair tokens,
 // supply fields, remove trailing text or load values from a fixture.
 let quoted=false,escaped=false,repaired='';
 for(const char of raw) {
  if(quoted && char==='\n') {
   if(escaped)return stop('unsupported_json_line_continuation');
   repaired+=' ';wraps++;continue;
  }
  repaired+=char;
  if(escaped)escaped=false;
  else if(quoted && char==='\\')escaped=true;
  else if(char==='"')quoted=!quoted;
 }
 if(!wraps)return stop('structured_intake_json_required_no_fixture_fallback');
 try {intake=JSON.parse(repaired);} catch {return stop('structured_intake_json_required_no_fixture_fallback');}
}
if(!intake || typeof intake!=='object' || Array.isArray(intake) || intake.synthetic_data!==true) return stop('explicit_synthetic_acknowledgement_required');
const paths=['client.name','client.address','client.email','client.jurisdiction','firm.name','firm.address','firm.email','firm.lawyer_name','firm.jurisdiction','matter.title','matter.summary','matter.requested_scope','fees.net_hourly_rate','fees.currency','fees.vat_mode','draft_date'];
const missing=paths.filter(path=>{let value=intake;for(const key of path.split('.'))value=value?.[key];return value===undefined || value===null || value==='';});
if(missing.length)return stop('required_intake_fields_missing',missing);
// The actual approved Gmail message determines local persistence idempotency.
intake.idempotency_key='incept-gmail-'+approved.message_id;
return [{json:{ready:true,state:'extracted_unverified_intake',intake,missing_fields:['Original case documents, assertions and signing authority remain unverified.',...(wraps?['Plain-text line wraps inside JSON strings were normalized to spaces; original email is unchanged and lawyer review remains required.']:[])],
 provenance:{origin:'approved_demo_gmail_message',message_id:approved.message_id,body_accessed_after_metadata_validation:true,fixture_substitution:false,
 normalized_quoted_linewraps:wraps,source_message_unchanged:true,normalization_requires_review:wraps>0}}}];
'''
LOOKUP=r'''
const rows=$input.all().map(x=>x.json).filter(x=>Object.keys(x).some(k=>k!=='row_number'));
if(rows.some(r=>r.error))return [{json:{ready:false,state:'ERROR',stage:'sheets_lookup',reason:'sheet_read_failed'}}];
const intake=$('Validate Intake').first().json.intake;
const columns=new Set(rows.flatMap(r=>Object.keys(r)));
let matches=[],status,certainty;
if(columns.has('idempotency_key')) {matches=rows.filter(r=>r.idempotency_key===intake.idempotency_key);status=matches.length?'existing_matter_key_candidates':'no_key_match_in_bounded_range';certainty='key_match_not_independent_verification';}
else if(columns.has('client_name') && columns.has('matter_id')) {matches=rows.filter(r=>r.client_name===intake.client.name && r.matter_id);status=matches.length?'existing_matter_candidates_by_client_name':'no_client_name_match_in_bounded_range';certainty='name_only_candidates_require_lawyer_review';}
else {status=rows.length?'unsupported_matter_lookup_columns':'empty_bounded_sheet_range';certainty='matter_existence_undetermined';}
return [{json:{ready:true,state:'read_only_lookup_complete',spreadsheet_id:'DEMO_SHEET_DEFAULT_001',range:'A1:Z101',rows_read:rows.length,candidate_count:matches.length,lookup_status:status,certainty,
 limitation:'Read-only bounded search is not proof of absence; no row created or updated.'}}];
'''
CALENDAR_CHECK=r'''
const r=$input.first().json,b=r.body;
if(r.statusCode!==200 || b?.kind!=='calendar#calendarList' || (b.items!==undefined&&!Array.isArray(b.items))) return [{json:{ready:false,state:'ERROR',stage:'calendar_read',reason:'calendar_list_failed'}}];
return [{json:{ready:true,calendar_count:(b.items||[]).length,has_more:!!b.nextPageToken,http_status:200,check_type:'calendar_list_only',availability_verified:false,event_data_read:false}}];
'''
PLAN_RESEARCH=r'''
const intake=$('Validate Intake').first().json.intake;
const scope=[intake.matter.title,intake.matter.summary,intake.matter.requested_scope].join(' ').toLowerCase();
const relevant=/vertrag|liefer|contract/.test(scope) && /forderung|zahlung|payment|invoice/.test(scope);
return [{json:{relevant,tool:relevant?'allowlisted_official_legislation_get':null,
 source_url:'https://www.gesetze-im-internet.de/bgb/__286.html',max_source_requests:1,
 rationale:relevant?'Contractual payment-demand allegation: review general default prerequisites, not established liability.':'Matter outside this bounded rule; no unrelated source search.'}}];
'''
PREPARE_RESEARCH=r'''
const response=$input.first().json;
let bytes=null;
if(response.statusCode===200 && $input.first().binary?.official_source) {
 try {bytes=await this.helpers.getBinaryDataBuffer(0,'official_source');} catch {}
}
return [{json:{synthetic_data:true,matter:$('Validate Intake').first().json.intake.matter,
 bundle:$('Validate Onboarding Bundle').first().json.bundle,
 source_url:'https://www.gesetze-im-internet.de/bgb/__286.html',retrieved_at:new Date().toISOString(),
 http_status:Number.isInteger(response.statusCode)?response.statusCode:null,
 source_html:'',source_bytes_base64:bytes && bytes.length<=200000?bytes.toString('base64'):'',
 source_content_type:response.headers?.['content-type']||'',
 retrieval_error:bytes && bytes.length>200000?'oversized_response':!bytes?'network_or_http_failure':null}}];
'''
RESEARCH_RESULT=r'''
const input=$input.first().json;
const candidate=$('Validate Intake').first().json.intake.matter.claimed_deadline??null;
function unavailable(status,reason) {return {status,source_url:'https://www.gesetze-im-internet.de/bgb/__286.html',retrieved_at:null,
 verified_rules:[],unresolved_research:[reason],case_findings_verified:false,enriched_assessment:null,
 potential_deadline_analysis:{state:'pending_lawyer_approval',candidate_date:candidate,confirmed_deadline:null,calculated_deadline:null,trigger_dates_verified:false,source_ids:[],explanation:'Original due date, reminder receipt and service evidence are missing; no confirmed deadline calculated.'}};}
if(input.research_not_applicable) return [{json:unavailable('not_applicable','No relevant source action selected for this matter.')}];
const b=input.body;
if(input.statusCode!==200 || !b || !['verified','partially_verified','unavailable','not_applicable'].includes(b.status) || !Array.isArray(b.verified_rules) || !Array.isArray(b.unresolved_research) || b.case_findings_verified!==false || b.source_url!=='https://www.gesetze-im-internet.de/bgb/__286.html') return [{json:unavailable('unavailable','Research verification helper unavailable or response unsupported.')}];
const deadline=b.potential_deadline_analysis;
if(deadline?.confirmed_deadline!==null || deadline?.calculated_deadline!==null || deadline?.state!=='pending_lawyer_approval') return [{json:unavailable('unavailable','Unsafe deadline result rejected.')}];
const sources=new Set((b.enriched_assessment?.sources||[]).map(x=>x.source_id));
if(b.verified_rules.some(rule=>rule.evidence_status!=='verified_source_rule_not_case_finding' || typeof rule.quote!=='string' || !sources.has(rule.source_id))) return [{json:unavailable('unavailable','Unsupported primary-source citation rejected.')}];
return [{json:b}];
'''

FINAL=r'''
const checked=$('Validate Onboarding Bundle').first().json;
const email=$('Extract Approved Inquiry').first().json;
const lookup=$('Assess Existing Matter Lookup').first().json;
const calendar=$('Check Calendar Metadata').first().json;
let research;
try {research=$('Primary Research Result').first().json;} catch {research={status:'unavailable',verified_rules:[],unresolved_research:['Primary research stage not executed.'],enriched_assessment:null,potential_deadline_analysis:{state:'pending_lawyer_approval',confirmed_deadline:null,calculated_deadline:null}};}
const bundle=JSON.parse(JSON.stringify(checked.bundle));
if(research.enriched_assessment) bundle.assessment=research.enriched_assessment;
const assessment=bundle.assessment;
const researched=['verified','partially_verified'].includes(research.status) && research.verified_rules.length>0;
return [{json:{product:'INCEPT',state:'PREVIEW_READY_FOR_LAWYER_REVIEW',n8n_execution_id:String($execution.id),
 integrated_preview_complete:true,approved_live_email_processed:true,fixture_substitution:false,email_bodies_read:1,
 gmail_provenance:email.provenance,sheets:lookup,calendar,
 bundle,validation:{...checked.validation,sources:assessment.sources.length,primary_research_status:research.status},primary_research:research,potential_deadline_analysis:research.potential_deadline_analysis,
 uncertainty:[...email.missing_fields,...assessment.missing_information,lookup.limitation,'Calendar listing does not determine availability or a legal deadline.'],
 autonomous_research:researched,research_method:'one_bounded_rule_selected_primary_source_check',research_scope:'structured_intake_plus_RAG_and_optional_verified_primary_source',
 source_grounded_live_case_research_performed:researched,external_writes:0,emails_sent:0,calendar_events_created:0,spreadsheet_writes:0,paid_api_calls:0,
 lawyer_approval_bypassed:false,completed_at:new Date().toISOString()}}];
'''
STOP=r'''
const input=$input.first().json;
function prior(name) {try{return $(name).first().json;}catch{return null;}}
const bodyRead=prior('Read Specific Approved Body'),sheet=prior('Assess Existing Matter Lookup'),calendar=prior('Check Calendar Metadata'),preview=prior('POST Real Onboarding Preview');
return [{json:{product:'INCEPT',state:input.state||'NEEDS_REVIEW',stage:input.stage||'validation',reason:input.reason||input.reasons||['validation_failed'],
 missing_fields:input.missing_fields||[],n8n_execution_id:String($execution.id),integrated_preview_complete:false,
 gmail_search_http_status:input.gmail_http_status??null,email_bodies_read:bodyRead?.statusCode===200?1:0,
 sheets_executed:!!sheet,calendar_executed:!!calendar,fixture_substitution:false,documents_generated:preview?.statusCode===200&&Array.isArray(preview.body?.documents),
 autonomous_research:false,source_grounded_live_case_research_performed:false,
 external_writes:0,emails_sent:0,calendar_events_created:0,spreadsheet_writes:0,paid_api_calls:0,
 lawyer_approval_bypassed:false,completed_at:new Date().toISOString()}}];
'''


def build_workflow():
    nodes=[];edges={}
    def add(name,kind,version,params,**extras):
        i=len(nodes);nodes.append({'id':uuid.uuid5(uuid.NAMESPACE_URL,'incept-integrated:'+name).hex,'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[(i%8)*240,(i//8)*300],'parameters':params,**extras})
    def code(name,body):add(name,'code',2,{'mode':'runOnceForAllItems','jsCode':body})
    def gate(name,field='ready'):
        add(name,'if',2.2,{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},'conditions':[{'id':uuid.uuid5(uuid.NAMESPACE_URL,name).hex,'leftValue':'={{ $json.'+field+' === true }}','rightValue':True,'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}})
    def http(name,url,kind=None,query=None,method='GET'):
        params={'method':method,'url':url,'options':{'timeout':15000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}}
        if kind:params.update(authentication='predefinedCredentialType',nodeCredentialType=kind)
        if query:params.update(sendQuery=True,queryParameters={'parameters':[{'name':k,'value':v} for k,v in query]})
        if method=='POST':params.update(sendBody=True,specifyBody='json',jsonBody="={{ JSON.stringify($('Validate Intake').first().json.intake) }}")
        add(name,'httpRequest',4.5,params,retryOnFail=False,onError='continueRegularOutput')
    add('Manual Integrated Intake','manualTrigger',1,{})
    http('Find Approved Demo Inquiry','https://gmail.googleapis.com/gmail/v1/users/me/messages','gmailOAuth2',[('q',QUERY),('maxResults','2'),('fields','messages(id),nextPageToken,resultSizeEstimate')])
    code('Check Demo Search',SEARCH_CHECK);gate('One Approved Candidate?')
    http('Read Candidate Headers',"={{ 'https://gmail.googleapis.com/gmail/v1/users/me/messages/' + encodeURIComponent($json.message_id) }}",'gmailOAuth2',
         [('format','metadata'),('metadataHeaders','From'),('metadataHeaders','To'),('metadataHeaders','Subject'),('fields','id,labelIds,internalDate,sizeEstimate,payload(headers)')])
    code('Validate Approved Metadata',METADATA_CHECK);gate('Metadata Approved?')
    http('Read Specific Approved Body',"={{ 'https://gmail.googleapis.com/gmail/v1/users/me/messages/' + encodeURIComponent($json.message_id) }}",'gmailOAuth2',
         [('format','full'),('fields','id,payload(mimeType,body(data,size),parts(mimeType,body(data,size)))')])
    code('Extract Approved Inquiry',EXTRACT);gate('Intake Extracted?')
    code('Validate Intake',VALIDATE_INPUT.replace('const intake = $input.first().json;','const intake = $input.first().json.intake;'));gate('Intake Valid?','valid')
    add('Read Existing Matters','googleSheets',4.7,{'authentication':'oAuth2','resource':'sheet','operation':'read',
         'documentId':{'__rl':True,'mode':'id','value':SHEET_ID},'sheetName':{'__rl':True,'mode':'id','value':'0'},
         'options':{'dataLocationOnSheet':{'values':{'rangeDefinition':'specifyRangeA1','range':'A1:Z101'}},'returnFirstMatch':False}},retryOnFail=False,onError='continueRegularOutput',alwaysOutputData=True)
    code('Assess Existing Matter Lookup',LOOKUP);gate('Lookup Read Completed?')
    http('Read Accessible Calendars','https://www.googleapis.com/calendar/v3/users/me/calendarList','googleCalendarOAuth2Api',
         [('maxResults','100'),('fields','kind,nextPageToken,items(accessRole,primary)')])
    code('Check Calendar Metadata',CALENDAR_CHECK);gate('Calendar Read Completed?')
    http('POST Real Onboarding Preview','http://127.0.0.1:8002/v1/onboarding/preview',method='POST')
    code('Validate Onboarding Bundle',VALIDATE_BUNDLE);gate('Bundle Valid?','valid')
    code('Plan Bounded Primary Research',PLAN_RESEARCH);gate('Research Relevant?','relevant')
    http('Retrieve Official Provision','https://www.gesetze-im-internet.de/bgb/__286.html')
    nodes[-1]['parameters']['options']['response']['response'].update(responseFormat='file',outputPropertyName='official_source')
    code('Prepare Primary Research Input',PREPARE_RESEARCH)
    http('Verify Primary Source','http://127.0.0.1:8002/v1/onboarding/research/verify',method='POST')
    nodes[-1]['parameters']['jsonBody']='={{ JSON.stringify($json) }}'
    code('Research Not Applicable','return [{json:{research_not_applicable:true}}];')
    code('Primary Research Result',RESEARCH_RESULT)
    code('Integrated Onboarding Report',FINAL);code('Clean Stop Summary',STOP)
    chain=[n['name'] for n in nodes if n['name'] not in ('Clean Stop Summary','Research Not Applicable')]
    def connect(a,b,index=0):
        outputs=edges.setdefault(a,{'main':[]})['main']
        while len(outputs)<=index:outputs.append([])
        outputs[index].append({'node':b,'type':'main','index':0})
    for a,b in zip(chain,chain[1:]):connect(a,b)
    for node in nodes:
        if node['type']=='n8n-nodes-base.if' and node['name']!='Research Relevant?':connect(node['name'],'Clean Stop Summary',1)
    connect('Research Relevant?','Research Not Applicable',1)
    connect('Research Not Applicable','Primary Research Result')
    return {'name':'INCEPT — Integrated Autonomous Intake Development','active':False,'nodes':nodes,'connections':edges,
            'settings':{'executionOrder':'v1','saveDataSuccessExecution':'all','saveDataErrorExecution':'all','saveManualExecutions':True}}


def bind_credentials(metadata):
    result=copy.deepcopy(build_workflow())
    for node in result['nodes']:
        kind=node['parameters'].get('nodeCredentialType')
        if node['type']=='n8n-nodes-base.googleSheets':kind='googleSheetsOAuth2Api'
        if kind:
            credential=metadata.get(kind,{})
            if credential.get('type')!=kind or not credential.get('id') or not credential.get('name'):raise ValueError('Compatible existing OAuth metadata required')
            node['credentials']={kind:{'id':credential['id'],'name':credential['name']}}
    return result
