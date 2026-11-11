"""Separate, read-only Google Sheets test using n8n-owned OAuth; no token access."""
import copy
import json
from pathlib import Path
import uuid

CHOOSE_DOCUMENT=r'''
const response=$input.first().json;
if(response.statusCode!==200 || !response.body || !Array.isArray(response.body.files)) throw new Error('spreadsheet_metadata_read_failed');
if(response.body.nextPageToken) throw new Error('metadata_selection_incomplete: more than one page; no automatic selection');
const files=response.body.files.filter(f=>Array.isArray(f.owners) && f.owners.some(o=>o.emailAddress==='ironhackproject3@gmail.com'));
if(files.length!==1) return [{json:{selection_status:files.length?'ambiguous':'not_found',candidates:files.map(f=>({id:f.id,name:f.name})),read_permitted:false}}];
return [{json:{selection_status:'unique',spreadsheet_id:files[0].id,spreadsheet_name:files[0].name,read_permitted:true}}];
'''
CHOOSE_TAB=r'''
const response=$input.first().json;
if(response.statusCode!==200 || !Array.isArray(response.body?.sheets)) throw new Error('worksheet_metadata_read_failed');
const tabs=response.body.sheets.filter(s=>s.properties?.sheetType==='GRID').map(s=>s.properties);
const document=$('Choose Spreadsheet').first().json;
if(tabs.length!==1) return [{json:{...document,selection_status:'ambiguous_tabs',read_permitted:false,tab_candidates:tabs.map(t=>({id:t.sheetId,title:t.title}))}}];
return [{json:{...document,tab_id:tabs[0].sheetId,tab_title:tabs[0].title,read_permitted:true}}];
'''
SUMMARY=r'''
const rows=$input.all().map(i=>i.json);
const meaningful=rows.filter(r=>Object.entries(r).some(([k,v])=>k!=='row_number' && v!==null && v!==''));
if(meaningful.length===0) throw new Error('no_real_rows_returned');
const selected=$('Choose Worksheet').first().json;
return [{json:{product:'INCEPT',integration:'Google Sheets',n8n_execution_id:String($execution.id),
 spreadsheet_id:selected.spreadsheet_id,spreadsheet_name:selected.spreadsheet_name,tab_id:selected.tab_id,tab_title:selected.tab_title,
 status:'passed',rows_returned:meaningful.length,column_count:new Set(meaningful.flatMap(r=>Object.keys(r).filter(k=>k!=='row_number'))).size,
 range:'A1:Z101',read_only:true,spreadsheet_writes:0,emails_sent:0,calendar_events_created:0,
 response_mocked:false,credential_secrets_exported:false,completed_at:new Date().toISOString()}}];
'''
STOP=r'''
return [{json:{product:'INCEPT',status:'selection_requires_review',...$input.first().json,
 n8n_execution_id:String($execution.id),spreadsheet_writes:0}}];
'''


def build_workflow():
    nodes=[]
    def add(name,kind,version,params,x,**kw):
        nodes.append({'id':uuid.uuid5(uuid.NAMESPACE_URL,'incept-sheets:'+name).hex,'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[x,0],'parameters':params,**kw})
    def code(name,body,x):add(name,'code',2,{'mode':'runOnceForAllItems','jsCode':body},x)
    def gate(name,x):add(name,'if',2.2,{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},'conditions':[{'id':uuid.uuid5(uuid.NAMESPACE_URL,name).hex,'leftValue':'={{ $json.read_permitted === true }}','rightValue':True,'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},x)
    def http(name,url,query,x):
        add(name,'httpRequest',4.5,{'method':'GET','url':url,'authentication':'predefinedCredentialType','nodeCredentialType':'googleSheetsOAuth2Api',
            'sendQuery':True,'queryParameters':{'parameters':[{'name':k,'value':v} for k,v in query.items()]},
            'options':{'timeout':15000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}},x,retryOnFail=False)
    add('Manual Read Test','manualTrigger',1,{},0)
    http('Discover Spreadsheets','https://www.googleapis.com/drive/v3/files',{'q':"mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false and 'me' in owners",'fields':'nextPageToken,files(id,name,owners(emailAddress))','pageSize':'100'},200)
    code('Choose Spreadsheet',CHOOSE_DOCUMENT,400);gate('Unique Spreadsheet?',600)
    http('Discover Worksheets',"={{ 'https://sheets.googleapis.com/v4/spreadsheets/' + encodeURIComponent($json.spreadsheet_id) }}",{'fields':'sheets.properties'},800)
    code('Choose Worksheet',CHOOSE_TAB,1000);gate('Unique Worksheet?',1200)
    add('Get Real Rows','googleSheets',4.7,{'authentication':'oAuth2','resource':'sheet','operation':'read',
        'documentId':{'__rl':True,'mode':'id','value':"={{ $json.spreadsheet_id }}"},
        'sheetName':{'__rl':True,'mode':'id','value':"={{ String($json.tab_id) }}"},
        'options':{'dataLocationOnSheet':{'values':{'rangeDefinition':'specifyRangeA1','range':'A1:Z101'}},'returnFirstMatch':False}},1400,retryOnFail=False)
    code('Sanitized Read Proof',SUMMARY,1600);code('Selection Needs Review',STOP,800)
    edges={}
    def connect(a,b,index=0):
        out=edges.setdefault(a,{'main':[]})['main']
        while len(out)<=index:out.append([])
        out[index].append({'node':b,'type':'main','index':0})
    names=['Manual Read Test','Discover Spreadsheets','Choose Spreadsheet','Unique Spreadsheet?','Discover Worksheets','Choose Worksheet','Unique Worksheet?','Get Real Rows','Sanitized Read Proof']
    for a,b in zip(names,names[1:]):connect(a,b)
    for name in ('Unique Spreadsheet?','Unique Worksheet?'):connect(name,'Selection Needs Review',1)
    return {'name':'INCEPT — Temporary Google Sheets Read-Only Test','active':False,'nodes':nodes,'connections':edges,
            'settings':{'executionOrder':'v1','saveDataSuccessExecution':'all','saveDataErrorExecution':'all','saveManualExecutions':True}}


def bind_credential(workflow,credential):
    if credential.get('type')!='googleSheetsOAuth2Api' or not credential.get('id') or not credential.get('name'):
        raise ValueError('Existing Google Sheets OAuth credential metadata required')
    bound=copy.deepcopy(workflow)
    for node in bound['nodes']:
        if node['type'] in ('n8n-nodes-base.httpRequest','n8n-nodes-base.googleSheets'):
            node['credentials']={'googleSheetsOAuth2Api':{'id':credential['id'],'name':credential['name']}}
    return bound


if __name__=='__main__':
    root=Path(__file__).resolve().parent.parent
    (root/'workflows/incept_google_sheets_read_test.json').write_text(json.dumps(build_workflow(),indent=2)+'\n')
