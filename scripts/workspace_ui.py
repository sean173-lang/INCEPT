"""Interactive inbox/mandate/document/reply workspace. No automatic sending."""
from email.utils import parseaddr
from scripts.gmail_workspace import GmailWorkspace,KINDS
from scripts.demo_runtime import DemoError
from scripts.report_renderer import text

FIELDS=[('name','Claimed client / company name'),('client_type','Client type'),('address','Client address — leave blank if unknown'),('jurisdiction','Client jurisdiction — only if known'),('governing_law','Explicit matter governing law — never inferred from company country'),('counterparty','Claimed counterparty'),('scope','Requested assistance / scope'),('sender_role','Sender’s claimed role — not verified'),('registration_number','Registration number — only if supplied'),('register_court','Register court — only if supplied'),('representative_name','Representative name — if supplied'),('representative_role','Representative role'),('authority_reference','Authority evidence reference — if actually reviewed'),('authority_checked','I reviewed the supplied fictional authority evidence'),('place','Place of signing / drafting — if supplied'),('firm_name','Law-firm name'),('firm_address','Law-firm address'),('lawyer_name','Responsible lawyer name')]


def build_workspace_app(workspace=None,fallback_builder=None):
 import gradio as gr
 ws=workspace or GmailWorkspace()
 def view(case=None):
  if not case:return ('No selected mandate yet.','Analyze an authorized test inquiry to generate its assessment.','Client identity, address, authority and case facts must be confirmed.','No current documents.',*(['']*3),*([None]*3),gr.update(choices=[],value=[]),gr.update(choices=[],value=[]),'')
  b=case['bundle'];status=('Reused existing result — ' if case.get('reused') else 'Processed selected message — ')+'n8n execution **#'+case['execution_id']+'**. '+case['assessment_mode']+'.'
  missing='## Missing information\n\n'+'\n'.join('- '+text(s) for s in b['assessment']['missing_information'])
  missing+='\n\n## Pending lawyer decisions\n'+'\n'.join('- **'+text(a['title'])+'** — '+a['state']+'; not executed' for a in b['proposed_actions'])
  missing+='\n\nSender role: '+text(case['profile'].get('sender_role') or 'unknown')+'; authority is not inferred from email identity. Actual Gmail contact stays in the reply composer. The backend .invalid address is a DEMO-only noncontact placeholder.'
  statuses=['| Document | Backend status | Attachment restriction |','|---|---|---|'];docs={d['kind']:d for d in b['documents']};eligible=[]
  for kind in KINDS:
   okay,reason=ws.eligible(case,kind)
   if okay:eligible.append(kind)
   statuses.append('| '+kind+' | '+docs[kind]['completeness_status']+' | '+text(reason)+' |')
  statuses+=['','All legal documents remain unissued and legally unapproved. A separate named-lawyer release can permit transmission of a complete Vollmacht/fee draft only. Advance requests cannot be attached in this pilot.','', '**Demo advance:** EUR 1,250 net + EUR 237.50 VAT = EUR 1,487.50.']
  for kind in KINDS:
   statuses+=['','### '+kind]+['- '+text(v) for v in docs[kind]['missing_information']]
  return (status,b['assessment']['content_markdown'],missing,'\n'.join(statuses),*[docs[k]['content_markdown'] for k in KINDS],*[ws.document(case['id'],k) for k in KINDS],gr.update(choices=eligible,value=[]),gr.update(choices=ws.released(case),value=[]),case['id'])
 def refresh(query,current):
  try:
   rows,eid,account=ws.refresh(query or '');choices=[(r['subject']+' — '+r['from'],r['id']) for r in rows]
   if current and current not in {r['id'] for r in rows} and ws.store.get('metadata:'+current):choices.append(('Previously selected message',current))
   return [[r['from'],r['date'],r['subject'],r['snippet']] for r in rows],gr.update(choices=choices,value=current if current else None),'Connected Gmail: **'+text(account)+'** · real read execution #'+eid+' · '+str(len(rows))+' messages.'
  except DemoError as e:return gr.update(),gr.update(),text(str(e))
 def select(mid):
  if not mid:return ('No message selected.','','','','',*[False if k=='authority_checked' else 'unknown' if k in ('client_type','jurisdiction','governing_law') else '' for k,_ in FIELDS],'','','','No reply preview yet.','',False,gr.update(interactive=False),*view())
  try:message,eid,profile=ws.select(mid)
  except DemoError as e:raise gr.Error(str(e)) from None
  existing=ws.store.get('case-'+mid)
  if existing:profile=existing['profile']
  metadata='**From:** '+text(message['from'])+'\n\n**Date:** '+text(message['date'])+'\n\n**Subject:** '+text(message['subject'])+'\n\nGmail message ID: '+mid+' · actual n8n read #'+eid
  att='\n'.join('- '+text(a['filename'])+' ('+str(a['size'])+' bytes; '+text(a['mime_type'])+')' for a in message['attachments']) or 'No incoming attachments reported.'
  recipient=parseaddr(message['from'])[1];subject=message['subject'] if message['subject'].lower().startswith('re:') else 'Re: '+message['subject']
  body='Guten Tag,\n\nvielen Dank für Ihre Anfrage. Dies ist eine ausschließlich simulierte INCEPT-Projektantwort. Die Unterlagen werden noch geprüft; es erfolgt keine Mandatsannahme und keine Rechnungsstellung.\n\nMit freundlichen Grüßen\nINCEPT Projektteam'
  return (metadata,message['body'],att,profile.get('extraction_note','Manual confirmation required; no paid extraction.'),mid,*[profile.get(key,False if key=='authority_checked' else '') for key,_ in FIELDS],recipient,subject[:200],body,'No reply preview yet.','',False,gr.update(interactive=False),*view(existing))
 def analyze(mid,synthetic,reanalyze,*values):
  if not mid:raise gr.Error('Select a Gmail message first.')
  profile=dict(zip([k for k,_ in FIELDS],values));message=ws.store.get('message:'+mid)
  if message:profile['extraction_note']=ws.prefill(message)['extraction_note']
  try:case=ws.analyze(mid,profile,synthetic,reanalyze)
  except DemoError as e:raise gr.Error(str(e)) from None
  except ValueError:raise gr.Error('Invalid client/matter fields. Check names, jurisdiction, field lengths and authority evidence. No successful analysis claimed.') from None
  return (*view(case),'',False,gr.update(interactive=False),'Reply preview invalidated; preview again after inspecting regenerated documents.')
 def release(case_id,kinds,reviewer,confirmed):
  try:
   released=ws.release(case_id,kinds or [],reviewer,confirmed);return 'Released for draft transmission only: '+', '.join(released),gr.update(choices=ws.released(ws.case(case_id)),value=[]),False
  except DemoError as e:return str(e),gr.update(),False
 def preview(case_id,recipient,subject,body,kinds):
  try:
   token,proof=ws.preview(case_id,recipient,subject,body,kinds or [])
   description='## Exact send preview\n\n**Recipient:** '+text(proof['recipient'])+'\n\n**Subject:** '+text(proof['subject'])+'\n\n**Attachments:** '+(', '.join(text(a['filename'])+' [SHA256 '+a['sha256'][:16]+']' for a in proof['attachments']) or 'NONE')+'\n\n'+text(proof['body'])+'\n\nSelf-addressed project test only. No mandate acceptance or invoice issuance.'
   return description,token,False,gr.update(interactive=True)
  except DemoError as e:return str(e),'',False,gr.update(interactive=False)
 def send(token,case_id,recipient,subject,body,kinds,confirmed):
  try:
   result=ws.send(token,case_id,recipient,subject,body,kinds or [],confirmed)
   return 'Gmail reports SENT — message '+result['gmail_message_id']+' · n8n execution #'+result['execution_id']+(' · duplicate send prevented' if result.get('duplicate_prevented') else '')+'. No mandate accepted or invoice issued.',False,gr.update(interactive=False)
  except DemoError as e:return str(e),False,gr.update(interactive=False)
  except Exception:return 'Gmail send failed or is uncertain. No success is claimed. Do not retry automatically; inspect Gmail/n8n.',False,gr.update(interactive=False)
 with gr.Blocks(title='INCEPT | Gmail mandate workspace',analytics_enabled=False) as app:
  gr.Markdown('# INCEPT\n### Gmail → Mandate workspace\nReal connected Gmail · authorized fictional/test inquiries only · read-only until explicit self-send confirmation')
  gr.Markdown('No paid AI or registry requests. Select an actual message; confirm missing client details. Sender identity never establishes company authority. The deterministic DEMO remains available in its own tab.')
  selected=gr.State('');case_id=gr.State('');preview_token=gr.State('')
  with gr.Tabs():
   with gr.Tab('INBOX'):
    with gr.Row():search=gr.Textbox(label='Inbox search',placeholder='Optional Gmail search');refresh_button=gr.Button('Refresh real Gmail inbox',variant='primary')
    gmail_status=gr.Markdown('Refresh to connect. No fabricated inbox is shown.')
    inbox=gr.Dataframe(headers=['Sender','Date','Subject','Snippet'],interactive=False,wrap=True)
    picker=gr.Dropdown(label='Select an actual message',choices=[],interactive=True)
    metadata=gr.Markdown('No message selected.');body_view=gr.Textbox(label='Full decoded message body',lines=12,interactive=False);incoming=gr.Markdown('Incoming attachments will be listed here.');extraction_note=gr.Markdown('')
    test_confirm=gr.Checkbox(label='I confirm this is an authorized fictional/test inquiry, not a real client instruction',value=False)
    reanalysis=gr.Checkbox(label='Explicitly reanalyze this already processed message',value=False)
    analyze_button=gr.Button('Analyze mandate',variant='primary')
    case_status=gr.Markdown('No mandate analyzed yet.')
   with gr.Tab('MANDATE'):
    gr.Markdown('### Client and matter details\nEnter only supplied/checked information. Blank details remain unknown. Changes regenerate artifacts through n8n and FastAPI, not by editing an unsynchronized document copy.')
    components=[]
    for start in range(0,len(FIELDS),2):
     with gr.Row():
      for key,label in FIELDS[start:start+2]:
       if key=='client_type':component=gr.Dropdown(['unknown','individual','company'],value='unknown',label=label)
       elif key in ('jurisdiction','governing_law'):component=gr.Dropdown(['unknown','Germany','United Kingdom'],value='unknown',label=label)
       elif key=='authority_checked':component=gr.Checkbox(label=label,value=False)
       else:component=gr.Textbox(label=label,lines=2 if key in ('address','scope','authority_reference') else 1)
       components.append(component)
    regenerate=gr.Button('Save corrections & regenerate through backend',variant='primary')
    assessment=gr.Markdown('Select a message and analyze it.');missing=gr.Markdown('Missing information will be explicit.')
   with gr.Tab('DOCUMENTS'):
    statuses=gr.Markdown('No current documents.')
    previews=[];downloads=[]
    with gr.Tabs():
     for kind in KINDS:
      with gr.Tab(kind):previews.append(gr.Markdown(''));downloads.append(gr.File(label='Download current draft PDF for review',interactive=False))
    gr.Markdown('### Lawyer transmission review\nBlocked documents cannot be released or attached. A release applies only to this exact revision and does not set legal approval or issue an invoice.')
    review_kinds=gr.CheckboxGroup(choices=[],value=[],label='Complete documents eligible for review')
    reviewer=gr.Textbox(label='Reviewing lawyer — supplied name');review_confirm=gr.Checkbox(label='I explicitly reviewed and release these complete drafts for this transmission',value=False);review_button=gr.Button('Record explicit draft-release decision');review_status=gr.Markdown('No documents released.')
   with gr.Tab('REPLY'):
    gr.Markdown('Controlled project pilot: only sending to the connected account itself is allowed. No automatic reply. Gmail send scope is verified only by an explicitly confirmed actual send; errors are reported honestly.')
    recipient=gr.Textbox(label='Exact recipient');subject=gr.Textbox(label='Subject');reply_body=gr.Textbox(label='Editable reply body',lines=10)
    attachments=gr.CheckboxGroup(choices=[],value=[],label='Released current-case attachments — NONE by default')
    preview_button=gr.Button('Preview exact reply and attachments');reply_preview=gr.Markdown('No preview yet.')
    send_confirm=gr.Checkbox(label='I explicitly confirm this ONE self-addressed Gmail send to the previewed recipient with the exact listed attachments',value=False)
    send_button=gr.Button('Send explicitly confirmed reply through Gmail',variant='primary',interactive=False);send_status=gr.Markdown('Nothing sent.')
   with gr.Tab('DEMO FALLBACK'):
    gr.Markdown('Fixed synthetic scenario only. This fallback is separate from selected-email processing; it never replaces a selected inbox message.')
    if fallback_builder is None:
     from scripts.gradio_app import build_app
     fallback_builder=build_app
    fallback_builder().render()
  view_outputs=[case_status,assessment,missing,statuses,*previews,*downloads,review_kinds,attachments,case_id]
  app.load(refresh,[search,selected],[inbox,picker,gmail_status],api_name=False,concurrency_limit=1,concurrency_id='gmail_workspace')
  refresh_button.click(refresh,[search,selected],[inbox,picker,gmail_status],api_name='refresh_inbox',concurrency_limit=1,concurrency_id='gmail_workspace')
  picker.change(select,[picker],[metadata,body_view,incoming,extraction_note,selected,*components,recipient,subject,reply_body,reply_preview,preview_token,send_confirm,send_button,*view_outputs],api_name='select_message',concurrency_limit=1,concurrency_id='gmail_workspace')
  for button,name in ((analyze_button,'analyze_mandate'),(regenerate,'regenerate_mandate')):
   button.click(analyze,[selected,test_confirm,reanalysis,*components],[*view_outputs,preview_token,send_confirm,send_button,reply_preview],api_name=name,concurrency_limit=1,concurrency_id='gmail_workspace')
  review_button.click(release,[case_id,review_kinds,reviewer,review_confirm],[review_status,attachments,review_confirm],api_name='release_drafts',concurrency_limit=1,concurrency_id='gmail_workspace')
  preview_button.click(preview,[case_id,recipient,subject,reply_body,attachments],[reply_preview,preview_token,send_confirm,send_button],api_name='preview_reply',concurrency_limit=1,concurrency_id='gmail_workspace')
  send_button.click(send,[preview_token,case_id,recipient,subject,reply_body,attachments,send_confirm],[send_status,send_confirm,send_button],api_name='send_reply',concurrency_limit=1,concurrency_id='gmail_workspace')
 return app.queue(default_concurrency_limit=1)
