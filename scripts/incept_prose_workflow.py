"""Separate manual-only prose intake graph. Export contains no credential bindings.

Real execution requires a locally bound dedicated account, exact approved message,
private service authentication and separately authorized two-request helper profile.
"""
import copy,json,uuid,re
from pathlib import Path
from scripts.document_examples import scenarios


def build_workflow(message_id='0000000000000000',account='project-demo@example.invalid',
                   subject='INCEPT-PROSE-APPROVED — fictional German inquiry',service_token='REPLACE_WITH_PRIVATE_SERVICE_TOKEN',gmail_binding=None):
    if not re.fullmatch(r'[a-fA-F0-9]{8,64}',message_id):raise ValueError('Exact approved Gmail message ID required')
    if not re.fullmatch(r'[A-Za-z0-9._+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}',account):raise ValueError('One dedicated project account required')
    mid=message_id;token=service_token;binding=gmail_binding or {}
    base=scenarios()['corporate'];base['document_options']['representative']=None;base['document_options']['invoice_number']=None
    base['client'].update(name='INCEPT DEMO GmbH',address='[Anschrift der fiktiven Gesellschaft noch zu ergänzen]',email='intake@incept-demo.invalid',jurisdiction='Germany',approved_provider_id='DEMO-INCEPT-DE',registration_number='DEMO-246468',register_court='Synthetic Berlin court',register_type='HRB')
    base['firm'].update(name='[Kanzleiname noch zu ergänzen]',address='[Kanzleianschrift noch zu ergänzen]',lawyer_name='[Bearbeitende Person noch zu ergänzen]')
    w={'name':'INCEPT — ordinary German prose, two authorized live AI calls (manual)','nodes':[],'connections':{},'settings':{'executionOrder':'v1'},'active':False}
    def add(name,kind,params,version=2):
     n={'id':uuid.uuid5(uuid.NAMESPACE_URL,'incept-prose-20261111:'+name).hex,'name':name,'type':'n8n-nodes-base.'+kind,'typeVersion':version,'position':[len(w['nodes'])*220,0],'parameters':params,'retryOnFail':False};w['nodes'].append(n)
     if len(w['nodes'])>1:w['connections'][w['nodes'][-2]['name']]={'main':[[{'node':name,'type':'main','index':0}]]}
     return n
    opts={'timeout':45000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}
    def http(name,url,body=None,google=False,text=False):
     p={'method':'POST' if body else 'GET','url':url,'options':copy.deepcopy(opts)}
     if text:p['options']['response']['response'].update(responseFormat='file',outputPropertyName='official_source')
     if body:p.update(sendBody=True,specifyBody='json',jsonBody=body)
     if google:p.update(authentication='predefinedCredentialType',nodeCredentialType='gmailOAuth2')
     if url.startswith('http://127.0.0.1:8005/'):
      p.update(sendHeaders=True,headerParameters={'parameters':[{'name':'X-LEGALFLOW-Service-Key','value':token}]})
     n=add(name,'httpRequest',p,4.5)
     if google:n['credentials']={'gmailOAuth2':binding}
     return n

    def code(name,js):
        if name in ('Validate Exact Message Scope','Decode Ordinary German Prose'):js='const account='+json.dumps(account)+';'+js
        return add(name,'code',{'mode':'runOnceForAllItems','jsCode':js})
    add('Manual Controlled Prose Test','manualTrigger',{},1)
    http('Read Exact Approved Gmail Metadata','https://gmail.googleapis.com/gmail/v1/users/me/messages/'+mid+'?format=metadata&metadataHeaders=From&metadataHeaders=To&metadataHeaders=Subject',google=True)
    code('Validate Exact Message Scope',"const r=$input.first().json,b=r.body;const h=n=>b?.payload?.headers?.filter(x=>x.name.toLowerCase()===n).map(x=>x.value);if(r.statusCode!==200||b?.id!=="+json.dumps(mid)+"||h('from')?.[0]!==account||h('to')?.[0]!==account||h('subject')?.[0]!=="+json.dumps(subject)+"||['from','to','subject'].some(k=>h(k)?.length!==1)||b.sizeEstimate>20000)throw new Error('Approved message metadata mismatch');return [{json:{message_id:b.id}}];")
    http('Read Approved Fictional Inquiry','https://gmail.googleapis.com/gmail/v1/users/me/messages/'+mid+'?format=full',google=True)
    code('Decode Ordinary German Prose',"const r=$input.first().json,b=r.body;const parts=[b?.payload,...(b?.payload?.parts||[])].filter(p=>p?.mimeType==='text/plain'&&p.body?.data);if(r.statusCode!==200||b.id!=="+json.dumps(mid)+"||parts.length!==1)throw new Error('One approved plain text body required');const text=Buffer.from(parts[0].body.data,'base64url').toString('utf8').replace(/\\r\\n/g,'\\n').trim();if(!text.includes('simulierte Testanfrage')||text.length>6000)throw new Error('Synthetic inquiry missing');return [{json:{synthetic_data:true,message_id:b.id,sender:account,recipient:account,subject:"+json.dumps(subject)+",body:text}}];")
    http('AI Extract Natural Intake','http://127.0.0.1:8005/v1/onboarding/extract','={{ JSON.stringify($json) }}')
    code('Validate Extracted Facts and Prepare Intake',"const r=$input.first().json,b=r.body,e=b?.extraction;if(r.statusCode!==200||b.status!=='completed'||!b.model_used||b.model!=='gpt-4o-mini'||e?.client_type!=='company'||e.company_name?.text!=='INCEPT DEMO GmbH'||!e.counterparty?.text)throw new Error('Live extraction failed or requires review');const intake="+json.dumps(base,ensure_ascii=False)+";intake.idempotency_key='incept-prose-gmail-'+$('Decode Ordinary German Prose').first().json.message_id;intake.client.name=e.company_name.text;intake.matter={title:'Simulierte Dienstleistungsforderung — anwaltliche Erstprüfung',summary:[e.matter_summary.text,...e.alleged_facts.map(x=>x.text),...e.dates.map(x=>x.text)].join(' '),requested_scope:e.requested_assistance.text,opposing_parties:[e.counterparty.text],governing_law:'Germany',claimed_deadline:null,deadline_source:null};return [{json:{intake,extraction:b}}];")
    http('Generate Real v2 Onboarding Drafts','http://127.0.0.1:8005/v1/onboarding/preview',"={{ JSON.stringify($json.intake) }}")
    code('Validate Draft Bundle',"const r=$input.first().json,b=r.body;if(r.statusCode!==200||b?.client?.name!=='INCEPT DEMO GmbH'||b.documents?.length!==3||b.documents.some(d=>d.template_version!=='2.0.0'||d.ready_for_issuance!==false||d.legally_approved!==false)||b.advance?.gross_total!=='1487.50'||b.proposed_actions?.length!==5||b.proposed_actions.some(a=>a.state!=='pending_lawyer_approval'||a.executed))throw new Error('Draft or approval safeguard failed');const audit=$('Validate Extracted Facts and Prepare Intake').first().json.extraction.grounding;if(audit){const message='Source grounding requires lawyer review: unsupported proposals were excluded ('+audit.excluded_proposals.map(x=>x.field).join(', ')+'); source case/spacing was restored. No sender authority verified.';b.assessment.review_warnings.push({warning_id:'intake:source-grounding',category:'unverified_evidence',message,source_ids:['intake:matter']});b.assessment.content_markdown+='\\n## Extraction grounding limitations\\n'+message+'\\n';}return [{json:{bundle:b}}];")
    http('Corporate Research Synthetic Only','http://127.0.0.1:8005/v1/onboarding/corporate-intelligence',"={{ JSON.stringify({synthetic_data:true,client_id:$json.bundle.client.client_id,matter_id:$json.bundle.matter.matter_id,client:$('Validate Extracted Facts and Prepare Intake').first().json.intake.client,source_policy:'approved_demo_fixture',max_external_requests:0,max_cached_operations:3}) }}")
    code('Preserve Synthetic Corporate Provenance',"const r=$input.first().json,c=r.body,b=$('Validate Draft Bundle').first().json.bundle;if(r.statusCode!==200||c.synthetic_evidence!==true||c.current_registry_verification!==false)throw new Error('Corporate provenance mismatch');b.assessment.content_markdown+='\\n'+c.section_markdown;return [{json:{bundle:b,corporate_result:c,legal_research:[]}}];")
    previous='Preserve Synthetic Corporate Provenance'
    for n in ('611','320','641'):
     http('Retrieve Official BGB '+n,'https://www.gesetze-im-internet.de/bgb/__'+n+'.html',text=True)
     code('Prepare Source Check '+n,"const r=$input.first().json;let bytes=null;if(r.statusCode===200 && $input.first().binary?.official_source){try{bytes=await this.helpers.getBinaryDataBuffer(0,'official_source');}catch{}}if(!bytes||bytes.length>200000)throw new Error('Official source bytes missing or oversized');return [{json:{synthetic_data:true,provision:'"+n+"',source_url:'https://www.gesetze-im-internet.de/bgb/__"+n+".html',retrieved_at:new Date().toISOString(),http_status:r.statusCode||503,source_html:'',source_bytes_base64:bytes.toString('base64'),source_content_type:r.headers?.['content-type']||''}}];")
     http('Verify Official Wording '+n,'http://127.0.0.1:8005/v1/onboarding/payment-research/verify','={{ JSON.stringify($json) }}')
     code('Attach Checked Guidance '+n,"const r=$input.first().json,e=r.body,p=JSON.parse(JSON.stringify($('"+previous+"').first().json));if(r.statusCode!==200||e?.status!=='wording_verified')throw new Error('Official source unavailable or wording changed');p.legal_research.push(e);p.bundle.assessment.sources.push(e.source);p.bundle.assessment.guidance.push({description:e.source.content,status:'reference_guidance',source_ids:[e.source.source_id]});p.bundle.assessment.content_markdown+='\\n## Official payment-dispute reference — not a case finding\\n'+e.source.content+'\\nSource: '+e.source.url+'; retrieved '+e.retrieved_at+'; '+e.limitation+'\\n';return [{json:p}];")
     previous='Attach Checked Guidance '+n
    http('AI Synthesize Mandate Assessment','http://127.0.0.1:8005/v1/onboarding/synthesis',"={{ JSON.stringify({bundle:$json.bundle,corporate_result:$json.corporate_result,primary_research:null}) }}")
    code('Validate Live AI Assessment and Pending Actions',"const r=$input.first().json,s=r.body,p=$('"+previous+"').first().json;if(r.statusCode!==200||s?.status!=='completed'||s.model_used!==true||!s.synthesis||s.synthesis.mandate_accepted!==false||s.synthesis.invoice_issued!==false||s.synthesis.documents_approved!==false||s.synthesis.external_actions_executed!==false)throw new Error('AI synthesis unavailable/rejected: '+(s?.reason||'unknown'));p.bundle.assessment=s.assessment;return [{json:{state:'LIVE_AI_PREVIEW_READY_FOR_LAWYER_REVIEW',...p,ai_synthesis:s,extraction:$('Validate Extracted Facts and Prepare Intake').first().json.extraction,message_id:$('Decode Ordinary German Prose').first().json.message_id,all_external_actions_pending_lawyer_approval:true,registry_requests:0,financial_requests:0,client_identity:'explicitly_fictional_not_registry_verified'}}];")
    for n in w['nodes']:
     assert not n['retryOnFail']
     if n['type'].endswith('httpRequest'):
      p=n['parameters'];assert p['method']=='GET' or p['url'].startswith('http://127.0.0.1:8005/')
      assert not any(x in p['url'].lower() for x in ('financial','openregister','tavily','send'))
    if not binding:
        for node in w['nodes']:node.pop('credentials',None)
    return w


if __name__=='__main__':
    Path('workflows/incept_prose_intake_dev.json').write_text(json.dumps(build_workflow(),ensure_ascii=False,indent=2)+'\n')
