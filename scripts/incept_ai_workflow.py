"""Separate inactive AI-synthesis development export; canonical graph is untouched."""
import copy
import json
from pathlib import Path
import uuid
from scripts.incept_document_workflow import build_workflow as document_workflow

VALIDATE = r'''
const response=$input.first().json;
const base=JSON.parse(JSON.stringify($('Unified Corporate Mandate Report').first().json));
function accounting(attempt) {
 const known=attempt&&typeof attempt.live_request==='boolean';
 base.non_ai_paid_api_calls=base.paid_api_calls??0;
 base.potentially_billable_ai_requests=known?(attempt.live_request?1:0):null;
 base.paid_api_calls=known?base.non_ai_paid_api_calls+base.potentially_billable_ai_requests:null;
 base.billing_confirmed=false;
}
function fallback(reason,attempt=null) {
 accounting(attempt);
 base.ai_synthesis={status:'unavailable',model_used:false,execution_mode:['mock','live'].includes(attempt?.execution_mode)?attempt.execution_mode:'disabled',live_request:attempt?.live_request??null,reason};
 base.bundle.assessment.content_markdown+='\n## AI analysis unavailable\n\nDeterministic assessment retained; no usable AI analysis is claimed. Lawyer review required.\n';
 base.uncertainty=[...new Set([...(base.uncertainty||[]),'AI analysis unavailable: '+reason])];
 return [{json:base}];
}
const body=response.body;
if(response.statusCode!==200 || !body || !['completed','unavailable'].includes(body.status))return fallback('helper_unavailable_or_invalid_response');
if(body.status==='unavailable')return fallback(typeof body.reason==='string'&&/^[a-z0-9_]{1,100}$/.test(body.reason)?body.reason:'ai_unavailable',body);
const a=body.synthesis;
if(!a || a.client_id!==base.bundle.client.client_id || a.matter_id!==base.bundle.matter.matter_id || a.client_name!==base.bundle.client.name || JSON.stringify(a.opposing_parties)!==JSON.stringify(base.bundle.matter.opposing_parties) || a.governing_law!==(base.bundle.matter.governing_law||'unknown') || a.lawyer_review_required!==true)return fallback('case_context_or_approval_mismatch');
if(!['mock','live'].includes(body.execution_mode) || body.model_used!==(body.execution_mode==='live') || !body.assessment || body.assessment.conclusion!=='lawyer_review_required' || body.assessment.confidence!=='insufficient_for_legal_conclusions')return fallback('unsafe_ai_metadata');
const original=base.bundle.assessment;
if(JSON.stringify(body.assessment.factual_findings)!==JSON.stringify(original.factual_findings) || JSON.stringify(body.assessment.guidance)!==JSON.stringify(original.guidance) || JSON.stringify(body.assessment.missing_information)!==JSON.stringify(original.missing_information) || JSON.stringify(body.assessment.review_warnings||[])!==JSON.stringify(original.review_warnings||[]))return fallback('deterministic_assessment_modified');
if(!Array.isArray(body.assessment.sources)||body.assessment.sources.some(s=>!s||typeof s.source_id!=='string'||typeof s.content!=='string'))return fallback('invalid_ai_source_index');
const sources=new Map(body.assessment.sources.map(s=>[s.source_id,s]));
if(sources.size!==(body.assessment.sources||[]).length || !original.sources.every(s=>JSON.stringify(sources.get(s.source_id))===JSON.stringify(s)))return fallback('original_provenance_modified');
const sections=['factual_background','preliminary_legal_issues','source_supported_analysis','corporate_intelligence_observations','missing_information','uncertainties_and_limitations','questions_requiring_lawyer_review','proposed_next_steps'];
const statements=[a.mandate_summary];
for(const key of sections) {if(!Array.isArray(a[key]))return fallback('invalid_ai_schema');statements.push(...a[key]);}
for(const item of statements) {
 if(!item || !Array.isArray(item.source_ids) || !item.source_ids.length || !Array.isArray(item.evidence_quotes) || !item.evidence_quotes.length || item.source_ids.some(id=>!sources.has(id)) || item.evidence_quotes.some(q=>!q||typeof q.source_id!=='string'||!item.source_ids.includes(q.source_id)||typeof q.quote!=='string'||!sources.get(q.source_id)?.content.includes(q.quote)))return fallback('unsupported_ai_citation');
}
if(typeof body.assessment.content_markdown!=='string' || !body.assessment.content_markdown.startsWith(original.content_markdown) || !body.assessment.content_markdown.includes('Requires professional lawyer review'))return fallback('invalid_ai_report');
// Only the assessment is replaceable. Documents, amounts and actions stay untouched.
base.bundle.assessment=body.assessment;
accounting(body);
base.ai_synthesis={status:body.status,model_used:body.model_used,live_request:body.live_request,execution_mode:body.execution_mode,model:body.model,reason:body.reason,cache_hit:body.cache_hit,evidence_fingerprint:body.evidence_fingerprint};
base.ai_analysis=a;
base.all_external_actions_pending_lawyer_approval=true;
return [{json:base}];
'''


def build_workflow():
    graph=copy.deepcopy(document_workflow())
    graph['name']='INCEPT — optional AI mandate synthesis development (manual; live AI disabled by default)'
    def add(name, kind, parameters, **extra):
        graph['nodes'].append({'id':uuid.uuid5(uuid.NAMESPACE_URL,'incept-ai-synthesis:'+name).hex,'name':name,'type':'n8n-nodes-base.'+kind,
            'typeVersion':4.5 if kind=='httpRequest' else 2,'position':[2000+len(graph['nodes'])*30,1700],'parameters':parameters,**extra})
    add('POST AI Mandate Synthesis','httpRequest',{'method':'POST','url':'http://127.0.0.1:8003/v1/onboarding/synthesis',
        'sendBody':True,'specifyBody':'json','jsonBody':"={{ JSON.stringify({bundle:$json.bundle,corporate_result:$json.corporate_client_intelligence||null,primary_research:['verified','partially_verified'].includes($json.primary_research?.status)?$json.primary_research:null}) }}",
        'options':{'timeout':25000,'redirect':{'redirect':{'followRedirects':False}},'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}},retryOnFail=False,onError='continueRegularOutput')
    add('Validate AI Synthesis Response','code',{'mode':'runOnceForAllItems','jsCode':VALIDATE})
    add('AI Final Mandate Report','code',{'mode':'runOnceForAllItems','jsCode':"return [{json:{...$input.first().json,workflow_variant:'optional_ai_synthesis',lawyer_review_queue:'pending_lawyer_approval'}}];"})
    for a,b in [('Unified Corporate Mandate Report','POST AI Mandate Synthesis'),('POST AI Mandate Synthesis','Validate AI Synthesis Response'),('Validate AI Synthesis Response','AI Final Mandate Report')]:
        graph['connections'][a]={'main':[[{'node':b,'type':'main','index':0}]]}
    return graph


if __name__=='__main__':
    path=Path(__file__).resolve().parents[1]/'workflows/incept_ai_synthesis_dev.json'
    path.write_text(json.dumps(build_workflow(),indent=2,ensure_ascii=False)+'\n')
