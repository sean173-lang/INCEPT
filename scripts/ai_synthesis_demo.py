"""Explicit MOCK LLM demonstrations, never a production fallback or live proof."""
import json
from pathlib import Path
import tempfile
from scripts.ai_synthesis import AIConfig, SynthesisRequest, SynthesisService
from scripts.onboarding import OnboardingService
from scripts.onboarding_schemas import OnboardingRequest
from scripts.incept_corporate_demo import scenarios
from scripts.corporate_intelligence import CorporateIntelligence, CorporateRequest


def mock_response(packet):
    """Hand-authored example contract for tests. Does NOT evaluate model reasoning."""
    c,sources=packet['context'],packet['sources']
    def item(id, message=None, status=None, quote_text=None):
        source=sources[id]
        if not quote_text and source['classification']=='question':
            coverage=json.loads(source['content']);quote_text=next(iter(coverage.get('limitations',[])),None)
        if not quote_text and id=='synthesis:intake:client':quote_text=c['client_name']
        if not quote_text and source['classification']=='source_guidance':quote_text=source['content']
        quote=quote_text or source['content'][:160]
        return {'statement':message or quote,'evidence_status':status or source['classification'],
                'source_ids':[id],'evidence_quotes':[{'source_id':id,'quote':quote}]}
    coverage='synthesis:intake:coverage'
    result={key:c[key] for key in ('client_id','matter_id','client_name','opposing_parties','governing_law')}
    result.update(lawyer_review_required=True,
        mandate_summary=item('synthesis:intake:matter',quote_text=json.loads(sources['synthesis:intake:matter']['content'])['summary']),factual_background=[item('synthesis:intake:client')],
        preliminary_legal_issues=[],source_supported_analysis=[],corporate_intelligence_observations=[],
        missing_information=[item(coverage,'Which original contract, correspondence and trigger evidence should the lawyer request?','question')],
        uncertainties_and_limitations=[item(coverage,'Which intake assertions, governing-law assumptions and source limitations remain unresolved?','question')],
        questions_requiring_lawyer_review=[item(coverage,'What evidence is needed to review identity, conflicts and representative authority?','question')],
        proposed_next_steps=[item(coverage,'Should the lawyer review the original documents and resolve missing evidence before any external action?','question')])
    legal=next((id for id,s in sources.items() if s['classification']=='source_guidance' and s.get('scope')=='applicable_legal_guidance'),None)
    if legal:
        result['preliminary_legal_issues']=[item(legal,'Which prerequisites and exceptions require review before applying this guidance to the matter?','question')]
        analysis=item(legal,'If a dispute is described only in intake, the lawyer may need original facts and a completed conflicts review before treating guidance as applicable.','preliminary_analysis')
        analysis['source_ids'].append('synthesis:intake:matter')
        analysis['evidence_quotes'].append({'source_id':'synthesis:intake:matter','quote':json.loads(sources['synthesis:intake:matter']['content'])['summary']})
        result['source_supported_analysis']=[analysis]
    corporate=next((id for id in sources if id.startswith('synthesis:corporate:') and id!='synthesis:corporate:coverage'),None)
    if corporate:
        observations=json.loads(sources[corporate]['content'])['observations']
        result['corporate_intelligence_observations']=[item(corporate,quote_text=observations[0] if observations else None)]
    corporate_coverage='synthesis:corporate:coverage'
    if corporate_coverage in sources:
        result['questions_requiring_lawyer_review'].append(item(corporate_coverage,'What original evidence is needed to resolve corporate identity discrepancies and representative authority?','question'))
        coverage=json.loads(sources[corporate_coverage]['content'])
        if coverage.get('discrepancies'):
            result['uncertainties_and_limitations'].append(item(corporate_coverage,'How should conflicting registration descriptions be reconciled before any identity conclusion?','question'))
    return json.dumps(result,ensure_ascii=False), {'input_tokens':100,'output_tokens':100,'total_tokens':200}


def requests_for_demo(db_path, cache_dir):
    store=OnboardingService(db_path); result={}
    for name,body in scenarios().items():
        bundle=store.preview(OnboardingRequest.model_validate(body))
        corporate=None
        if bundle.client.client_type=='company':
            corporate=CorporateIntelligence(cache_dir,allow_demo=True).collect(CorporateRequest(
                synthetic_data=True,client_id=bundle.client.client_id,matter_id=bundle.matter.matter_id,
                client=bundle.client,source_policy='approved_demo_fixture'))
        result[name]=SynthesisRequest(bundle=bundle,corporate_result=corporate)
    return result


def generate(output=None):
    output=Path(output or 'reports/incept_ai_synthesis_mock');output.mkdir(parents=True,exist_ok=True)
    summary={}
    with tempfile.TemporaryDirectory() as tmp:
        service=SynthesisService(AIConfig(enabled=True,billing_verified=True,approval_id='offline-mock-only',model='MOCK-NOT-A-REAL-MODEL',
            max_requests=4,max_input_tokens=100000,max_output_tokens=3000,max_total_tokens=400000),ledger_path=Path(tmp)/'ai.sqlite3',transport=mock_response)
        for name,request in requests_for_demo(Path(tmp)/'onboarding.sqlite3',Path(tmp)/'empty-cache').items():
            result=service.run(request)
            (output/(name+'.json')).write_text(result.model_dump_json(indent=2))
            (output/(name+'.md')).write_text(result.assessment.content_markdown)
            summary[name]={'status':result.status,'execution_mode':result.execution_mode,'model_used':result.model_used,'live_request':result.live_request,'reason':result.reason}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':
    print(json.dumps(generate(),indent=2))
