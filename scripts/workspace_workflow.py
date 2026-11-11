"""Bounded n8n graphs for Gmail workspace; no credential values or model calls."""
import copy,json,uuid
from scripts.demo_workflow import BACKEND
from scripts.incept_prose_workflow import build_workflow as prose_workflow

GMAIL='https://gmail.googleapis.com/gmail/v1/users/me/'

def node(name,kind,params,version=2):
 return {'id':uuid.uuid5(uuid.NAMESPACE_URL,'incept-workspace:'+name).hex,'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[0,0],'parameters':params,'retryOnFail':False}
def http(name,url,body=None,binding=None):
 p={'method':'POST' if body else 'GET','url':url,'options':{'timeout':20000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}}
 if body:p.update(sendBody=True,specifyBody='json',jsonBody=body)
 n=node(name,'httpRequest',p,4.5)
 if url.startswith(GMAIL) or url.startswith('={{'):
  p.update(authentication='predefinedCredentialType',nodeCredentialType='gmailOAuth2')
  if binding:n['credentials']={'gmailOAuth2':binding}
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

def analysis_graph(message,payload,binding=None):
 graph=chain('INCEPT workspace — selected-message mandate processing',[
  http('Recheck Selected Gmail Message',GMAIL+'messages/'+message['id']+'?format=full',binding=binding),
  code('Validate Selected Message and Intake',"const r=$input.first().json,b=r.body;function parts(p){return [...(p?.body?.data&&['text/plain','text/html'].includes(p.mimeType)?[p.body.data]:[]),...(p?.parts||[]).flatMap(parts)];}if(r.statusCode!==200||b?.id!=="+json.dumps(message['id'])+"||JSON.stringify(parts(b.payload))!=="+json.dumps(json.dumps(message['encoded_parts']))+")throw new Error('Selected message content changed; refresh before analysis');return [{json:"+json.dumps(payload,ensure_ascii=False)+"}];"),
  http('POST Selected Intake Preview',BACKEND+'/v1/onboarding/preview','={{ JSON.stringify($json) }}'),
  code('Validate Selected Bundle',"const r=$input.first().json,b=r.body;if(r.statusCode!==200||!b?.matter?.matter_id||b.documents?.length!==3||b.documents.some(d=>d.template_version!=='2.0.0'||d.legally_approved||d.ready_for_issuance)||b.proposed_actions?.length!==5||b.proposed_actions.some(a=>a.executed||a.state!=='pending_lawyer_approval'))throw new Error('Onboarding response invalid');return [{json:{bundle:b,legal_research:[]}}];")])
 scope=' '.join([payload['matter']['summary'],payload['matter']['title'],payload['matter']['requested_scope']]).lower()
 relevant=payload['matter']['governing_law']=='Germany' and any(t in scope for t in ('rechnung','zahlung','payment','invoice','forderung'))
 if relevant:
  templates={n['name']:n for n in prose_workflow()['nodes']};previous='Validate Selected Bundle'
  for n in ('611','320','641'):
   for label in ('Retrieve Official BGB ','Prepare Source Check ','Verify Official Wording ','Attach Checked Guidance '):
    new=copy.deepcopy(templates[label+n]);p=new['parameters']
    if label=='Verify Official Wording ':p['url']=BACKEND+'/v1/onboarding/payment-research/verify'
    if label=='Attach Checked Guidance ':
     p['jsCode']="const r=$input.first().json,e=r.body,p=JSON.parse(JSON.stringify($('"+previous+"').first().json));if(r.statusCode===200&&e?.status==='wording_verified'){p.legal_research.push(e);p.bundle.assessment.sources.push(e.source);p.bundle.assessment.guidance.push({description:e.source.content,status:'reference_guidance',source_ids:[e.source.source_id]});p.bundle.assessment.content_markdown+='\\n## Checked payment-dispute guidance — not a case finding\\n'+e.source.content+'\\n'+e.source.url+'; retrieved '+e.retrieved_at+'\\n'+e.limitation+'\\n';}else{p.bundle.assessment.missing_information.push('Official payment-source check unavailable; lawyer research required.');p.bundle.assessment.content_markdown+='\\nOfficial legal source unavailable; no supported rule or deadline inferred.\\n';}return [{json:p}];"
    graph['connections'][graph['nodes'][-1]['name']]={'main':[[{'node':new['name'],'type':'main','index':0}]]};graph['nodes'].append(new)
   previous='Attach Checked Guidance '+n
 final=code('Workspace Case Result',"return [{json:{...$input.first().json,message_id:"+json.dumps(message['id'])+",n8n_execution_id:String($execution.id),assessment_mode:'deterministic; no new paid AI request',external_actions:0,financial_requests:0,registry_requests:0}}];")
 graph['connections'][graph['nodes'][-1]['name']]={'main':[[{'node':final['name'],'type':'main','index':0}]]};graph['nodes'].append(final);return graph

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
   elif url in (BACKEND+'/v1/onboarding/preview',BACKEND+'/v1/onboarding/payment-research/verify'):
    if method!='POST':raise ValueError('Invalid helper request')
   elif url not in ['https://www.gesetze-im-internet.de/bgb/__'+n+'.html' for n in ('611','320','641')] or method!='GET':raise ValueError('Destination not allowlisted')
 return graph


if __name__=='__main__':
 from pathlib import Path
 Path('workflows/incept_workspace_inbox.json').write_text(json.dumps(inbox_graph(),ensure_ascii=False,indent=2)+'\n')
