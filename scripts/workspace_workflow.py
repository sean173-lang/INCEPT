"""Bounded Gmail workspace graphs; synthesis uses the existing guarded FastAPI endpoint."""
import copy,json,uuid,os
from pathlib import Path
from dotenv import dotenv_values
from scripts.incept_prose_workflow import build_workflow as prose_workflow
from scripts.incept_ai_workflow import VALIDATE as AI_VALIDATE

GMAIL='https://gmail.googleapis.com/gmail/v1/users/me/'
SYNTHESIS_BACKEND='http://127.0.0.1:8003'
BACKEND=SYNTHESIS_BACKEND
ROOT=Path(__file__).resolve().parents[1]

def node(name,kind,params,version=2):
 return {'id':uuid.uuid5(uuid.NAMESPACE_URL,'incept-workspace:'+name).hex,'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[0,0],'parameters':params,'retryOnFail':False}
def bind_fastapi(n):
 token=os.getenv('LEGALFLOW_SERVICE_TOKEN') or dotenv_values(ROOT/'.env').get('LEGALFLOW_SERVICE_TOKEN')
 if not token:raise ValueError('Authenticated FastAPI service-key binding is unavailable')
 n['parameters'].update(sendHeaders=True,headerParameters={'parameters':[{'name':'X-LEGALFLOW-Service-Key','value':token}]})
 return n
def http(name,url,body=None,binding=None):
 p={'method':'POST' if body else 'GET','url':url,'options':{'timeout':20000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}}
 if body:p.update(sendBody=True,specifyBody='json',jsonBody=body)
 n=node(name,'httpRequest',p,4.5)
 if url.startswith(GMAIL) or url.startswith('={{'):
  p.update(authentication='predefinedCredentialType',nodeCredentialType='gmailOAuth2')
  if binding:n['credentials']={'gmailOAuth2':binding}
 elif url.startswith(SYNTHESIS_BACKEND+'/'):
  bind_fastapi(n)
 return n
def code(name,js):return node(name,'code',{'mode':'runOnceForAllItems','jsCode':js})
def chain(name,nodes):
 all_nodes=[node('Manual Workspace Operation','manualTrigger',{},1)]+nodes
 edges={a['name']:{'main':[[{'node':b['name'],'type':'main','index':0}]]} for a,b in zip(all_nodes,all_nodes[1:])}
 return {'name':name,'active':False,'nodes':all_nodes,'connections':edges,'settings':{'executionOrder':'v1','saveDataSuccessExecution':'all','saveDataErrorExecution':'all','saveManualExecutions':True}}

def inbox_graph(query='in:inbox -in:spam -in:trash',binding=None):
 from urllib.parse import urlencode
 return chain('INCEPT workspace — read inbox metadata only',[
  http('Read Gmail Profile',GMAIL+'profile',binding=binding),
  http('List Recent Gmail IDs',GMAIL+'messages?'+urlencode({'q':query,'maxResults':8}),binding=binding),
  code('Bound Message IDs',"const r=$input.first().json;if(r.statusCode!==200)throw new Error('Gmail list unavailable');const ids=r.body?.messages||[];if(!Array.isArray(ids)||ids.length>8)throw new Error('Unsupported list');return ids.map(v=>{if(!/^[a-f0-9]{8,64}$/i.test(v.id))throw new Error('Invalid Gmail ID');return {json:{message_id:v.id}};});"),
  # An empty list remains an explicit response, never a fabricated message.
  http('Read Message Metadata',"={{ '"+GMAIL+"messages/'+($json.empty?'NO_MESSAGES':$json.message_id)+'?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject&metadataHeaders=Date&metadataHeaders=Message-ID' }}",binding=binding)])

def message_graph(mid,binding=None):return chain('INCEPT workspace — read selected message',[http('Read Selected Gmail Message',GMAIL+'messages/'+mid+'?format=full',binding=binding)])

def extraction_graph(message,binding=None):
 encoded_parts=json.dumps(json.dumps(message['encoded_parts'],ensure_ascii=False),ensure_ascii=False)
 return chain('INCEPT workspace — extract selected legal inquiry',[
  http('Recheck Selected Gmail Message for Extraction',GMAIL+'messages/'+message['id']+'?format=full',binding=binding),
  code('Validate Selected Message for Extraction',"const r=$input.first().json,b=r.body;function parts(p){return [...(p?.body?.data&&['text/plain','text/html'].includes(p.mimeType)?[p.body.data]:[]),...(p?.parts||[]).flatMap(parts)];}if(r.statusCode!==200||b?.id!=="+json.dumps(message['id'])+"||JSON.stringify(parts(b.payload))!==JSON.stringify(JSON.parse("+encoded_parts+")))throw new Error('Selected message content changed; refresh before extraction');const h=Object.fromEntries((b.payload?.headers||[]).map(x=>[x.name.toLowerCase(),x.value]));return [{json:{authorized_for_ai:true,message_id:b.id,sender:h.from||'',recipient:h.to||'',subject:h.subject||'(no subject)',body:"+json.dumps(message['body'],ensure_ascii=False)+"}}];"),
  http('POST Selected Inquiry Extraction',BACKEND+'/v1/onboarding/extract','={{ JSON.stringify($json) }}'),
  code('Validate Selected Inquiry Extraction',"const r=$input.first().json,b=r.body;if(r.statusCode!==200||b?.status!=='completed'||b.model_used!==true||b.execution_mode!=='live'||b.sender_authority_verified!==false||b.lawyer_review_required!==true||b.grounding?.method!=='exact_source_span_resolution_not_semantic_acceptance')throw new Error('AI extraction failed or failed source-span validation: '+(b?.reason||'extraction_not_completed'));return [{json:{message_id:"+json.dumps(message['id'])+",extraction:b.extraction,model:b.model,usage:b.usage,live_request:b.live_request,grounding:b.grounding}}];")])

def analysis_graph(message,payload,binding=None):
 encoded_parts=json.dumps(json.dumps(message['encoded_parts'],ensure_ascii=False),ensure_ascii=False)
 graph=chain('INCEPT workspace — selected-message mandate processing',[
  http('Recheck Selected Gmail Message',GMAIL+'messages/'+message['id']+'?format=full',binding=binding),
  code('Validate Selected Message and Intake',"const r=$input.first().json,b=r.body;function parts(p){return [...(p?.body?.data&&['text/plain','text/html'].includes(p.mimeType)?[p.body.data]:[]),...(p?.parts||[]).flatMap(parts)];}if(r.statusCode!==200||b?.id!=="+json.dumps(message['id'])+"||JSON.stringify(parts(b.payload))!==JSON.stringify(JSON.parse("+encoded_parts+")))throw new Error('Selected message content changed; refresh before analysis');return [{json:"+json.dumps(payload,ensure_ascii=False)+"}];"),
  http('POST Selected Intake Assessment',BACKEND+'/v1/onboarding/assessment','={{ JSON.stringify($json) }}'),
  code('Validate Selected Assessment',"const r=$input.first().json,b=r.body;if(r.statusCode!==200||!b?.matter?.matter_id||b.documents?.length!==0||!Array.isArray(b.proposed_actions)||b.proposed_actions.some(a=>a.executed||a.state!=='pending_lawyer_approval')||b.external_actions_executed!==false||b.paid_api_calls!==0)throw new Error('Assessment response invalid');return [{json:{bundle:b,legal_research:[]}}];")])
 scope=' '.join([payload['matter']['summary'],payload['matter']['title'],payload['matter']['requested_scope']]).lower()
 sale_matter=any(t in scope for t in ('kaufvertrag','kaufpreis','lieferung','verspät','verspaet','sachmangel','defekt','produktionsmaschine','schadensersatz'))
 payment_matter=any(t in scope for t in ('rechnung','zahlung','payment','invoice','forderung'))
 relevant=sale_matter or payment_matter
 previous='Validate Selected Assessment'
 if relevant:
  templates={n['name']:n for n in prose_workflow()['nodes']}
  provisions=('433','434','437','439','280','281','286','323') if sale_matter else ('611','614','631','640','633','634','641','632a','320')
  for n in provisions:
   for label in ('Retrieve Official BGB ','Prepare Source Check ','Verify Official Wording ','Attach Checked Guidance '):
    new=copy.deepcopy(templates.get(label+n,templates[label+'611']));new_name=label+n;new['name']=new_name;new['id']=uuid.uuid5(uuid.NAMESPACE_URL,'incept-workspace:'+new_name).hex;new['position']=[len(graph['nodes'])*220,0];p=new['parameters']
    if label=='Retrieve Official BGB ':p['url']='https://www.gesetze-im-internet.de/bgb/__'+n+'.html'
    if label=='Prepare Source Check ':
     p['jsCode']=p['jsCode'].replace("synthetic_data:true,",'').replace("provision:'611'","provision:'"+n+"'").replace('/bgb/__611.html','/bgb/__'+n+'.html')
    if label=='Verify Official Wording ':p['url']=BACKEND+'/v1/onboarding/payment-research/verify'
    if label=='Verify Official Wording ':bind_fastapi(new)
    if label=='Attach Checked Guidance ':
     p['jsCode']="const r=$input.first().json,e=r.body,p=JSON.parse(JSON.stringify($('"+previous+"').first().json));if(r.statusCode===200&&e?.status==='wording_verified'){p.legal_research.push(e);p.bundle.assessment.sources.push(e.source);p.bundle.assessment.guidance.push({description:e.source.content,status:'reference_guidance',source_ids:[e.source.source_id]});p.bundle.assessment.content_markdown+='\\n## Official German legal source — applicability requires confirmation\\n'+e.source.locator+'\\n'+e.source.content+'\\n'+e.source.url+'; retrieved '+e.retrieved_at+'\\n'+e.limitation+'\\n';}else{p.bundle.assessment.missing_information.push('Official legal-source wording could not be validated; lawyer research required.');p.bundle.assessment.content_markdown+='\\nOfficial legal source wording unavailable; no legal rule or deadline inferred.\\n';}return [{json:p}];"
    graph['connections'][graph['nodes'][-1]['name']]={'main':[[{'node':new['name'],'type':'main','index':0}]]};graph['nodes'].append(new)
   previous='Attach Checked Guidance '+n
 ai=http('POST Source-Exact AI Mandate Synthesis',SYNTHESIS_BACKEND+'/v1/onboarding/synthesis',"={{ JSON.stringify({contract_version:'2.0',bundle:$json.bundle,corporate_result:null,primary_research:null}) }}")
 ai['parameters']['options']['timeout']=65000;ai['onError']='continueRegularOutput'
 graph['connections'][graph['nodes'][-1]['name']]={'main':[[{'node':ai['name'],'type':'main','index':0}]]};graph['nodes'].append(ai)
 validator=code('Validate Source-Exact AI Synthesis',AI_VALIDATE.replace("$('Unified Corporate Mandate Report')","$('"+previous+"')"))
 graph['connections'][graph['nodes'][-1]['name']]={'main':[[{'node':validator['name'],'type':'main','index':0}]]};graph['nodes'].append(validator)
 final=code('Workspace Case Result',"const r=$input.first().json,s=r.ai_synthesis||{};const accepted=s.status==='completed'&&s.model_used===true&&s.execution_mode==='live'&&s.contract_version==='2.0'&&typeof s.evidence_fingerprint==='string'&&/^[a-f0-9]{64}$/.test(s.evidence_fingerprint);return [{json:{...r,message_id:"+json.dumps(message['id'])+",n8n_execution_id:String($execution.id),ai_validation_passed:accepted,assessment_mode:accepted?'validated live AI synthesis':'AI analysis unavailable',external_actions:0,financial_requests:0,registry_requests:0,documents_generated:false}}];")
 graph['connections'][graph['nodes'][-1]['name']]={'main':[[{'node':final['name'],'type':'main','index':0}]]};graph['nodes'].append(final);return graph

def documents_graph(message,payload,binding=None):
 graph=chain('INCEPT workspace — separately requested legal document drafts',[
  http('Recheck Selected Gmail Message for Documents',GMAIL+'messages/'+message['id']+'?format=full',binding=binding),
  code('Validate Selected Message and Document Intake',"const r=$input.first().json,b=r.body;function parts(p){return [...(p?.body?.data&&['text/plain','text/html'].includes(p.mimeType)?[p.body.data]:[]),...(p?.parts||[]).flatMap(parts)];}if(r.statusCode!==200||b?.id!=="+json.dumps(message['id'])+"||JSON.stringify(parts(b.payload))!=="+json.dumps(json.dumps(message['encoded_parts']))+")throw new Error('Selected message content changed; refresh before document generation');return [{json:"+json.dumps(payload,ensure_ascii=False)+"}];"),
  http('POST Optional Document Draft Generation',BACKEND+'/v1/onboarding/preview','={{ JSON.stringify($json) }}'),
  code('Validate Optional Document Drafts',"const r=$input.first().json,b=r.body;if(r.statusCode!==200||!b?.matter?.matter_id||b.documents?.length!==3||b.documents.some(d=>d.template_version!=='2.0.0'||d.legally_approved||d.ready_for_issuance)||b.proposed_actions?.length!==5||b.proposed_actions.some(a=>a.executed||a.state!=='pending_lawyer_approval'))throw new Error('Document draft response invalid');return [{json:{bundle:b,message_id:"+json.dumps(message['id'])+",n8n_execution_id:String($execution.id),documents_generated_separately:true,external_actions:0,financial_requests:0,registry_requests:0}}];")])
 return graph

def send_graph(raw,binding=None):return chain('INCEPT workspace — explicitly confirmed self-reply only',[http('Send Confirmed Gmail Reply',GMAIL+'messages/send','={{ JSON.stringify({raw:'+json.dumps(raw)+'}) }}',binding)])


def check_graph(graph,allow_send=False):
 if graph.get('active'):raise ValueError('Workspace workflow must stay inactive')
 for n in graph['nodes']:
  if n.get('retryOnFail') or n['type'].split('.')[-1] not in ('manualTrigger','code','httpRequest'):raise ValueError('Unexpected workspace node')
  if n['type'].endswith('httpRequest'):
   p=n['parameters'];url=p['url'];method=p.get('method','GET')
   if url==GMAIL+'messages/send':
    if not allow_send or method!='POST':raise ValueError('Unconfirmed send blocked')
   elif url.startswith(GMAIL):
    if method!='GET':raise ValueError('Gmail writes prohibited')
   elif url.startswith('={{'):
    if p!=inbox_graph()['nodes'][-1]['parameters']:raise ValueError('Unexpected dynamic URL')
   elif url in (BACKEND+'/v1/onboarding/assessment',BACKEND+'/v1/onboarding/preview',BACKEND+'/v1/onboarding/payment-research/verify',BACKEND+'/v1/onboarding/extract',SYNTHESIS_BACKEND+'/v1/onboarding/synthesis'):
    if method!='POST':raise ValueError('Invalid helper request')
    headers=p.get('headerParameters',{}).get('parameters',[])
    if not p.get('sendHeaders') or not any(h.get('name')=='X-LEGALFLOW-Service-Key' and h.get('value') for h in headers):raise ValueError('Authenticated FastAPI service-key binding is missing')
   elif url not in ['https://www.gesetze-im-internet.de/bgb/__'+paragraph+'.html' for paragraph in ('611','614','631','640','633','634','641','632a','320','433','434','437','439','280','281','286','323')] or method!='GET':raise ValueError('Destination not allowlisted')
 return graph


if __name__=='__main__':
 from pathlib import Path
 Path('workflows/incept_workspace_inbox.json').write_text(json.dumps(inbox_graph(),ensure_ascii=False,indent=2)+'\n')
