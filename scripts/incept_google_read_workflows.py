"""Credential-free read-only exports. n8n binds existing OAuth metadata at deployment."""
import copy
import json
from pathlib import Path
import uuid

OPERATIONS={
 'gmail':{'credential_type':'gmailOAuth2','url':'https://gmail.googleapis.com/gmail/v1/users/me/labels',
          'query':{'fields':'labels(type)'},'array':'labels','name':'Gmail Labels List','count_scope':'all_labels'},
 'calendar':{'credential_type':'googleCalendarOAuth2Api','url':'https://www.googleapis.com/calendar/v3/users/me/calendarList',
             'query':{'maxResults':'100','fields':'kind,nextPageToken,items(accessRole,primary)'},'array':'items','name':'Google Calendar List','count_scope':'first_page_up_to_100'}
}


def summary_code(kind):
    operation=OPERATIONS[kind]
    return r'''
const response=$input.first().json;
if(response.statusCode!==200) throw new Error('google_read_failed_http_'+(Number.isInteger(response.statusCode)?response.statusCode:'unknown'));
const body=response.body;
if(!body || typeof body!=='object') throw new Error('unsupported_google_response');
''' + (r"""
if(!Array.isArray(body.labels) || body.labels.some(x=>!x || !['system','user'].includes(x.type))) throw new Error('unsupported_labels_response');
const count=body.labels.length;
""" if kind=='gmail' else r"""
if(body.kind!=='calendar#calendarList' || (body.items!==undefined && !Array.isArray(body.items))) throw new Error('unsupported_calendar_response');
const items=body.items||[];
if(items.some(x=>!x || typeof x.accessRole!=='string')) throw new Error('unsupported_calendar_metadata');
const count=items.length;
""") + "return [{json:{product:'INCEPT',integration:"+json.dumps(kind)+",status:'passed',http_status:200,n8n_execution_id:String($execution.id),response_count:count,count_scope:"+json.dumps(operation['count_scope'])+r''',
 has_more:typeof body.nextPageToken==='string' && body.nextPageToken.length>0,
 read_only:true,response_mocked:false,email_bodies_read:0,emails_sent:0,spreadsheet_writes:0,calendar_events_created:0,
 personal_content_exported:false,credential_secrets_exported:false,completed_at:new Date().toISOString()}}];
'''


def build_workflow(kind):
    op=OPERATIONS[kind];names=['Manual Read Test',op['name'],'Sanitized Proof']
    def node(name,type_,version,parameters,x,**kw):
        return {'id':uuid.uuid5(uuid.NAMESPACE_URL,'incept-'+kind+':'+name).hex,'name':name,'type':'n8n-nodes-base.'+type_,
                'typeVersion':version,'position':[x,0],'parameters':parameters,**kw}
    nodes=[node(names[0],'manualTrigger',1,{},0),
           node(names[1],'httpRequest',4.5,{'method':'GET','url':op['url'],'authentication':'predefinedCredentialType','nodeCredentialType':op['credential_type'],
                'sendQuery':True,'queryParameters':{'parameters':[{'name':k,'value':v} for k,v in op['query'].items()]},
                'options':{'timeout':15000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}},250,retryOnFail=False),
           node(names[2],'code',2,{'mode':'runOnceForAllItems','jsCode':summary_code(kind)},500)]
    return {'name':'INCEPT — Read-Only '+op['name']+' Test','active':False,'nodes':nodes,
            'connections':{a:{'main':[[{'node':b,'type':'main','index':0}]]} for a,b in zip(names,names[1:])},
            'settings':{'executionOrder':'v1','saveDataSuccessExecution':'all','saveDataErrorExecution':'all','saveManualExecutions':True}}


def bind_credential(kind,credential):
    op=OPERATIONS[kind]
    if credential.get('type')!=op['credential_type'] or not credential.get('id') or not credential.get('name'):
        raise ValueError('An existing compatible n8n credential is required; never substitute Sheets credentials.')
    workflow=copy.deepcopy(build_workflow(kind))
    workflow['nodes'][1]['credentials']={op['credential_type']:{'id':credential['id'],'name':credential['name']}}
    return workflow


if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    for kind in OPERATIONS:
        (root/'workflows'/('incept_'+kind+'_read_test.json')).write_text(json.dumps(build_workflow(kind),indent=2)+'\n')
