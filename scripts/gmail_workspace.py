"""Selected-message workspace; existing n8n/FastAPI do the actual processing.

Local synthetic-matter pilot only. Gmail is real; no paid model request is made.
Release records authorize transmission of a specific complete draft, never legal
approval, mandate acceptance or invoice issuance. Sending is self-account only.
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
from scripts.demo_runtime import DemoRunner,DemoError,RUNTIME as DEMO_RUNTIME
from scripts.demo_workflow import ROOT
from scripts.workspace_workflow import inbox_graph,message_graph,analysis_graph,send_graph,check_graph
from scripts.onboarding_schemas import OnboardingRequest,OnboardingBundle
from scripts.document_examples import scenarios

RUNTIME=ROOT/'data/gmail_workspace'
DOWNLOADS=ROOT/'downloads'
KINDS=('vollmacht','fee_agreement','advance_invoice')

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

class WorkspaceN8N(DemoRunner):
 def __init__(self,runtime=RUNTIME,**kwargs):super().__init__(runtime=runtime,**kwargs)
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
  check_graph(graph,allow_send);self.runtime.mkdir(parents=True,exist_ok=True,mode=0o700);DEMO_RUNTIME.mkdir(parents=True,exist_ok=True)
  with (DEMO_RUNTIME/'run.lock').open('a') as lock:
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
  profile={'name':'','address':'','client_type':'unknown','jurisdiction':'unknown','governing_law':'unknown','counterparty':'','scope':'','sender_role':'','registration_number':'','register_court':'','representative_name':'','representative_role':'','authority_reference':'','authority_checked':False,'firm_name':'','firm_address':'','lawyer_name':''}
  # Only reuse the retained REAL extraction for its exact original message/body.
  try:
   from scripts.natural_intake import EmailInquiry
   proof=json.loads((ROOT/'data/incept_prose_retry/grounding_revalidation.json').read_text())
   e=EmailInquiry(synthetic_data=True,message_id=message['id'],sender=parseaddr(message['from'])[1].lower(),recipient=parseaddr(message['to'])[1].lower(),subject=message['subject'],body=message['body'])
   if hashlib.sha256(e.model_dump_json().encode()).hexdigest()==proof['email_sha256']:
    data=proof['validated_extraction'];profile.update(name=data['company_name']['text'],client_type=data['client_type'],jurisdiction='Germany' if data.get('jurisdiction_clue',{}).get('text')=='Deutschland' else 'unknown',counterparty=data['counterparty']['text'],scope=data['requested_assistance']['text'],sender_role=data['sender_role']['text'] if data.get('sender_role') else '')
    profile['extraction_note']='Retained live extraction from this exact message, grounded to source excerpts; no new AI call. Authority remains unverified.'
  except (OSError,ValueError,KeyError,TypeError):pass
  profile.setdefault('extraction_note','Paid extraction is disabled. Confirm client identity/type/jurisdiction manually; the selected email supplies the unverified case facts.')
  return profile
 def payload(self,message,profile,synthetic):
  if synthetic is not True:raise DemoError('This backend supports authorized fictional/test inquiries only. Confirm the selected message is a test; real-client processing is not enabled.')
  if len(textline(profile.get('name')))<3:raise DemoError('Supply the claimed client name; sender identity does not prove the client or company authority.')
  # Existing backend safety requires .invalid synthetic contact addresses. The
  # actual Gmail sender remains separately available in the composer, never replaced.
  body=scenarios()['corporate'];body['draft_date']=datetime.now(ZoneInfo('Europe/Berlin')).date().isoformat();body['document_options']['representative']=None;body['firm']['email']='firm-contact-not-provided@workspace.invalid';body['document_options']['firm_policy']['policy_id']='WORKSPACE-DEMO-POLICY-v1';body['document_options']['place']=textline(profile.get('place')) or None
  for key in ('name','address','lawyer_name'):body['firm'][key]=textline(profile.get('firm_'+key if key!='lawyer_name' else key)) or '[Kanzleiangabe fehlt — nicht verifiziert]'
  body['client']={'name':textline(profile['name']),'address':textline(profile.get('address')) or '[Mandantenanschrift fehlt — nicht angegeben]','email':'contact-not-provided@workspace.invalid','client_type':profile.get('client_type','unknown'),'jurisdiction':profile.get('jurisdiction','unknown'),'registration_number':textline(profile.get('registration_number')) or None,'register_court':textline(profile.get('register_court')) or None}
  body['matter']={'title':textline(message['subject'])[:190] or 'Ausgewählte E-Mail-Anfrage','summary':textline(message['body'])[:2900],
    'requested_scope':textline(profile.get('scope')) or 'Vorläufige Prüfung der ausgewählten Testanfrage; Umfang anwaltlich zu klären.',
    'opposing_parties':[textline(profile['counterparty'])] if textline(profile.get('counterparty')) else [],'governing_law':profile.get('governing_law') if profile.get('governing_law') in ('Germany','United Kingdom') else 'unknown','claimed_deadline':None,'deadline_source':None}
  if profile.get('representative_name'):
   body['document_options']['representative']={'name':textline(profile['representative_name']),'role':textline(profile.get('representative_role')) or 'Rolle ungeklärt','authority_status':'synthetic_evidence_checked' if profile.get('authority_checked') else 'asserted','evidence_reference':textline(profile.get('authority_reference')) or None}
  body['document_options']['recipient_business_status']='business' if profile.get('client_type')=='company' else 'consumer' if profile.get('client_type')=='individual' else 'unknown'
  body['document_options']['engagement_law']='Germany' if profile.get('governing_law')=='Germany' else 'unknown'
  body['idempotency_key']='workspace-'+message['id']+'-'+digest({'profile':profile,'body':message['body'],'draft_date':body['draft_date']})[:20]
  return OnboardingRequest.model_validate(body).model_dump(mode='json')
 def analyze(self,mid,profile,synthetic=False,reanalyze=False):
  message=self.store.get('message:'+str(mid))
  if not message:raise DemoError('Select and read an email first.')
  payload=self.payload(message,profile,synthetic);case_id='case-'+mid;revision=digest(payload);previous=self.store.get(case_id)
  if previous and not reanalyze:
   same_source=previous.get('source_body_sha256')==hashlib.sha256(message['body'].encode()).hexdigest() if previous.get('source_body_sha256') else previous['payload']['matter']['summary']==payload['matter']['summary']
   if same_source and previous['profile']==profile:return {**previous,'reused':True}
  record=self.transport.run_graph(analysis_graph(message,payload,self.transport.binding()));values=results(record,'Workspace Case Result')
  if len(values)!=1:raise DemoError('n8n did not return a case result.')
  result=values[0];bundle=OnboardingBundle.model_validate(result['bundle'])
  if bundle.client.name!=payload['client']['name'] or bundle.matter.summary!=payload['matter']['summary'] or bundle.matter.opposing_parties!=payload['matter']['opposing_parties']:raise DemoError('Backend result does not match this selected email/intake.')
  if any(d.ready_for_issuance or d.legally_approved for d in bundle.documents) or any(a.executed for a in bundle.proposed_actions):raise DemoError('Approval safeguard violation.')
  case={'id':case_id,'message_id':mid,'source_body_sha256':hashlib.sha256(message['body'].encode()).hexdigest(),'revision':revision,'profile':profile,'payload':payload,'bundle':bundle.model_dump(mode='json'),'execution_id':record['id'],'workflow_id':record['workflowId'],'legal_research':result['legal_research'],'reused':False,'assessment_mode':'deterministic; no new paid AI request'}
  case['bundle']['assessment']['content_markdown']+='\n## Selected-email provenance and limitations\nSource: Gmail message '+mid+'; sender '+parseaddr(message['from'])[1]+'. Email statements are unverified allegations. Sender is not a verified company representative. '+profile.get('extraction_note','Manual intake confirmation; no paid AI extraction.')+'\nReal sender/reply contact is retained in the workspace; the backend .invalid contact is a clearly artificial safety placeholder, not client contact evidence. No registry verification was performed. Missing dates remain unknown.\n'
  if len(textline(message['body']))>2900:case['bundle']['assessment']['content_markdown']+='Long email: only the first 2,900 whitespace-normalized characters entered the bounded assessment; full message remains visible. Lawyer must review omitted content.\n'
  self.store.put(case_id,case);return case
 def case(self,case_id):
  case=self.store.get(str(case_id))
  if not case:raise DemoError('No current mandate case. Analyze a selected test email first.')
  return case
 def eligible(self,case,kind):
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
