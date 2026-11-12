"""Interactive inbox/mandate/document/reply workspace. No automatic sending."""
from email.utils import parseaddr
from scripts.gmail_workspace import GmailWorkspace,KINDS
from scripts.workspace_runtime import WorkspaceError
from scripts.report_renderer import text

INTAKE_FIELDS=[('name','Mandant/in — Name, falls aus der Nachricht ersichtlich'),('email','Kontakt-E-Mail'),('address','Anschrift, falls angegeben'),('counterparty','Gegenseite, falls angegeben'),('scope','Gewünschte Unterstützung')]
DOCUMENT_FIELDS=[('representative_name','Vertretende Person'),('representative_role','Rolle laut Unterlagen'),('authority_reference','Nachweisreferenz'),('authority_checked','Nachweis anwaltlich geprüft'),('place','Ort'),('firm_name','Kanzlei'),('firm_address','Kanzleianschrift'),('lawyer_name','Verantwortliche/r Anwältin/Anwalt'),('firm_policy_id','Honorarregelung: Referenz'),('hourly_rate','Vorgegebener Nettostundensatz'),('advance_hours','Vorgegebene Vorschussstunden'),('vat_mode','Umsatzsteuer: unknown, taxable, exempt'),('vat_percent','Vorgegebener Umsatzsteuersatz'),('vat_basis','Grundlage der Umsatzsteuerangabe'),('billing_method','Abrechnungsmethode'),('billing_increment_minutes','Abrechnungsschritt in Minuten'),('time_recording','Zeiterfassung'),('expenses_terms','Auslagenregelung'),('payment_terms','Zahlungsbedingungen'),('other_professionals_terms','Weitere Kosten'),('tax_identifier','Steuernummer'),('payment_instructions','Zahlungsangaben'),('vat_configuration_confirmed','Umsatzsteuer anwaltlich geprüft')]
FIELDS=INTAKE_FIELDS+DOCUMENT_FIELDS


def synthesis_runtime_summary(case):
 synthesis=case.get('ai_synthesis') or {}
 accepted=(synthesis.get('status')=='completed' and synthesis.get('model_used') is True and
           synthesis.get('execution_mode')=='live' and synthesis.get('contract_version')=='2.0')
 model=synthesis.get('model')
 if not isinstance(model,str) or not model or len(model)>100 or any(not (c.isalnum() or c in '._-') for c in model):model='not configured/unknown'
 return ('OpenAI called this run: '+('yes' if synthesis.get('live_request') is True else 'no')+
         ' · model: '+model+' (used: '+('yes' if synthesis.get('model_used') is True else 'no')+')'+
         ' · source-exact v2 validation: '+('passed' if accepted else 'not accepted'))


def build_workspace_app(workspace=None):
 import gradio as gr
 ws=workspace or GmailWorkspace()
 def view(case=None,include_documents=True):
  if not case:return ('No selected matter yet.','Select a Gmail inquiry and authorize its processing to generate an assessment.','Client identity, address, authority and case facts must be confirmed.','Optional legal document drafts have not been generated.',*(['']*3),*([None]*3),gr.update(choices=[],value=[]),gr.update(choices=[],value=[]),'')
  b=case['bundle'];status=('Loaded previously validated current-version AI result — ' if case.get('reused') else 'Processed selected message — ')+'n8n execution **#'+case['execution_id']+'**. '+case['assessment_mode']+'. '+synthesis_runtime_summary(case)
  missing='## Missing information\n\n'+'\n'.join('- '+text(s) for s in b['assessment']['missing_information'])
  missing+='\n\n## Pending lawyer decisions\n'+'\n'.join('- **'+text(a['title'])+'** — '+a['state']+'; not executed' for a in b['proposed_actions'])
  missing+='\n\nSender role: '+text(case['profile'].get('sender_role') or 'unknown')+'; authority is not inferred from email identity. Actual Gmail contact stays in the reply composer.'
  docs={d['kind']:d for d in b.get('documents',[])} if include_documents else {};eligible=[]
  if not include_documents:
   statuses='Document drafts are excluded from Analyze. Use the separate optional action to generate or load them.'
   previews=['']*3;downloads=[None]*3
  elif not docs:
   statuses='Drafts have not been generated. Use “Generate legal document drafts (optional)” after reviewing the assessment.'
   previews=['']*3;downloads=[None]*3
  else:
   lines=['| Document | Backend status | Attachment restriction |','|---|---|---|']
   for kind in KINDS:
    okay,reason=ws.eligible(case,kind)
    if okay:eligible.append(kind)
    lines.append('| '+kind+' | '+docs[kind]['completeness_status']+' | '+text(reason)+' |')
   lines+=['','All legal documents remain unissued and legally unapproved. A separate named-lawyer release can permit transmission of eligible drafts. Advance requests cannot be attached.']
   for kind in KINDS:lines+=['','### '+kind]+['- '+text(v) for v in docs[kind]['missing_information']]
   statuses='\n'.join(lines);previews=[docs[k]['content_markdown'] for k in KINDS];downloads=[ws.document(case['id'],k) for k in KINDS]
  return (status,b['assessment']['content_markdown'],missing,statuses,*previews,*downloads,gr.update(choices=eligible,value=[]),gr.update(choices=ws.released(case),value=[]),case['id'])
 def refresh(query,current):
  try:
   rows,eid,account=ws.refresh(query or '');choices=[(r['subject']+' — '+r['from'],r['id']) for r in rows]
   if current and current not in {r['id'] for r in rows} and ws.store.get('metadata:'+current):choices.append(('Previously selected message',current))
   return [[r['from'],r['date'],r['subject'],r['snippet']] for r in rows],gr.update(choices=choices,value=current if current else None),'Connected Gmail: **'+text(account)+'** · real read execution #'+eid+' · '+str(len(rows))+' messages.'
  except WorkspaceError as e:return gr.update(),gr.update(),text(str(e))
 def defaults(profile):
  return [profile.get(key,False if key in ('authority_checked','vat_configuration_confirmed') else 'unknown' if key in ('vat_mode','billing_method') else None if key=='billing_increment_minutes' else '') for key,_ in FIELDS]
 def empty_view(status='Select an email, then click ANALYZE.'):
  values=list(view());values[0]=status;return tuple(values)
 def select(mid):
  reset=('No message selected.','','','','',*defaults({}),'','','','No reply preview yet.','',False,gr.update(interactive=False),False,*empty_view(),gr.update(selected='inbox'))
  if not mid:return reset
  try:message,eid,profile=ws.select(mid)
  except Exception as error:
   safe=str(error) if isinstance(error,WorkspaceError) else 'Could not read this message. Refresh Gmail and try selecting it again.'
   values=list(reset);values[-14]='Analysis failed: '+safe;return tuple(values)
  metadata='**From:** '+text(message['from'])+'\n\n**Subject:** '+text(message['subject'])+'\n\n**Date:** '+text(message['date'])
  att='Attachments: '+(', '.join(text(a['filename']) for a in message['attachments']) or 'none')
  recipient=parseaddr(message['from'])[1];subject=message['subject'] if message['subject'].lower().startswith('re:') else 'Re: '+message['subject']
  body='Guten Tag,\n\nwir bestätigen den Eingang Ihrer Nachricht. Wir prüfen Ihre Anfrage und melden uns anschließend. Diese Eingangsbestätigung ist keine Mandatsannahme.\n\nMit freundlichen Grüßen'
  note='Selected Gmail message '+mid+' · read execution #'+eid+'. '+profile.get('extraction_note','Manual confirmation required; no paid extraction.')
  # Never render a stored case merely because a different inbox item was selected.
  # Analyze explicitly loads/reprocesses it and labels cache reuse honestly.
  return (metadata,message['body'],att,note,mid,*defaults(profile),recipient,subject[:200],body,'No reply preview yet.','',False,gr.update(interactive=False),False,*empty_view('Email selected. Review the message and authorize processing before analysis.'),gr.update(selected='inbox'))
 def begin():
  return (*empty_view('Analyzing… Please wait for n8n and FastAPI. No email will be sent.'),'',False,gr.update(interactive=False),'Reply preview cleared while analysis runs.')
 def analyze(picked_mid,ready_mid,authorized,reanalyze,*values):
  stage='input'
  try:
   if not picked_mid:raise WorkspaceError('Select an email in INBOX first.')
   if not ready_mid or picked_mid!=ready_mid:raise WorkspaceError('The selected email is still loading. Wait until its body appears, then click ANALYZE again.')
   if authorized is not True:raise WorkspaceError('Confirm that this inquiry may be sent to the configured AI provider before analysis.')
   profile=dict(zip([k for k,_ in FIELDS],values))
   message=ws.store.get('message:'+picked_mid)
   if not message:raise WorkspaceError('The selected message is not loaded. Refresh Gmail and select it again.')
   profile['extraction_note']=ws.prefill(message)['extraction_note']
   stage='n8n_processing'
   case=ws.analyze(picked_mid,profile,authorized,reanalyze)
   stage='assessment_display'
   result=list(view(case,include_documents=False))
   result[0]=(('Previously validated current-version AI analysis loaded — n8n execution **#'+case['execution_id']+'**. No new n8n execution ran for this unchanged matter. ') if case.get('reused') else ('Assessment completed — n8n execution **#'+case['execution_id']+'**. Optional legal documents have not been generated. '))+synthesis_runtime_summary(case)
   return (*result,'',False,gr.update(interactive=False),'Preview again after inspecting the current documents.',gr.update(selected='analysis'))
  except Exception as error:
   if stage=='assessment_display':reason='The backend returned an assessment, but the report display failed. No document generation was requested.'
   elif isinstance(error,WorkspaceError):reason=str(error)
   elif isinstance(error,ValueError):reason='The selected inquiry or optional draft inputs failed validation. Check the supplied details and preserved n8n diagnostics.'
   else:reason='AI analysis could not be completed. Inspect the preserved execution diagnostics before retrying.'
   # Persistent visible status, never a toast-only error or a silent fixture.
   from pathlib import Path
   import json,os
   path=ws.root/'ui_errors.jsonl'
   try:
    with path.open('a') as log:log.write(json.dumps({'operation':'analyze','stage':stage,'message_id':picked_mid,'error_type':type(error).__name__,'reason':reason})+'\n')
    path.chmod(0o600)
   except OSError:pass
   target='analysis' if isinstance(error,ValueError) else 'inbox'
   return (*empty_view('Analysis failed: '+reason),'',False,gr.update(interactive=False),'No reply preview: analysis failed.',gr.update(selected=target))
 def generate_documents(case_id):
  try:
   case=ws.generate_documents(case_id);result=list(view(case))
   action='Existing optional legal document drafts loaded' if case.get('documents_reused') else 'Optional legal document drafts generated'
   result[0]=action+' — n8n execution **#'+case['document_execution_id']+'**. They remain unapproved and unissued.'
   return (*result,'',False,gr.update(interactive=False),'Document set changed; preview the reply again before any separate send confirmation.')
  except Exception as error:
   reason=str(error) if isinstance(error,WorkspaceError) else 'The optional document generation action failed. Check n8n and FastAPI; the assessment remains available.'
   case=ws.store.get(str(case_id)) if case_id else None
   try:current=list(view(case))
   except Exception:current=list(view(case,include_documents=False))
   current[0]='Document generation failed: '+reason+' Assessment remains available.'
   return (*current,'',False,gr.update(interactive=False),'No document generation success claimed; reply preview cleared.')
 def release(case_id,kinds,reviewer,confirmed):
  try:
   released=ws.release(case_id,kinds or [],reviewer,confirmed);return 'Released for draft transmission only: '+', '.join(released),gr.update(choices=ws.released(ws.case(case_id)),value=[]),False
  except WorkspaceError as e:return str(e),gr.update(),False
 def preview(case_id,recipient,subject,body,kinds):
  try:
   token,proof=ws.preview(case_id,recipient,subject,body,kinds or [])
   description='## Exact send preview\n\n**Recipient:** '+text(proof['recipient'])+'\n\n**Subject:** '+text(proof['subject'])+'\n\n**Attachments:** '+(', '.join(text(a['filename'])+' [SHA256 '+a['sha256'][:16]+']' for a in proof['attachments']) or 'NONE')+'\n\n'+text(proof['body'])+'\n\nNothing in this preview accepts the mandate or issues an invoice.'
   return description,token,False,gr.update(interactive=True)
  except WorkspaceError as e:return str(e),'',False,gr.update(interactive=False)
 def send(token,case_id,recipient,subject,body,kinds,confirmed):
  try:
   result=ws.send(token,case_id,recipient,subject,body,kinds or [],confirmed)
   return 'Gmail reports SENT — message '+result['gmail_message_id']+' · n8n execution #'+result['execution_id']+(' · duplicate send prevented' if result.get('duplicate_prevented') else '')+'. No mandate accepted or invoice issued.',False,gr.update(interactive=False)
  except WorkspaceError as e:return str(e),False,gr.update(interactive=False)
  except Exception:return 'Gmail send failed or is uncertain. No success is claimed. Do not retry automatically; inspect Gmail/n8n.',False,gr.update(interactive=False)
 with gr.Blocks(title='INCEPT | Gmail mandate workspace',analytics_enabled=False) as app:
  gr.Markdown('# INCEPT\nGmail → legal assessment → lawyer-reviewed drafts. Analysis sends the selected message to the configured AI provider.')
  analysis_status=gr.Markdown('Select an email to begin.',elem_id='analysis-status')
  ready_mid=gr.State('');case_id=gr.State('');preview_token=gr.State('')
  fields={}
  def field(key):
   label=dict(FIELDS)[key]
   if key=='vat_mode':c=gr.Dropdown(['unknown','taxable','exempt'],value='unknown',label=label)
   elif key=='billing_method':c=gr.Dropdown(['unknown','actual_minutes','specified_increment'],value='unknown',label=label)
   elif key=='billing_increment_minutes':c=gr.Number(label=label,precision=0,value=None)
   elif key=='vat_configuration_confirmed':c=gr.Checkbox(label=label,value=False)
   elif key=='authority_checked':c=gr.Checkbox(label=label,value=False)
   else:c=gr.Textbox(label=label,lines=2 if key in ('address','scope','authority_reference') else 1)
   fields[key]=c;return c
  with gr.Tabs(selected='inbox',elem_id='workspace-main-tabs') as primary_tabs:
   with gr.Tab('INBOX',id='inbox'):
    with gr.Row():search=gr.Textbox(label='Search inbox (optional)',scale=3);refresh_button=gr.Button('Refresh Gmail',scale=1)
    gmail_status=gr.Markdown('Loading connected Gmail…')
    # Kept hidden for backward-compatible refresh callback output, not primary UI.
    inbox=gr.Dataframe(headers=['Sender','Date','Subject','Snippet'],interactive=False,visible=False)
    picker=gr.Dropdown(label='Select email',choices=[],interactive=True,elem_id='email-picker')
    metadata=gr.Markdown('No message selected.');body_view=gr.Textbox(label='Message',lines=10,interactive=False);incoming=gr.Markdown('')
    test_confirm=gr.Checkbox(label='I authorize processing this selected inquiry by the configured external AI provider',value=False)
    analyze_button=gr.Button('ANALYZE',variant='primary',elem_id='analyze-button')
   with gr.Tab('ANALYSIS',id='analysis'):
    with gr.Accordion('Mandantenangaben — fehlende Angaben leer lassen',open=True):
     with gr.Row():field('name');field('email')
     with gr.Row():field('address');field('counterparty')
     field('scope')
     with gr.Accordion('Optionale Angaben für getrennte Dokumententwürfe',open=False):
      keys=[k for k,_ in DOCUMENT_FIELDS]
      for start in range(0,len(keys),2):
       with gr.Row():
        for key in keys[start:start+2]:field(key)
     regenerate=gr.Button('Save details & regenerate')
    gr.Markdown('### Mandate Assessment')
    assessment=gr.Markdown('No analysis yet.',elem_id='mandate-assessment')
    with gr.Accordion('Missing information & pending lawyer decisions',open=False):missing=gr.Markdown('No current case.')
    gr.Markdown('### Legal documents')
    generate_docs_button=gr.Button('Generate legal document drafts (optional)',variant='secondary')
    statuses=gr.Markdown('No current documents.',elem_id='document-statuses')
    previews=[];downloads=[]
    with gr.Tabs():
     for kind,label in [('vollmacht','Vollmacht'),('fee_agreement','Vergütungsvereinbarung'),('advance_invoice','Vorschussanforderung')]:
      with gr.Tab(label):previews.append(gr.Markdown('',elem_id='preview-'+kind));downloads.append(gr.File(label='Download '+label+' PDF',interactive=False))
   with gr.Tab('REPLY',id='reply'):
    gr.Markdown('Nothing is sent without preview and explicit confirmation. Incomplete documents cannot be attached.')
    recipient=gr.Textbox(label='Recipient');subject=gr.Textbox(label='Subject');reply_body=gr.Textbox(label='Reply message',lines=8)
    attachments=gr.CheckboxGroup(choices=[],value=[],label='Eligible released attachments — none selected by default')
    with gr.Accordion('Advanced: lawyer release of complete drafts',open=False):
     gr.Markdown('Transmission release is revision-bound. It does not approve the mandate, sign documents or issue an invoice. Advance requests remain blocked.')
     review_kinds=gr.CheckboxGroup(choices=[],value=[],label='Complete drafts eligible for review')
     reviewer=gr.Textbox(label='Reviewing lawyer');review_confirm=gr.Checkbox(label='I explicitly reviewed and release these complete drafts for transmission',value=False)
     review_button=gr.Button('Record draft release');review_status=gr.Markdown('No drafts released.')
    preview_button=gr.Button('Preview reply');reply_preview=gr.Markdown('No preview yet.')
    send_confirm=gr.Checkbox(label='I explicitly confirm this ONE self-addressed send to the previewed recipient and attachments',value=False)
    send_button=gr.Button('Send confirmed reply',variant='primary',interactive=False);send_status=gr.Markdown('Nothing sent.')
  with gr.Accordion('Diagnostics and reanalysis',open=False):
   extraction_note=gr.Markdown('No message loaded.')
   reanalysis=gr.Checkbox(label='Reanalyze instead of loading an existing result',value=False)
  components=[fields[key] for key,_ in FIELDS]
  view_outputs=[analysis_status,assessment,missing,statuses,*previews,*downloads,review_kinds,attachments,case_id]
  analyze_outputs=[*view_outputs,preview_token,send_confirm,send_button,reply_preview,primary_tabs]
  document_outputs=[*view_outputs,preview_token,send_confirm,send_button,reply_preview]
  begin_outputs=[*view_outputs,preview_token,send_confirm,send_button,reply_preview]
  app.load(refresh,[search,ready_mid],[inbox,picker,gmail_status],api_name=False,concurrency_limit=1,concurrency_id='gmail_workspace')
  refresh_button.click(refresh,[search,ready_mid],[inbox,picker,gmail_status],api_name='refresh_inbox',concurrency_limit=1,concurrency_id='gmail_workspace')
  picker.change(select,[picker],[metadata,body_view,incoming,extraction_note,ready_mid,*components,recipient,subject,reply_body,reply_preview,preview_token,send_confirm,send_button,test_confirm,*view_outputs,primary_tabs],api_name='select_message',concurrency_limit=1,concurrency_id='gmail_workspace')
  for button,name in ((analyze_button,'analyze_mandate'),(regenerate,'regenerate_mandate')):
   button.click(begin,inputs=[],outputs=begin_outputs,api_name=False,concurrency_limit=1,concurrency_id='gmail_workspace').then(analyze,[picker,ready_mid,test_confirm,reanalysis,*components],analyze_outputs,api_name=name,concurrency_limit=1,concurrency_id='gmail_workspace')
  generate_docs_button.click(generate_documents,[case_id],document_outputs,api_name='generate_documents',concurrency_limit=1,concurrency_id='gmail_workspace')
  review_button.click(release,[case_id,review_kinds,reviewer,review_confirm],[review_status,attachments,review_confirm],api_name='release_drafts',concurrency_limit=1,concurrency_id='gmail_workspace')
  preview_button.click(preview,[case_id,recipient,subject,reply_body,attachments],[reply_preview,preview_token,send_confirm,send_button],api_name='preview_reply',concurrency_limit=1,concurrency_id='gmail_workspace')
  send_button.click(send,[preview_token,case_id,recipient,subject,reply_body,attachments,send_confirm],[send_status,send_confirm,send_button],api_name='send_reply',concurrency_limit=1,concurrency_id='gmail_workspace')
 return app.queue(default_concurrency_limit=1)
