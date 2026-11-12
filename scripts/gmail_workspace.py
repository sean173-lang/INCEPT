"""Selected Gmail inquiries flow through authenticated n8n and FastAPI for analysis.
Documents and any confirmed reply remain separate lawyer-reviewed operations.
"""
from contextlib import closing
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from email.utils import parseaddr
from html.parser import HTMLParser
import base64,copy,hashlib,json,os,re,secrets,sqlite3,subprocess,threading
from pathlib import Path
from xml.sax.saxutils import escape
from scripts.workspace_runtime import N8NClient,WorkspaceError,ROOT
from scripts.workspace_workflow import inbox_graph,message_graph,extraction_graph,analysis_graph,documents_graph,send_graph,check_graph
from scripts.onboarding_schemas import OnboardingRequest,OnboardingBundle
from scripts.document_schemas import DocumentOptions,DocumentFirmPolicy
from scripts.onboarding_schemas import FeeInput,FirmInput

RUNTIME=ROOT/'data/gmail_workspace'
DOWNLOADS=ROOT/'downloads'
KINDS=('vollmacht','fee_agreement','advance_invoice')
DemoError=WorkspaceError

def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def textline(value):return ' '.join(str(value or '').split())
def address(value):
 if not isinstance(value,str) or '\r' in value or '\n' in value:raise DemoError('One valid email address is required.')
 parsed=parseaddr(value)[1]
 if parsed!=value.strip() or not re.fullmatch(r'[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+',parsed):raise DemoError('Use one bare email address, without CC/BCC or display-name syntax.')
 return parsed.lower()

class Store:
 def __init__(self,root=RUNTIME):
  self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700);self.path=self.root/'workspace.sqlite3'
  with closing(sqlite3.connect(self.path)) as db:db.execute('CREATE TABLE IF NOT EXISTS records(key TEXT PRIMARY KEY,value TEXT NOT NULL)');db.commit()
  self.path.chmod(0o600)
 def get(self,key,default=None):
  with closing(sqlite3.connect(self.path)) as db:r=db.execute('SELECT value FROM records WHERE key=?',(key,)).fetchone()
  return json.loads(r[0]) if r else default
 def put(self,key,value):
  with closing(sqlite3.connect(self.path)) as db:db.execute('INSERT OR REPLACE INTO records VALUES(?,?)',(key,json.dumps(value,ensure_ascii=False)));db.commit()
 def reserve(self,key,value):
  with closing(sqlite3.connect(self.path)) as db:
   db.execute('BEGIN IMMEDIATE');r=db.execute('INSERT OR IGNORE INTO records VALUES(?,?)',(key,json.dumps(value)));db.commit();return r.rowcount==1

class WorkspaceN8N(N8NClient):
 def __init__(self,runtime=RUNTIME,**kwargs):super().__init__(runtime,**kwargs)
 def binding(self):
  # Supported REST workflow metadata contains references, not OAuth tokens.
  path=self.runtime/'gmail_binding.json'
  if path.exists():return json.loads(path.read_text())
  rows=self.request('GET','/workflows',params={'limit':100}).get('data',[])
  for row in rows:
   for n in row.get('nodes',[]):
    b=n.get('credentials',{}).get('gmailOAuth2')
    if b:return b
  raise DemoError('No connected Gmail OAuth credential reference is visible in n8n workflow metadata.')
 def run_graph(self,graph,allow_send=False):
  import fcntl
  check_graph(graph,allow_send);self.runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
  with (self.runtime/'run.lock').open('a') as lock:
   try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   except BlockingIOError:raise DemoError('Another local n8n operation is running; wait before retrying.') from None
   try:
    created=self.request('POST','/workflows',json={k:graph[k] for k in ('name','nodes','connections','settings')})
    if created.get('active'):raise DemoError('Workspace operation unexpectedly active; execution blocked.')
    check_graph(created,allow_send);wid=created['id']
    env=dict(os.environ,N8N_RUNNERS_BROKER_PORT='5693',N8N_RUNNERS_MODE='internal',N8N_DIAGNOSTICS_ENABLED='false',N8N_VERSION_NOTIFICATIONS_ENABLED='false',N8N_LICENSE_AUTO_RENEW_ENABLED='false')
    try:p=self.execute(self.command(wid),env=env,capture_output=True,text=True,timeout=100,cwd=ROOT)
    except (OSError,subprocess.TimeoutExpired):raise DemoError('n8n operation timed out or failed. Outcome uncertain; sends are never retried automatically.') from None
    rows=self.request('GET','/executions',params={'workflowId':wid,'limit':1}).get('data',[])
    if not rows:raise DemoError('No actual n8n execution trace was recorded.')
    record=self.request('GET','/executions/'+rows[0]['id'],params={'includeData':'true'})
    for suffix,value in (('.json',json.dumps(record)),('.log',p.stdout+p.stderr)):
     path=self.runtime/('execution_'+record['id']+suffix);path.write_text(value);path.chmod(0o600)
    if record.get('status')!='success' or p.returncode!=0:raise DemoError('n8n execution '+record['id']+' failed; inspect its local trace. No success is claimed.')
    return record
   finally:fcntl.flock(lock,fcntl.LOCK_UN)

def results(record,name):
 rows=record['data']['resultData'].get('runData',{}).get(name,[]);return [item['json'] for row in rows for batch in row.get('data',{}).get('main',[]) for item in batch]
def gmail_result(value,operation):
 status=value.get('statusCode');body=value.get('body',{})
 if status!=200:
  reasons=[v.get('reason') for v in body.get('error',{}).get('errors',[])] if isinstance(body,dict) else []
  if status in (401,403):raise DemoError('Gmail '+operation+' HTTP '+str(status)+': authorization or required scope unavailable'+(' (insufficientPermissions)' if 'insufficientPermissions' in reasons else '')+'. No success claimed.')
  raise DemoError('Gmail '+operation+' failed with HTTP '+str(status)+'. No automatic retry.')
 return body

def headers(raw):
 result={}
 for h in raw.get('payload',{}).get('headers',[]):
  key=h['name'].lower()
  if key not in result:result[key]=h['value']
 return result
class PlainHTML(HTMLParser):
 def __init__(self):super().__init__();self.parts=[];self.hidden=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style'):self.hidden+=1
  if tag in ('p','div','br'):self.parts.append('\n')
 def handle_endtag(self,tag):
  if tag in ('script','style') and self.hidden:self.hidden-=1
 def handle_data(self,data):
  if not self.hidden:self.parts.append(data)

def decode_message(raw):
 if not re.fullmatch(r'[a-fA-F0-9]{8,64}',raw.get('id','')):raise DemoError('Invalid Gmail message ID.')
 h=headers(raw);plain=[];html=[];attachments=[];encoded=[]
 def walk(part):
  body=part.get('body',{});data=body.get('data');mime=part.get('mimeType','')
  if data and mime in ('text/plain','text/html'):
   encoded.append(data)
   try:value=base64.urlsafe_b64decode(data+'='*((-len(data))%4)).decode('utf-8',errors='strict')
   except (ValueError,UnicodeError):raise DemoError('Selected message has unsupported/lossy body encoding; manual review required.') from None
   (plain if mime=='text/plain' else html).append(value)
  if part.get('filename'):attachments.append({'filename':part['filename'],'mime_type':mime,'size':body.get('size',0),'attachment_id':body.get('attachmentId')})
  for child in part.get('parts',[]):walk(child)
 walk(raw.get('payload',{}))
 if plain:body='\n'.join(plain).replace('\r\n','\n').strip()
 else:
  parser=PlainHTML();parser.feed('\n'.join(html));body=''.join(parser.parts).strip()
 if not body or len(body)>100000:raise DemoError('Empty or oversized message body; analysis blocked.')
 return {'id':raw['id'],'thread_id':raw.get('threadId'),'from':h.get('from',''),'to':h.get('to',''),'subject':h.get('subject','(no subject)'),'date':h.get('date',''),'rfc_message_id':h.get('message-id'),'body':body,'encoded_parts':encoded,'attachments':attachments,'snippet':raw.get('snippet','')}

class GmailWorkspace:
 def __init__(self,root=RUNTIME,transport=None):self.store=Store(root);self.transport=transport or WorkspaceN8N(root);self.root=Path(root)
 def refresh(self,query=''):
  if len(query)>200:raise DemoError('Search is limited to 200 characters.')
  record=self.transport.run_graph(inbox_graph('in:inbox -in:spam -in:trash '+query,self.transport.binding()))
  profile=gmail_result(results(record,'Read Gmail Profile')[0],'profile');account=address(profile.get('emailAddress',''));self.store.put('account',account)
  listed=gmail_result(results(record,'List Recent Gmail IDs')[0],'list');wanted={v['id'] for v in listed.get('messages',[])};rows=[]
  for r in results(record,'Read Message Metadata'):
   raw=gmail_result(r,'metadata')
   if raw.get('id') not in wanted:raise DemoError('Unexpected metadata identity.')
   h=headers(raw);row={'id':raw['id'],'from':h.get('from',''),'subject':h.get('subject','(no subject)'),'date':h.get('date',''),'snippet':raw.get('snippet','')};self.store.put('metadata:'+raw['id'],row);rows.append(row)
  self.store.put('inbox',rows);return rows,record['id'],account
 def select(self,mid):
  if not self.store.get('metadata:'+str(mid)):raise DemoError('Select a message from the refreshed inbox before reading its body.')
  record=self.transport.run_graph(message_graph(mid,self.transport.binding()));message=decode_message(gmail_result(results(record,'Read Selected Gmail Message')[0],'read'));self.store.put('message:'+mid,message)
  return message,record['id'],self.prefill(message)
 def prefill(self,message):
  profile={'name':'','email':'','address':'','counterparty':'','scope':'','representative_name':'','representative_role':'','authority_reference':'','authority_checked':False,'firm_name':'','firm_address':'','lawyer_name':''}
  profile.setdefault('extraction_note','Selected message will be extracted and grounded to its original text before analysis.')
  return profile
 def payload(self,message,profile,authorized):
  if authorized is not True:raise DemoError('External AI processing was not authorized for this inquiry.')
  if len(message['body'])>6000:raise DemoError('Selected message exceeds the source-grounded analysis limit; no content was truncated.')
  client_name=textline(profile.get('name')) or None
  client_type='unknown'
  governing_law='unknown'
  firm=None
  if all(textline(profile.get(k)) for k in ('firm_name','firm_address','lawyer_name')):
   firm=FirmInput(name=textline(profile['firm_name']),address=textline(profile['firm_address']),email=None,
                  jurisdiction='unknown',client_type='company',lawyer_name=textline(profile['lawyer_name'])).model_dump(mode='json')
  fees=None
  if textline(profile.get('hourly_rate')):
   fees=FeeInput(net_hourly_rate=textline(profile['hourly_rate']),
      proposed_advance_hours=textline(profile.get('advance_hours')) or None,
      vat_mode=profile.get('vat_mode') if profile.get('vat_mode') in ('unknown','taxable','exempt') else 'unknown',
      vat_percent=textline(profile.get('vat_percent')) or None,vat_basis=textline(profile.get('vat_basis')) or None)
  options=None
  policy=None
  if textline(profile.get('firm_policy_id')) and textline(profile.get('hourly_rate')):
   increment=profile.get('billing_increment_minutes')
   policy=DocumentFirmPolicy(policy_id=textline(profile['firm_policy_id']),net_hourly_rate=textline(profile['hourly_rate']),
      billing_method=profile.get('billing_method') if profile.get('billing_method') in ('unknown','actual_minutes','specified_increment') else 'unknown',
      billing_increment_minutes=int(increment) if increment else None,
      time_recording=textline(profile.get('time_recording')) or None,expenses_terms=textline(profile.get('expenses_terms')) or None,
      payment_terms=textline(profile.get('payment_terms')) or None,other_professionals_terms=textline(profile.get('other_professionals_terms')) or None,
      tax_identifier=textline(profile.get('tax_identifier')) or None,payment_instructions=textline(profile.get('payment_instructions')) or None,
      vat_configuration_confirmed=profile.get('vat_configuration_confirmed') is True)
  rep=None
  if textline(profile.get('representative_name')) and textline(profile.get('representative_role')):
   rep={'name':textline(profile['representative_name']),'role':textline(profile['representative_role']),
        'authority_status':'evidence_checked' if profile.get('authority_checked') else 'asserted',
        'evidence_reference':textline(profile.get('authority_reference')) or None}
  if firm or policy or rep or textline(profile.get('place')):
   options=DocumentOptions(representative=rep,place=textline(profile.get('place')) or None,
      recipient_business_status='unknown',engagement_law='unknown',firm_policy=policy).model_dump(mode='json')
  body={'synthetic_data':False,'idempotency_key':'gmail-'+message['id']+'-'+digest({'message_id':message['id'],'body':message['body'],'profile':profile})[:24],
    'client':{'name':client_name,'address':textline(profile.get('address')) or None,'email':textline(profile.get('email')) or parseaddr(message.get('from',''))[1] or None,'client_type':client_type,
      'jurisdiction':'unknown',
      'registration_number':textline(profile.get('registration_number')) or None,'register_court':textline(profile.get('register_court')) or None},
    'firm':firm,'matter':{'title':textline(message['subject'])[:190] or 'Anfrage','summary':message['body'],
      'requested_scope':textline(profile.get('scope')) or message['body'][:900],
      'opposing_parties':[textline(profile['counterparty'])] if textline(profile.get('counterparty')) else [],
      'governing_law':governing_law,'claimed_deadline':None,'deadline_source':None},
    'fees':fees.model_dump(mode='json') if fees else None,'document_options':options,'draft_date':None}
  return OnboardingRequest.model_validate(body).model_dump(mode='json')
 def analyze(self,mid,profile,authorized=False,reanalyze=False):
  from scripts.mandate_report import VERSION
  message=self.store.get('message:'+str(mid))
  if not message:raise DemoError('Select and read an email first.')
  if authorized is not True:raise DemoError('External AI processing was not authorized for this inquiry.')
  if len(message['body'])>6000:raise DemoError('Selected message exceeds the source-grounded analysis limit; no content was truncated.')
  extraction_record=self.transport.run_graph(extraction_graph(message,self.transport.binding()))
  extraction_rows=results(extraction_record,'Validate Selected Inquiry Extraction')
  if len(extraction_rows)!=1 or extraction_rows[0].get('message_id')!=mid:
   raise DemoError('Selected-message extraction did not return a validated result. n8n execution '+str(extraction_record.get('id','unknown'))+' diagnostics were preserved.')
  extraction=extraction_rows[0]['extraction']
  extracted_name=extraction.get('client_name')
  profile={**profile,'name':textline(profile.get('name')) or (extracted_name.get('text') if extracted_name else ''),
           'email':textline(profile.get('email')) or parseaddr(message.get('from',''))[1],
           'counterparty':textline(profile.get('counterparty')) or (extraction.get('counterparty') or {}).get('text',''),
           'scope':textline(profile.get('scope')) or (extraction.get('requested_assistance') or {}).get('text',''),
           'extraction_note':'Live '+str(extraction_rows[0].get('model') or 'OpenAI')+' extraction; names and facts are validated against exact source excerpts.'}
  payload=self.payload(message,profile,authorized);case_id='case-'+mid;revision=digest(payload);previous=self.store.get(case_id)
  from scripts.ai_synthesis import AIConfig
  analysis_version=VERSION+':source-exact-2.0'
  cache_key=digest({'message_id':mid,'source_sha256':hashlib.sha256(message['body'].encode()).hexdigest(),
                    'payload':payload,'analysis_version':analysis_version,'model':AIConfig.from_environment().model,
                    'validation_state':'live_source_exact_v2_required'})
  if previous and not reanalyze:
   same_source=previous.get('source_body_sha256')==hashlib.sha256(message['body'].encode()).hexdigest() if previous.get('source_body_sha256') else previous['payload']['matter']['summary']==payload['matter']['summary']
   prior_ai=previous.get('ai_synthesis') or {}
   prior_ai_accepted=(prior_ai.get('status')=='completed' and prior_ai.get('model_used') is True and
                      prior_ai.get('execution_mode')=='live' and prior_ai.get('contract_version')=='2.0')
   if same_source and previous['profile']==profile and previous.get('analysis_cache_key')==cache_key and previous.get('report_version')==VERSION and prior_ai_accepted:return {**previous,'reused':True}
  if previous:
   previous_execution=str(previous.get('execution_id') or revision[:16])
   history_key='case-history:'+str(mid)+':'+previous_execution
   if not self.store.get(history_key):self.store.put(history_key,previous)
  record=self.transport.run_graph(analysis_graph(message,payload,self.transport.binding()));values=results(record,'Workspace Case Result')
  if len(values)!=1:raise DemoError('n8n did not return a case result.')
  result=values[0];bundle=OnboardingBundle.model_validate(result['bundle'])
  if bundle.client.name!=payload['client']['name'] or bundle.matter.summary!=payload['matter']['summary'] or bundle.matter.opposing_parties!=payload['matter']['opposing_parties']:raise DemoError('Backend result does not match this selected email/intake.')
  if any(d.ready_for_issuance or d.legally_approved for d in bundle.documents) or any(a.executed for a in bundle.proposed_actions):raise DemoError('Approval safeguard violation.')
  case={'id':case_id,'message_id':mid,'source_body_sha256':hashlib.sha256(message['body'].encode()).hexdigest(),'revision':revision,'analysis_cache_key':cache_key,'profile':profile,'payload':payload,'bundle':bundle.model_dump(mode='json'),'execution_id':record['id'],'extraction_execution_id':extraction_record['id'],'workflow_id':record['workflowId'],'legal_research':result['legal_research'],'reused':False,'documents_generated':False}
  case['bundle']['assessment']['content_markdown']+='\n\n*Quelle: ausgewählte Gmail-Nachricht '+mid+'. Angaben aus der Nachricht sind Parteivortrag und nicht unabhängig geprüft.*\n'
  from scripts.mandate_report import render_ai
  case['assessment_audit_original']=case['bundle']['assessment']['content_markdown']
  status=result.get('ai_synthesis') or {'status':'unavailable','reason':'ai_synthesis_status_missing','model_used':False,'execution_mode':'disabled','live_request':False}
  accepted=(result.get('ai_validation_passed') is True and status.get('status')=='completed' and status.get('model_used') is True and status.get('execution_mode')=='live' and status.get('contract_version')=='2.0' and re.fullmatch(r'[a-f0-9]{64}',str(status.get('evidence_fingerprint',''))) is not None)
  if accepted:
   try:
    case['ai_analysis']=result['ai_analysis'];case['ai_synthesis']=status;case['ai_validation_passed']=True
    report,audit=render_ai(case,message,case['ai_analysis'],status)
    case['assessment_mode']='live AI synthesis accepted' if not status.get('cache_hit') else 'validated cached live AI synthesis accepted'
   except (KeyError,TypeError,ValueError):
    accepted=False;status={**status,'status':'unavailable','model_used':False,'reason':'workspace_ai_report_validation_failed'}
  if not accepted:
   reason=status.get('reason') or 'ai_synthesis_not_accepted'
   if not re.fullmatch(r'[a-z0-9_]{1,100}',str(reason)):reason='ai_synthesis_not_accepted'
   diagnostic={'message_id':mid,'execution_id':record['id'],'workflow_id':record['workflowId'],'reason':reason,
               'model':status.get('model'),'validation_diagnostic':status.get('validation_diagnostic'),
               'validation_fields':status.get('validation_fields',[]),
               'validation_error_type':status.get('validation_error_type'),
               'live_request':status.get('live_request'),'source_sha256':hashlib.sha256(message['body'].encode()).hexdigest(),
               'at':datetime.now(timezone.utc).isoformat()}
   self.store.put('failed-analysis:'+mid+':'+record['id'],diagnostic)
   fields=status.get('validation_fields',[])
   detail='; validator: '+str(status.get('validation_error_type')) if status.get('validation_error_type') else ''
   if status.get('validation_error_code'):detail+='; validation code: '+str(status.get('validation_error_code'))
   if status.get('validation_error_message'):detail+='; validation detail: '+str(status.get('validation_error_message'))
   if isinstance(fields,list) and fields:detail+='; failed fields: '+', '.join(str(v) for v in fields)
   raise DemoError('AI analysis could not be completed; source-exact validation did not pass ('+reason+detail+'). n8n execution '+str(record['id'])+' diagnostics were preserved.')
  case['bundle']['assessment']['content_markdown']=report
  case['assessment_presentation_evidence']=audit;case['report_version']=VERSION
  case['analysis_cache_key']=cache_key;self.store.put(case_id,case);return case
 def generate_documents(self,case_id):
  case=self.case(case_id)
  if case.get('bundle',{}).get('documents'):
   return {**case,'documents_reused':True}
  message=self.store.get('message:'+case['message_id'])
  if not message:raise DemoError('Original selected message is unavailable; document generation is blocked.')
  payload=dict(case['payload']);payload['draft_date']=datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat()
  if not payload.get('firm') or not payload.get('fees') or not payload.get('document_options') or not payload['document_options'].get('firm_policy'):
   raise DemoError('Document drafting requires current firm details, a supplied fee policy and an advance calculation. No defaults were inserted.')
  OnboardingRequest.model_validate(payload)
  record=self.transport.run_graph(documents_graph(message,payload,self.transport.binding()))
  values=results(record,'Validate Optional Document Drafts')
  if len(values)!=1:raise DemoError('n8n did not return separately generated document drafts.')
  result=values[0];bundle=OnboardingBundle.model_validate(result['bundle'])
  if (bundle.client.name!=case['bundle']['client']['name'] or bundle.matter.summary!=case['bundle']['matter']['summary'] or
      bundle.matter.opposing_parties!=case['bundle']['matter']['opposing_parties'] or
      bundle.client.client_id!=case['bundle']['client']['client_id'] or bundle.matter.matter_id!=case['bundle']['matter']['matter_id']):
   raise DemoError('Document generation returned a different client, matter or selected email.')
  if len(bundle.documents)!=3 or any(d.ready_for_issuance or d.legally_approved for d in bundle.documents) or any(a.executed for a in bundle.proposed_actions):
   raise DemoError('Document approval safeguard violation.')
  case['bundle']['documents']=[d.model_dump(mode='json') for d in bundle.documents]
  case['documents_generated']=True;case['document_execution_id']=record['id'];case['document_workflow_id']=record['workflowId']
  self.store.put(case['id'],case);return case
 def case(self,case_id):
  case=self.store.get(str(case_id))
  if not case:raise DemoError('No current mandate case. Analyze a selected email first.')
  return case
 def eligible(self,case,kind):
  if not case.get('bundle',{}).get('documents'):return False,'Optional legal document drafts have not been generated.'
  d=next(d for d in case['bundle']['documents'] if d['kind']==kind);p=case['profile']
  if kind=='advance_invoice':return False,'Advance requests remain unissued; attachment is blocked in this pilot.'
  if d['completeness_status']!='DRAFT_COMPLETE_FOR_LAWYER_REVIEW' or d['missing_information']:return False,'Document is blocked: '+d['completeness_status']
  if not all(textline(p.get(k)) for k in ('name','address','firm_name','firm_address','lawyer_name')):return False,'Client/firm details remain missing.'
  return True,'Eligible for explicit lawyer transmission review; not automatically released.'
 def release(self,case_id,kinds,reviewer,confirmed):
  case=self.case(case_id)
  if not kinds:raise DemoError('Select at least one eligible complete draft; no release recorded.')
  if not confirmed or len(textline(reviewer))<3:raise DemoError('Named lawyer review and explicit draft-release confirmation are required.')
  for kind in kinds:
   if kind not in KINDS:raise DemoError('Unknown document selection.')
   okay,reason=self.eligible(case,kind)
   if not okay:raise DemoError(reason)
  for kind in kinds:
   d=next(d for d in case['bundle']['documents'] if d['kind']==kind)
   self.store.put('release:'+case_id+':'+kind,{'revision':case['revision'],'document_sha256':digest(d),'reviewer':textline(reviewer),'confirmed_at':datetime.now(timezone.utc).isoformat(),'scope':'transmission of this unissued draft only'})
  return list(kinds)
 def released(self,case):
  result=[]
  for d in case['bundle']['documents']:
   release=self.store.get('release:'+case['id']+':'+d['kind'])
   if release and release['revision']==case['revision'] and release['document_sha256']==digest(d) and self.eligible(case,d['kind'])[0]:result.append(d['kind'])
  return result
 def document(self,case_id,kind):
  from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
  from reportlab.lib.styles import getSampleStyleSheet
  from reportlab.pdfbase import pdfmetrics
  from reportlab.pdfbase.ttfonts import TTFont
  import reportlab
  case=self.case(case_id)
  if kind not in KINDS:raise DemoError('Unknown document kind.')
  if not case.get('bundle',{}).get('documents'):raise DemoError('Generate the optional legal document drafts before downloading a PDF.')
  doc=next(d for d in case['bundle']['documents'] if d['kind']==kind)
  folder=DOWNLOADS/case_id/case['revision'];folder.mkdir(parents=True,exist_ok=True,mode=0o700);path=folder/(kind+'_DRAFT.pdf')
  if not path.exists():
   if 'INCEPTVera' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('INCEPTVera',str(Path(reportlab.__file__).parent/'fonts/Vera.ttf')))
   style=getSampleStyleSheet()['Normal'];style.fontName='INCEPTVera';style.fontSize=9;style.leading=13
   paragraphs=[]
   for block in doc['content_markdown'].split('\n\n'):
    paragraphs.extend([Paragraph(escape(block).replace('\n','<br/>'),style),Spacer(1,9)])
   SimpleDocTemplate(str(path)).build(paragraphs);path.chmod(0o600)
  return str(path)
 def preview(self,case_id,recipient,subject,body,kinds):
  case=self.case(case_id);account=self.store.get('account')
  if not account:raise DemoError('Refresh Gmail to establish the connected account.')
  recipient=address(recipient)
  if recipient!=account:raise DemoError('Controlled pilot: only a reply to the connected Gmail account itself is allowed. External recipients are blocked.')
  if not textline(subject) or len(subject)>200 or any(c in subject for c in '\r\n'):raise DemoError('A single-line subject of at most 200 characters is required.')
  if not body.strip() or len(body)>15000:raise DemoError('Supply an email body, at most 15,000 characters.')
  released=self.released(case)
  if any(k not in released for k in kinds):raise DemoError('Only current complete drafts explicitly released by a lawyer may be attached. Blocked or stale drafts cannot be sent.')
  attachments=[]
  for kind in kinds:
   path=self.document(case_id,kind);attachments.append({'kind':kind,'path':path,'filename':Path(path).name,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()})
  proof={'case_id':case_id,'revision':case['revision'],'recipient':recipient,'subject':subject,'body':body,'attachments':attachments,'message_id':case['message_id']}
  token=secrets.token_urlsafe(24);proof['fingerprint']=digest(proof);self.store.put('preview:'+token,proof)
  return token,proof
 def send(self,token,case_id,recipient,subject,body,kinds,confirmed=False):
  if confirmed is not True:raise DemoError('Final explicit confirmation is required; no email sent.')
  proof=self.store.get('preview:'+str(token));case=self.case(case_id)
  if not proof or proof['case_id']!=case_id or proof['revision']!=case['revision'] or (recipient.lower(),subject,body)!=(proof['recipient'],proof['subject'],proof['body']) or sorted(kinds)!=sorted(a['kind'] for a in proof['attachments']):raise DemoError('Composer/case changed after preview. Preview again; nothing sent.')
  if address(recipient)!=self.store.get('account'):raise DemoError('External destination prohibited.')
  for attachment in proof['attachments']:
   if attachment['kind'] not in self.released(case) or hashlib.sha256(Path(attachment['path']).read_bytes()).hexdigest()!=attachment['sha256']:raise DemoError('Attachment release or content changed; no send.')
  key='send:'+proof['fingerprint'];prior=self.store.get(key)
  if prior:
   if prior['state']=='sent':return {**prior,'duplicate_prevented':True}
   raise DemoError('A prior send attempt is failed or uncertain. Automatic retry is blocked; inspect Gmail/n8n before another authorization.')
  if not self.store.reserve(key,{'state':'reserved_no_retry'}):raise DemoError('Duplicate concurrent send blocked.')
  message=self.store.get('message:'+case['message_id']);mime=EmailMessage();mime['From']=self.store.get('account');mime['To']=recipient;mime['Subject']=subject
  if message.get('rfc_message_id') and not any(c in message['rfc_message_id'] for c in '\r\n'):
   mime['In-Reply-To']=message['rfc_message_id'];mime['References']=message['rfc_message_id']
  mime.set_content(body)
  for a in proof['attachments']:mime.add_attachment(Path(a['path']).read_bytes(),maintype='application',subtype='pdf',filename=a['filename'])
  payload={'raw':base64.urlsafe_b64encode(mime.as_bytes()).decode()}
  if message.get('thread_id'):payload['threadId']=message['thread_id']
  try:
   # Build body with the thread ID as well as MIME threading headers.
   graph=send_graph(payload['raw'],self.transport.binding());graph['nodes'][-1]['parameters']['jsonBody']='={{ JSON.stringify('+json.dumps(payload)+') }}'
   record=self.transport.run_graph(graph,allow_send=True);sent=gmail_result(results(record,'Send Confirmed Gmail Reply')[0],'send')
   if not re.fullmatch(r'[a-fA-F0-9]{8,64}',sent.get('id','')):raise DemoError('Gmail send result lacks a genuine message ID; outcome uncertain.')
   result={'state':'sent','gmail_message_id':sent['id'],'thread_id':sent.get('threadId'),'execution_id':record['id'],'recipient':recipient,'attachments':[a['filename'] for a in proof['attachments']],'confirmed_at':datetime.now(timezone.utc).isoformat()};self.store.put(key,result);return result
  except Exception:
   self.store.put(key,{'state':'failed_or_uncertain_no_retry'});raise
