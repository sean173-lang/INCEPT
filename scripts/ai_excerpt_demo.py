"""Hand-authored v2 selections and interpretation for offline contract evaluation.

This is not a model and is never a production fallback.
"""
import json


def mock_excerpt_response(packet):
    catalog=packet['excerpts'];context=packet['context']
    def reference(e):return {'excerpt_id':e['excerpt_id']}
    def pick(section,**conditions):
        return next(e for e in catalog.values() if section in e['allowed_sections'] and all(e.get(k)==v for k,v in conditions.items()))
    def question(statement,records,category='missing_evidence',kind='lawyer_review_request'):
        return {'statement':statement,'issue_category':category,'assertion_type':kind,
                'action_state':'not_performed_pending_lawyer_approval','evidence_references':[reference(e) for e in records]}
    def grounded_analysis(statement,legal,inquiry):
        return {'statement':statement,'issue_category':'german_contract_law','assertion_type':'conditional_analysis',
                'action_state':'not_performed_pending_lawyer_approval','legal_evidence':reference(legal),
                'inquiry_evidence':reference(inquiry)}
    coverage=pick('reasoning',role='coverage_limitation')
    summary=pick('mandate_summary');client=pick('factual_background',role='client')
    data={key:context[key] for key in ('client_id','matter_id','client_name','opposing_parties','governing_law')}
    data.update(contract_version='2.0',lawyer_review_required=True,mandate_accepted=False,documents_approved=False,
        invoice_issued=False,external_actions_executed=False,mandate_summary=reference(summary),factual_background=[reference(client)],
        preliminary_legal_issues=[],source_supported_analysis=[],
        missing_information=[question('Which original contract, invoice, performance records and correspondence should the lawyer request?',[coverage])],
        uncertainties_and_limitations=[question('Which intake allegations, missing trigger dates and authority limitations remain unresolved?',[coverage])],
        questions_requiring_lawyer_review=[question('What evidence supports the sender authority, conflict review and proposed mandate scope?',[coverage])],
        proposed_next_steps=[question('Should the lawyer review the original documents before considering any external action?',[coverage])])
    legal=next((e for e in catalog.values() if e['provenance'].get('scope') in ('applicable_legal_guidance','conditional_jurisdiction_candidate')),None)
    if legal:
        data['preliminary_legal_issues']=[question('Which contractual prerequisites and performance objections require review before applying this guidance?',[summary,legal],'mandate_intake')]
        statement='Wenn deutsches Recht anwendbar ist, kann der amtliche Regelungsgehalt für die geschilderte Vertragsfrage relevant sein; entscheidend sind der Vertrag, die konkrete Abweichung und die dokumentierte Reaktion der Gegenseite.'
        data['source_supported_analysis']=[grounded_analysis(statement,legal,summary)]
        data['questions_requiring_lawyer_review'].append(question('Welche Vertragsunterlagen und Belege sind für die rechtliche Einordnung entscheidend?',[summary,legal],'german_contract_law'))
    for category,support in packet['issue_support'].items():
        if not support['contradictions']:continue
        def span(entry):return next(e for e in catalog.values() if e['source_id']==entry['source_id'] and e['text']==entry['quote'] and 'reasoning' in e['allowed_sections'])
        data['uncertainties_and_limitations'].append(question('What original evidence resolves the disputed allegation and its denial?',[span(support['evidence'][0]),span(support['contradictions'][0])],category))
    return json.dumps(data,ensure_ascii=False),{'input_tokens':100,'output_tokens':100,'total_tokens':200}


def generate(output='reports/incept_source_exact_offline'):
    """Offline reports, including a German dispute; never regenerates live evidence."""
    import hashlib,socket,tempfile
    from pathlib import Path
    from unittest.mock import patch
    from scripts.ai_synthesis import SynthesisService,AIConfig,SynthesisRequest
    from scripts.ai_synthesis_demo import requests_for_demo
    from scripts.onboarding import OnboardingService
    from scripts.onboarding_schemas import OnboardingRequest,AssessmentSource,AssessmentFinding
    from scripts.document_examples import scenarios as document_scenarios
    from scripts.local_rag import LocalRAG
    from scripts.payment_research import CORPUS
    out=Path(output);out.mkdir(parents=True,exist_ok=True);summaries={}
    with tempfile.TemporaryDirectory() as tmp,patch.object(socket.socket,'connect',side_effect=AssertionError('Offline QA prohibits networking')):
        root=Path(tmp);cases=requests_for_demo(root/'cases.sqlite3',root/'cache')
        body=document_scenarios()['corporate'];body['idempotency_key']='source-exact-synthetic-company';body['document_options']['representative']=None
        body['client'].update(name='INCEPT DEMO GmbH',registration_number=None,approved_provider_id=None,register_court=None,register_type=None,jurisdiction='unknown',client_type='unknown')
        body['matter'].update(title='Simulierte streitige Dienstleistungsrechnung',summary='Die fiktive Mandantschaft behauptet eine offene Rechnung über 18.750 Euro. Nach ihrer Darstellung wurden die Leistungen erbracht. Die fiktive Nordlicht Projektservice GmbH bestreitet die Höhe und behauptet unvollständige Leistungen. Die Rechnung wurde laut Intake im Oktober gestellt; genaue Fälligkeit, Abnahme und Mahnung sind ungeklärt.',requested_scope='Erste rechtliche Einschätzung der behaupteten Forderung und Anforderung der Vertrags-, Rechnungs- und Leistungsunterlagen; keine Klage oder externe Aktion.',opposing_parties=['Nordlicht Projektservice GmbH'],governing_law='Germany')
        bundle=OnboardingService(root/'sample.sqlite3').preview(OnboardingRequest.model_validate(body))
        for card in LocalRAG(CORPUS).chunks.values():
            bundle.assessment.sources.append(AssessmentSource(source_id=card['chunk_id'],kind='legal_reference',locator=card['locator'],content=card['text'],url=card['source_url'],reviewed_at=card['reviewed_at'],document_date=card['document_date']))
            bundle.assessment.guidance.append(AssessmentFinding(description=card['text'],status='reference_guidance',source_ids=[card['chunk_id']]))
        from scripts.review_warnings import ReviewWarning
        bundle.assessment.review_warnings.append(ReviewWarning(warning_id='offline:curated-reference-only',category='provenance',message='Offline mock demonstration: legal reference wording is supplied from the curated corpus, not retrieved live. Sender authority, performance and payment entitlement are unverified.',source_ids=[]))
        cases['german_payment_dispute']=SynthesisRequest(bundle=bundle)
        service=SynthesisService(AIConfig(enabled=True,billing_verified=True,approval_id='explicit-offline-mock-only',model='MOCK-NOT-A-REAL-MODEL',max_requests=5,max_input_tokens=200000,max_output_tokens=3500,max_total_tokens=1000000),ledger_path=root/'synthesis.sqlite3',transport=mock_excerpt_response,corporate_cache_dir=root/'cache')
        for name,request in cases.items():
            request.contract_version='2.0';before=request.bundle.model_dump_json();documents=request.bundle.documents
            result=service.run(request)
            assert request.bundle.model_dump_json()==before
            folder=out/name;folder.mkdir(exist_ok=True)
            (folder/'mandate_assessment.md').write_text(result.assessment.content_markdown)
            (folder/'synthesis_response.json').write_text(result.model_dump_json(indent=2))
            for document in documents:(folder/(document.kind+'.md')).write_text(document.content_markdown)
            summaries[name]={'status':result.status,'reason':result.reason,'execution_mode':result.execution_mode,'model_used':result.model_used,'live_request':result.live_request,'contract_version':result.contract_version,'documents_unchanged':True,'document_sha256':{d.kind:hashlib.sha256(d.content_markdown.encode()).hexdigest() for d in documents},'all_five_actions_pending':len(request.bundle.proposed_actions)==5 and all(not a.executed and a.state=='pending_lawyer_approval' for a in request.bundle.proposed_actions),'advance_gross':request.bundle.advance.gross_total,'excerpt_count':len(result.excerpt_catalog)}
    (out/'summary.json').write_text(json.dumps(summaries,indent=2)+'\n');return summaries


if __name__=='__main__':print(json.dumps(generate(),indent=2))
