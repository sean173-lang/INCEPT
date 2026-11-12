"""Build the sanitized n8n export for the isolated Project 3 MVP."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / "workflow.json"
CORPUS = Path(__file__).resolve().parent / "reference_corpus.json"
PROMPT = Path(__file__).resolve().parent / "prompts" / "corporate_intelligence_v1.md"
FORM_THEME = Path(__file__).resolve().parent / "form_theme.css"
TAVILY_PARSER = Path(__file__).resolve().parent / "tavily_parser.js"
MARKDOWN_RENDERER = Path(__file__).resolve().parent / "markdown_renderer.js"
FORM_REPORT_RENDERER = Path(__file__).resolve().parent / "form_report_renderer.js"
PATH = "ironhack-company-research"
FORM_PATH = "incept-company-research"


def node(name, kind, parameters, version=1, **extra):
    return {"id": uuid.uuid5(uuid.NAMESPACE_URL, "ironhack-p3:" + name).hex,
            "name": name, "type": "n8n-nodes-base." + kind, "typeVersion": version,
            "position": [0, 0], "parameters": parameters, **extra}


def build(credentials=None):
    credentials = credentials or {}
    webhook = node("Webhook Trigger", "webhook", {
        "httpMethod": "POST", "path": PATH, "responseMode": "lastNode",
        "authentication": "headerAuth", "options": {},
    }, 2.1)
    if credentials.get("webhook"):
        webhook["credentials"] = {"httpHeaderAuth": credentials["webhook"]}

    manual = node("Manual Trigger", "manualTrigger", {}, 1)
    demo_input = node("Set Demo Company", "set", {"assignments": {"assignments": [
        {"id": "demo-company-name", "name": "company_name", "value": "SAP SE", "type": "string"},
        {"id": "demo-register-id", "name": "register_identifier", "value": "", "type": "string"},
    ]}, "options": {}}, 3.4)
    form = node("Company Research Form", "formTrigger", {
        "authentication": "n8nUserAuth", "requireExecuteAccess": True,
        "trustedSource": "n8n-internal", "path": FORM_PATH,
        "formTitle": "CompanyScope",
        "formDescription": "Company research, made simple.\\nResearch German companies using official registry data, public web sources and AI-assisted analysis. Generate structured, source-referenced company reports in one workflow.",
        "formFields": {"values": [{
            "fieldName": "company_name", "fieldLabel": "Company name", "fieldType": "text",
            "placeholder": "e.g. SAP SE", "requiredField": True,
        }, {
            "fieldName": "register_identifier", "fieldLabel": "Register number (optional)", "fieldType": "text",
            "placeholder": "e.g. HRB 100653", "requiredField": False,
        }]},
        "responseMode": "lastNode",
        "options": {"path": FORM_PATH, "buttonLabel": "Generate Company Report", "appendAttribution": False,
                    "customCss": FORM_THEME.read_text(encoding="utf-8").strip()},
    }, 2.6)

    validate = node("Normalize Input", "code", {"mode": "runOnceForAllItems", "jsCode": """
const raw=$input.first().json||{};
const b=raw.body&&typeof raw.body==='object'?raw.body:raw;
const entrypoint=['production','test'].includes(raw.formMode)?'form':(raw.body?'webhook':'manual');
const name=String(b.company_name||'').trim();
const register=String(b.register_identifier||'').trim();
if(name.length<2||name.length>200) return [{json:{valid:false,entrypoint,error_code:'invalid_company_name',message:'company_name must contain 2–200 characters.'}}];
if(register.length>100||/[\\r\\n\\0]/.test(register)) return [{json:{valid:false,entrypoint,error_code:'invalid_register_identifier',message:'register_identifier is invalid.'}}];
return [{json:{valid:true,entrypoint,company_name:name,register_identifier:register||null,requested_at:new Date().toISOString()}}];
"""}, 2)
    input_if = node("Input Valid?", "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [{"leftValue": "={{ $json.valid === true }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 2.2)
    search = node("OpenRegister Search", "httpRequest", {
        "method": "GET",
        "url": "={{ 'https://api.openregister.de/v1/autocomplete/company?query='+encodeURIComponent($('Normalize Input').first().json.company_name.replace(/\\s+AG$/i,' Aktiengesellschaft')) }}",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "options": {"timeout": 20000, "redirect": {"redirect": {"followRedirects": False}}},
    }, 4.2, retryOnFail=False, onError="continueErrorOutput")
    if credentials.get("openregister"):
        search["credentials"] = {"httpHeaderAuth": credentials["openregister"]}
    choose = node("Select Exact Entity", "code", {"mode": "runOnceForAllItems", "jsCode": """
const raw=$input.first().json.body||$input.first().json;
const rows=Array.isArray(raw.results)?raw.results:[];
const req=$('Normalize Input').first().json;
const norm=s=>String(s||'').normalize('NFKC').toLocaleLowerCase('de').replace(/[^\\p{L}\\p{N}]/gu,'');
const normEntity=s=>norm(s).replace(/aktiengesellschaft$/,'ag');
const regNorm=s=>String(s||'').replace(/[^\\p{L}\\p{N}]/gu,'').toLocaleLowerCase('de');
const candidates=req.register_identifier
 ? rows.filter(r=>[r.register_number,r.company_id,`${r.register_type||''}${r.register_number||''}`].some(x=>regNorm(x)===regNorm(req.register_identifier)))
 : rows.filter(r=>normEntity(r.name)===normEntity(req.company_name));
const tokenSet=s=>new Set((String(s||'').normalize('NFKC').toLocaleLowerCase('de').match(/[\\p{L}\\p{N}]{2,}/gu)||[]).filter(t=>!['gmbh','ag','se','kg','ug','mbh','aktiengesellschaft','gesellschaft','mit','beschrankter','haftung'].includes(t)));
const requestedTokens=tokenSet(req.company_name);
const plausible=rows.filter(r=>{
 const nameTokens=tokenSet(r.name);
 return requestedTokens.size>0&&[...requestedTokens].every(t=>[...nameTokens].some(n=>n===t||n.startsWith(t)||t.startsWith(n)));
});
const displayCandidates=candidates.length>1?candidates:(candidates.length===0?plausible:[]);
const safeCandidates=displayCandidates.filter(r=>/^[A-Za-z0-9-]{5,100}$/.test(String(r.company_id||''))&&typeof r.name==='string'&&r.name.trim());
const list=safeCandidates.slice(0,10).map((r,i)=>{
 const number=String(r.register_number||r.register?.register_number||'not provided');
 const court=String(r.register_court||r.register?.register_court||'not provided');
 return `${i+1}. ${r.name} — ${r.register_type||r.register?.register_type||'Register'} ${number} — ${court}`;
});
if(candidates.length!==1) return [{json:{valid:false,failed_step:'OpenRegister identity resolution',error_code:candidates.length?'ambiguous_registry_identity':(safeCandidates.length?'company_candidate_selection_required':'exact_company_match_not_found'),candidate_count:safeCandidates.length,candidates:list,message:safeCandidates.length?`No company was selected automatically. Plausible OpenRegister candidates:\\n${list.join('\\n')}\\nRestart research using the exact registered company name. If names are duplicated, enter the register number in the optional register-number field.`:(candidates.length?'Registry identity is ambiguous, but OpenRegister did not return safely displayable candidate details. Enter a register number.':'No exact or plausible OpenRegister company match was found. Check the company name and try again.')}}];
const c=candidates[0];
if(!/^[A-Za-z0-9-]{5,100}$/.test(String(c.company_id||''))) return [{json:{valid:false,failed_step:'OpenRegister identity resolution',error_code:'invalid_registry_identifier',message:'OpenRegister returned no valid company identifier.'}}];
return [{json:{...req,valid:true,registry_match:c}}];
"""}, 2)
    identity_if = node("Entity Match?", "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [{"leftValue": "={{ $json.valid === true }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 2.2)
    details = node("OpenRegister Details", "httpRequest", {
        "method": "GET",
        "url": "={{ 'https://api.openregister.de/v1/company/'+encodeURIComponent($json.registry_match.company_id)+'?export=true' }}",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "options": {"timeout": 25000, "redirect": {"redirect": {"followRedirects": False}}},
    }, 4.2, retryOnFail=False, onError="continueErrorOutput")
    if credentials.get("openregister"):
        details["credentials"] = {"httpHeaderAuth": credentials["openregister"]}
    prep_research = node("Prepare Tavily Query", "code", {"mode": "runOnceForAllItems", "jsCode": """
const d=$input.first().json.body||$input.first().json;
const name=d.name?.name||d.name||$('Select Exact Entity').first().json.registry_match.name;
if(typeof name!=='string'||!name.trim()) throw new Error('OpenRegister company name missing');
const match=$('Select Exact Entity').first().json.registry_match;
const company={name,company_id:d.id||match.company_id,
 legal_form:d.legal_form||d.name?.legal_form||match.legal_form||null,register:d.register||d.company_register||match.register||{register_court:match.register_court||null,register_number:match.register_number||null,register_type:match.register_type||null},address:d.address||match.address||null,
 purpose:d.purpose?.purpose||d.purpose||null,industry_codes:d.industry_codes||null,status:d.status||null,
 retrieved_at:new Date().toISOString(),register_source:'OpenRegister API'};
const address=typeof company.address==='string'?company.address:JSON.stringify(company.address||{});
const purpose=typeof company.purpose==='string'?company.purpose:JSON.stringify(company.purpose||{});
const location=String((company.register||{}).register_court||'')+' '+address;
const search_query='"'+name+'" '+location+' '+purpose+' official website products services recent news developments';
return [{json:{company,company_name:name,search_query}}];
"""}, 2)
    tavily = node("Tavily Search", "httpRequest", {
        "method": "POST", "url": "https://api.tavily.com/search",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify({query:$json.search_query,search_depth:'advanced',max_results:8,include_answer:false,include_raw_content:false,include_images:false,auto_parameters:false}) }}",
        "options": {"timeout": 30000, "redirect": {"redirect": {"followRedirects": False}}, "response": {"response": {"fullResponse": True, "responseFormat": "json"}}},
    }, 4.2, retryOnFail=False, onError="continueErrorOutput")
    if credentials.get("tavily"):
        tavily["credentials"] = {"httpHeaderAuth": credentials["tavily"]}
    cards = json.dumps(json.loads(CORPUS.read_text(encoding="utf-8")), ensure_ascii=False)
    rag = node("Local RAG", "code", {"mode": "runOnceForAllItems", "jsCode": """
const cards=__CORPUS__;
const q=$('Prepare Tavily Query').first().json;
const terms=new Set((String(q.company.purpose||'')+' '+String(q.company.legal_form||'')+' corporate diligence sources follow-up').toLocaleLowerCase().match(/[\\p{L}\\p{N}]{4,}/gu)||[]);
const selected=cards.map(c=>({c,score:(c.title+' '+c.text).toLocaleLowerCase().match(/[\\p{L}\\p{N}]{4,}/gu)?.filter(t=>terms.has(t)).length||0})).sort((a,b)=>b.score-a.score).slice(0,3).map(x=>x.c);
return [{json:{company:q.company,search_query:q.search_query,rag_context:selected}}];
""".replace("__CORPUS__", cards)}, 2)
    parser = TAVILY_PARSER.read_text(encoding="utf-8")
    prep_tavily = node("Assemble Evidence", "code", {"mode": "runOnceForAllItems", "jsCode": parser + """
const c=$('Local RAG').first().json;
const envelope=$('Tavily Search').first().json;
const response=envelope.body||envelope;
if(!Array.isArray(response.results)) throw new Error('Tavily did not return a results list');
const web=parseTavilySources(response.results,c.company,new Date().toISOString());
const sources=[{id:'REGISTRY-1',kind:'registry',source_type:'official_registry',confidence:'official_registry_record',title:'OpenRegister company record',url:'https://api.openregister.de/v1/company/'+encodeURIComponent(c.company.company_id),retrieved_at:c.company.retrieved_at,published_at:null,content:JSON.stringify(c.company)},...web.sources];
return [{json:{company:c.company,rag_context:c.rag_context,sources,search_query:c.search_query,tavily_result_count:web.raw_result_count,tavily_http_status:envelope.statusCode||null,tavily_accepted_count:web.sources.length,tavily_rejected_reasons:web.rejected_reasons}}];
"""}, 2)
    def strings(max_items=8, max_length=500):
        return {"type": "array", "items": {"type": "string"}}
    source_ids = {"type": "array", "items": {"type": "string"}}
    cited_claim = {"type": "object", "additionalProperties": False, "properties": {
        "text": {"type": "string"}, "source_ids": source_ids,
        "claim_type": {"type": "string", "enum": ["reported_fact", "analysis"]}},
        "required": ["text", "source_ids", "claim_type"]}
    ai_schema = {"type": "object", "additionalProperties": False, "properties": {
        "executive_summary": {"type": "array", "items": cited_claim},
        "business_model_analysis": {"type": "array", "items": cited_claim},
        "public_findings": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "properties": {"source_id": {"type": "string"}, "finding": {"type": "string"},
                "significance": {"type": "string"},
                "finding_type": {"type": "string", "enum": ["company_presentation", "public_development", "other"]}},
            "required": ["source_id", "finding", "significance", "finding_type"]}},
        "analytical_observations": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "properties": {"observation": {"type": "string"},
                "why_it_matters": {"type": "string"}, "evidence_source_ids": source_ids,
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]}},
            "required": ["observation", "why_it_matters", "evidence_source_ids", "confidence"]}},
        "information_gaps": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "properties": {"gap": {"type": "string"}, "why_it_matters": {"type": "string"}},
            "required": ["gap", "why_it_matters"]}},
        "recommended_actions": {"type": "array", "items": {"type": "object", "additionalProperties": False,
            "properties": {"action": {"type": "string"}, "addresses_gap": {"type": "string"}},
            "required": ["action", "addresses_gap"]}},
        "business_activity_source_ids": source_ids,
        "public_research_source_ids": source_ids,
        "development_source_ids": source_ids,
        "uncertainties": strings(8, 240), "follow_ups": strings(8, 240),
    }, "required": ["executive_summary", "business_model_analysis", "public_findings", "analytical_observations", "information_gaps", "recommended_actions", "business_activity_source_ids", "public_research_source_ids", "development_source_ids", "uncertainties", "follow_ups"]}
    system_prompt = PROMPT.read_text(encoding="utf-8")
    prepare_ai = node("Prepare OpenAI Input", "code", {"mode": "runOnceForAllItems", "jsCode":
        "const e=$input.first().json;const schema=" + json.dumps(ai_schema, ensure_ascii=False) + ";" +
        "const webIds=e.sources.filter(s=>s.kind==='web_lead').map(s=>s.id);schema.properties.public_findings.items.properties.source_id.enum=webIds.length?webIds:['NO_PUBLIC_WEB_SOURCE'];" +
        "const system=" + json.dumps(system_prompt, ensure_ascii=False) + ";" +
        "const req={model:'gpt-4o-mini',store:false,max_output_tokens:3500,input:[{role:'system',content:system},{role:'user',content:JSON.stringify({company_name:e.company.name,registry_evidence:e.sources.filter(s=>s.kind==='registry'),public_web_research:e.sources.filter(s=>s.kind==='web_lead'),rag_context:e.rag_context,research_date:new Date().toISOString().slice(0,10)})}],text:{format:{type:'json_schema',name:'company_research_report',strict:true,schema}}};" +
        "return [{json:{...e,openai_request:req}}];"}, 2)
    ai = node("OpenAI Synthesis", "httpRequest", {
        "method": "POST", "url": "https://api.openai.com/v1/responses",
        "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
        "sendBody": True, "specifyBody": "json", "jsonBody": "={{ JSON.stringify($json.openai_request) }}",
        "options": {"timeout": 60000, "redirect": {"redirect": {"followRedirects": False}}},
    }, 4.2, retryOnFail=False, onError="continueErrorOutput")
    if credentials.get("openai"):
        ai["credentials"] = {"httpHeaderAuth": credentials["openai"]}
    validate_report = node("Validate & Render Report", "code", {"mode": "runOnceForAllItems", "jsCode": MARKDOWN_RENDERER.read_text(encoding="utf-8") + """
const raw=$input.first().json.body||$input.first().json;
const fail=(code,field)=>({json:{ok:false,n8n_execution_id:String($execution.id),entrypoint:$('Normalize Input').first().json.entrypoint,failed_step:'Source and claim validation',error_code:code,failed_field:field||null,openai_status:raw.status||'unknown',model:raw.model||'gpt-4o-mini',usage:raw.usage||null,message:'No report was accepted or saved.'}});
if(raw.status!=='completed') return [fail('openai_response_not_completed','response.status')];
const item=(raw.output||[]).flatMap(x=>x.content||[]).find(x=>x.type==='output_text');
if(!item?.text) return [fail('openai_structured_output_missing','response.output_text')];
let report;try{report=JSON.parse(item.text);}catch{return [fail('openai_json_invalid','response.output_text')];}
const evidence=$('Assemble Evidence').first().json;
const sources=Object.fromEntries(evidence.sources.map(s=>[s.id,s]));
const groups=['business_activity_source_ids','public_research_source_ids','development_source_ids'];
for(const group of groups){if(!Array.isArray(report[group])||report[group].length>5)return [fail('source_selection_invalid',group)];if(report[group].some(id=>typeof id!=='string'||!sources[id]))return [fail('unknown_source_id',group)];if(group!=='business_activity_source_ids'&&report[group].some(id=>sources[id].kind!=='web_lead'))return [fail('source_type_mismatch',group)];report[group]=[...new Set(report[group])];}
for(const field of ['executive_summary','business_model_analysis','public_findings','analytical_observations','information_gaps','recommended_actions'])if(!Array.isArray(report[field])||report[field].length>(field==='analytical_observations'||field==='recommended_actions'?3:8))return [fail('report_section_invalid',field)];
const cited=(items,path)=>{if(!Array.isArray(items))return path;for(let i=0;i<items.length;i++){const ids=items[i].source_ids||items[i].evidence_source_ids;if(!Array.isArray(ids)||!ids.length||ids.some(id=>typeof id!=='string'||!sources[id]))return path+'['+i+'].source_ids';}return null;};
for(const field of ['executive_summary','business_model_analysis','analytical_observations']){const issue=cited(report[field],'$.');if(issue)return [fail('claim_source_validation_failed',field+issue)];}
if(!Array.isArray(report.public_findings))return [fail('report_section_invalid','public_findings')];
const badPublicFinding=report.public_findings.findIndex(x=>!sources[x.source_id]||sources[x.source_id].kind!=='web_lead');
if(badPublicFinding>=0)return [fail('public_finding_source_invalid','public_findings['+badPublicFinding+'].source_id')];
for(const [i,x] of report.public_findings.entries())if(typeof x.finding!=='string'||!x.finding.trim()||typeof x.significance!=='string'||!x.significance.trim())return [fail('public_finding_invalid','public_findings['+i+']')];
for(const [i,x] of report.information_gaps.entries())if(!x.gap?.trim()||!x.why_it_matters?.trim())return [fail('information_gap_invalid','information_gaps['+i+']')];
for(const [i,x] of report.recommended_actions.entries())if(!x.action?.trim()||!x.addresses_gap?.trim())return [fail('recommended_action_invalid','recommended_actions['+i+']')];
for(const field of ['uncertainties','follow_ups'])if(!Array.isArray(report[field])||report[field].length>8||report[field].some(q=>typeof q!=='string'||q.trim().length<8||q.length>240))return [fail('review_item_invalid',field)];
const c=evidence.company;
const claimCount=report.executive_summary.length+report.business_model_analysis.length+report.analytical_observations.length+report.public_findings.length;
const markdown=renderCorporateReport(report,evidence,{execution_id:$execution.id,model:raw.model||'gpt-4o-mini'});
return [{json:{ok:true,n8n_execution_id:String($execution.id),entrypoint: $('Normalize Input').first().json.entrypoint,model:raw.model||'gpt-4o-mini',openai_status:raw.status,usage:raw.usage||null,company:c,rag_context:evidence.rag_context,sources:evidence.sources,report_markdown:markdown,validation:{source_ids_valid:true,cited_claims_have_source_ids:true,validated_cited_claim_count:claimCount,semantic_entailment:'not_automatically_verified'},retrieval:{tavily_results:evidence.tavily_result_count,tavily_http_status:evidence.tavily_http_status,tavily_accepted_count:evidence.tavily_accepted_count,tavily_rejected_reasons:evidence.tavily_rejected_reasons,search_query:evidence.search_query}}}];
"""}, 2)
    convert_report = node("Convert Report to File", "convertToFile", {"operation": "toText", "sourceProperty": "report_markdown", "binaryPropertyName": "data", "options": {"fileName": "={{ 'INCEPT-'+$json.company.name.replace(/[^A-Za-z0-9-]+/g,'-')+'-'+$json.n8n_execution_id+'.md' }}", "encoding": "utf8"}}, 1.2)
    save_report = node("Save Markdown Report", "readWriteFile", {"operation": "write", "fileName": "={{ '/Users/seanl/Projects/legalflow-ma/projects/ironhack_project3/reports/'+$binary.data.fileName }}", "dataPropertyName": "data", "options": {}}, 1.1)
    report_output = node("Report Output", "code", {"mode": "runOnceForAllItems", "jsCode": "const report=$('Validate & Render Report').first().json;return [{json:{...report,report_file:$('Save Markdown Report').first().json.fileName}}];"}, 2)
    form_success_if = node("Form Success?", "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [{"leftValue": "={{ $json.entrypoint === 'form' }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 2.2)
    form_error_if = node("Form Error?", "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [{"leftValue": "={{ $json.entrypoint === 'form' }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 2.2)
    render_form_result = node("Render Form Result", "code", {
        "mode": "runOnceForAllItems",
        "jsCode": FORM_REPORT_RENDERER.read_text(encoding="utf-8") + "\nconst companyScopeCss=" + json.dumps(FORM_THEME.read_text(encoding="utf-8").strip(), ensure_ascii=False) + ";\nconst item=$input.first().json||{};return [{json:{...item,form_html:renderCompanyScopeResult(item,companyScopeCss)}}];",
    }, 2)
    form_completion = node("Form Result", "form", {
        "operation": "completion", "respondWith": "showText",
        "responseText": "={{ $json.form_html }}",
        "options": {"appendAttribution": False},
    }, 2.5)
    return_report = node("Return Report", "code", {"mode": "runOnceForAllItems", "jsCode": "return [{json:$input.first().json}];"}, 2)
    return_error = node("Return Error", "code", {"mode": "runOnceForAllItems", "jsCode": "return [{json:$input.first().json}];"}, 2)
    validation_if = node("Validation Passed?", "if", {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}, "conditions": [{"leftValue": "={{ $json.ok === true }}", "rightValue": True, "operator": {"type": "boolean", "operation": "true", "singleValue": True}}], "combinator": "and"}, "options": {}}, 2.2)
    validation_error = node("Error: Validation", "code", {"mode": "runOnceForAllItems", "jsCode": "return [{json:$input.first().json}];"}, 2)

    failures = []
    for source_node, label in ((search, "OpenRegister company search"), (details, "OpenRegister company details"), (tavily, "Tavily public web search"), (ai, "OpenAI synthesis")):
        short_label = {"OpenRegister company search": "Registry Search", "OpenRegister company details": "Registry Details", "Tavily public web search": "Tavily", "OpenAI synthesis": "OpenAI"}[label]
        err = node("Error: " + short_label, "code", {"mode": "runOnceForAllItems", "jsCode": "const j=$input.first().json||{},b=j.body||{},e=b.error||j.error||{};const c=String(e.code||j.errorCode||'provider_request_failed');return [{json:{ok:false,n8n_execution_id:String($execution.id),entrypoint:$('Normalize Input').first().json.entrypoint,failed_step:"+json.dumps(label)+",error_code:/^[A-Za-z0-9_.-]{1,80}$/.test(c)?c:'provider_request_failed',http_status:Number.isInteger(j.statusCode)?j.statusCode:null,message:'The research step failed. No missing company research was fabricated.'}}];"}, 2)
        failures.append(err)
    identity_error = node("Error: Entity", "code", {"mode": "runOnceForAllItems", "jsCode": "const j=$input.first().json||{};return [{json:{ok:false,n8n_execution_id:String($execution.id),entrypoint:$('Normalize Input').first().json.entrypoint,failed_step:j.failed_step||'OpenRegister identity resolution',error_code:j.error_code||'exact_company_match_not_found',message:j.message||'No company details were selected.'}}];"}, 2)
    input_error = node("Error: Input", "code", {"mode": "runOnceForAllItems", "jsCode": "const j=$input.first().json||{};return [{json:{ok:false,n8n_execution_id:String($execution.id),entrypoint:j.entrypoint,failed_step:'Request validation',error_code:j.error_code||'invalid_request',message:j.message||'Company research request is invalid.'}}];"}, 2)

    nodes = [webhook, manual, demo_input, form, validate, input_if, search, choose, identity_if, details, prep_research, tavily, rag, prep_tavily, prepare_ai, ai, validate_report, validation_if, convert_report, save_report, report_output, form_success_if, form_error_if, render_form_result, form_completion, return_report, return_error, *failures, identity_error, input_error, validation_error]
    connections = {webhook["name"]: {"main": [[{"node": validate["name"], "type": "main", "index": 0}]]},
                   manual["name"]: {"main": [[{"node": demo_input["name"], "type": "main", "index": 0}]]},
                   demo_input["name"]: {"main": [[{"node": validate["name"], "type": "main", "index": 0}]]},
                   form["name"]: {"main": [[{"node": validate["name"], "type": "main", "index": 0}]]},
                   validate["name"]: {"main": [[{"node": input_if["name"], "type": "main", "index": 0}]]},
                   input_if["name"]: {"main": [[{"node": search["name"], "type": "main", "index": 0}], [{"node": input_error["name"], "type": "main", "index": 0}]]},
                   search["name"]: {"main": [[{"node": choose["name"], "type": "main", "index": 0}], [{"node": failures[0]["name"], "type": "main", "index": 0}]]},
                   choose["name"]: {"main": [[{"node": identity_if["name"], "type": "main", "index": 0}]]},
                   identity_if["name"]: {"main": [[{"node": details["name"], "type": "main", "index": 0}], [{"node": identity_error["name"], "type": "main", "index": 0}]]},
                   details["name"]: {"main": [[{"node": prep_research["name"], "type": "main", "index": 0}], [{"node": failures[1]["name"], "type": "main", "index": 0}]]},
                   prep_research["name"]: {"main": [[{"node": tavily["name"], "type": "main", "index": 0}]]},
                   tavily["name"]: {"main": [[{"node": rag["name"], "type": "main", "index": 0}], [{"node": failures[2]["name"], "type": "main", "index": 0}]]},
                   rag["name"]: {"main": [[{"node": prep_tavily["name"], "type": "main", "index": 0}]]},
                   prep_tavily["name"]: {"main": [[{"node": prepare_ai["name"], "type": "main", "index": 0}]]},
                   prepare_ai["name"]: {"main": [[{"node": ai["name"], "type": "main", "index": 0}]]},
                   ai["name"]: {"main": [[{"node": validate_report["name"], "type": "main", "index": 0}], [{"node": failures[3]["name"], "type": "main", "index": 0}]]},
                   validate_report["name"]: {"main": [[{"node": validation_if["name"], "type": "main", "index": 0}]]},
                   validation_if["name"]: {"main": [[{"node": convert_report["name"], "type": "main", "index": 0}], [{"node": validation_error["name"], "type": "main", "index": 0}]]},
                   convert_report["name"]: {"main": [[{"node": save_report["name"], "type": "main", "index": 0}]]},
                   save_report["name"]: {"main": [[{"node": report_output["name"], "type": "main", "index": 0}]]},
                   report_output["name"]: {"main": [[{"node": form_success_if["name"], "type": "main", "index": 0}]]},
                   form_success_if["name"]: {"main": [[{"node": render_form_result["name"], "type": "main", "index": 0}], [{"node": return_report["name"], "type": "main", "index": 0}]]},
                   render_form_result["name"]: {"main": [[{"node": form_completion["name"], "type": "main", "index": 0}]]}}
    for failure in failures + [identity_error, input_error, validation_error]:
        connections[failure["name"]] = {"main": [[{"node": form_error_if["name"], "type": "main", "index": 0}]]}
    connections[form_error_if["name"]] = {"main": [[{"node": render_form_result["name"], "type": "main", "index": 0}], [{"node": return_error["name"], "type": "main", "index": 0}]]}
    positions = {
        "Webhook Trigger": [0, 360], "Manual Trigger": [0, 0], "Set Demo Company": [320, 0],
        "Company Research Form": [0, 720],
        "Normalize Input": [680, 180], "Input Valid?": [1020, 180],
        "OpenRegister Search": [1360, 180], "Select Exact Entity": [1700, 180], "Entity Match?": [2040, 180],
        "OpenRegister Details": [2380, 180], "Prepare Tavily Query": [2720, 180],
        "Tavily Search": [3060, 180], "Local RAG": [3400, 180], "Assemble Evidence": [3740, 180],
        "Prepare OpenAI Input": [4080, 180], "OpenAI Synthesis": [4420, 180],
        "Validate & Render Report": [4760, 180], "Validation Passed?": [5100, 180],
        "Convert Report to File": [5440, 180], "Save Markdown Report": [5780, 180], "Report Output": [6120, 180],
        "Form Success?": [6460, 180], "Return Report": [6800, 180], "Render Form Result": [6800, 420], "Form Result": [7160, 420],
        "Form Error?": [6460, 620], "Return Error": [6800, 620],
        "Error: Registry Search": [1360, 620], "Error: Registry Details": [2380, 620],
        "Error: Tavily": [3060, 620], "Error: OpenAI": [4420, 620],
        "Error: Input": [1020, 620], "Error: Entity": [2040, 620], "Error: Validation": [5100, 620],
    }
    for item in nodes:
        if item["name"] not in positions:
            raise ValueError("Missing explicit layout position for " + item["name"])
        item["position"] = positions[item["name"]]
    validate_layout(nodes, connections)
    return {"name": "INCEPT — Company Research Agent", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "all", "saveDataErrorExecution": "all"}}


def validate_layout(nodes, connections):
    """Fail closed if export positions overlap or connections dangle."""
    by_name = {item["name"]: item for item in nodes}
    if len(by_name) != len(nodes):
        raise ValueError("Duplicate workflow node name")
    boxes, width, height = [], 260, 170
    for item in nodes:
        pos = item.get("position")
        if not isinstance(pos, list) or len(pos) != 2 or any(not isinstance(v, (int, float)) for v in pos):
            raise ValueError("Invalid position for " + item["name"])
        if len(item["name"]) > 25:
            raise ValueError("Workflow node label is too long: " + item["name"])
        x, y = pos
        for other, (ox, oy) in boxes:
            if x < ox + width and x + width > ox and y < oy + height and y + height > oy:
                raise ValueError("Overlapping nodes: " + other + " and " + item["name"])
        boxes.append((item["name"], (x, y)))
    for source, ports in connections.items():
        if source not in by_name:
            raise ValueError("Unknown connection source: " + source)
        for outputs in ports.get("main", []):
            for edge in outputs:
                if edge["node"] not in by_name:
                    raise ValueError("Unknown connection target: " + edge["node"])
                if edge["node"].startswith("Error:"):
                    source_y = by_name[source]["position"][1]
                    target_y = by_name[edge["node"]]["position"][1]
                    if target_y - source_y < 180:
                        raise ValueError("Error branch is not separated below its source: " + edge["node"])
    mainline = ["OpenRegister Search", "Select Exact Entity", "Entity Match?", "OpenRegister Details",
                "Prepare Tavily Query", "Tavily Search", "Local RAG", "Assemble Evidence",
                "Prepare OpenAI Input", "OpenAI Synthesis", "Validate & Render Report",
                "Validation Passed?", "Convert Report to File", "Save Markdown Report", "Report Output"]
    if any(by_name[right]["position"][0] - by_name[left]["position"][0] < 300
           for left, right in zip(mainline, mainline[1:])):
        raise ValueError("Main pipeline nodes must be spaced at least 300 px apart")
    if any(item["type"].endswith("respondToWebhook") for item in nodes):
        raise ValueError("Respond to Webhook is not compatible with manual trigger")
    form_node = by_name["Company Research Form"]
    if form_node["type"] != "n8n-nodes-base.formTrigger" or form_node["parameters"].get("responseMode") != "lastNode":
        raise ValueError("Company Research Form must return the final workflow result")
    fields = form_node["parameters"].get("formFields", {}).get("values", [])
    if not any(field.get("fieldName") == "company_name" and field.get("requiredField") for field in fields):
        raise ValueError("Company Research Form requires a company_name field")
    if not any(field.get("fieldName") == "register_identifier" and not field.get("requiredField") for field in fields):
        raise ValueError("Company Research Form requires an optional register_identifier field")


def write_sanitized():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_sanitized()
