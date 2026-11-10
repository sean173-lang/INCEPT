"""Validate saved n8n execution evidence, not just its top-level success flag.

No network requests. Feed a private API execution export to assess what actually
ran. Older Phase 1 successes cannot pass the Phase 2 end-to-end checks.
"""
from scripts.local_rag import LocalRAG
from scripts.research_schemas import ResearchReport


REQUIRED = ('Verified Company', 'FastAPI Create Research Run', 'FastAPI Research Tool',
            'FastAPI Research Report', 'Due Diligence Report')


def outputs(node_run):
    return [item.get('json', {}) for branch in node_run.get('data', {}).get('main', []) if branch for item in branch]


def validate_execution(execution, rag=None):
    rag = rag or LocalRAG()
    runs = execution.get('data', {}).get('resultData', {}).get('runData', {})
    failures = []
    checks = {}

    def check(name, condition):
        checks[name] = bool(condition)
        if not condition:
            failures.append(name)

    check('execution_success', execution.get('status') == 'success' and execution.get('finished') is True)
    check('phase2_nodes_executed', all(runs.get(name) for name in REQUIRED))
    tools = runs.get('FastAPI Research Tool', [])
    check('exactly_two_tool_executions', len(tools) == 2)
    create = [item for node in runs.get('FastAPI Create Research Run', []) for item in outputs(node)]
    tool_responses = [item for node in tools for item in outputs(node)]
    check('first_planned_action_retrieval', len(create) == 1 and create[0].get('statusCode') == 200
          and create[0].get('body', {}).get('next_tool') == 'retrieve_references'
          and create[0].get('body', {}).get('iteration') == 0)
    check('second_planned_action_company_research', len(tool_responses) == 2
          and tool_responses[0].get('body', {}).get('iteration') == 1
          and tool_responses[0].get('body', {}).get('next_tool') == 'company_research')
    check('planner_stopped_at_two', len(tool_responses) == 2
          and tool_responses[1].get('body', {}).get('state') == 'complete'
          and tool_responses[1].get('body', {}).get('iteration') == 2
          and tool_responses[1].get('body', {}).get('next_tool') is None)
    check('tool_responses_development_only', len(tool_responses) == 2 and all(
        item.get('statusCode') == 200 and item.get('body', {}).get('development') is True for item in tool_responses))
    final = [item for node in runs.get('Due Diligence Report', []) for item in outputs(node)]
    report = None
    if len(final) == 1:
        try:
            report = ResearchReport.model_validate(final[0])
        except Exception:
            pass
    check('structured_report_valid', report is not None)
    if report is not None:
        check('development_report', report.development is True)
        check('reported_two_iterations', report.iterations == 2)
        identities = [item for node in runs.get('Verified Company', []) for item in outputs(node)]
        check('report_matches_verified_company', len(identities) == 1
              and identities[0].get('company', {}).get('provider_company_id') == report.company.provider_company_id
              and identities[0].get('company', {}).get('jurisdiction') == report.company.jurisdiction)
        check('corpus_version_matches', report.corpus_version == rag.version)
        check('four_diligence_topics', {s.topic for s in report.sections} == {
            'corporate_identity', 'financial_disclosures', 'litigation', 'regulatory_risks'})
        check('report_confidence_and_risk', report.overall_confidence == 'insufficient' and report.risk_assessment == 'Undetermined')
        check('missing_data_and_document_requests', all(s.missing_data for s in report.sections)
              and bool(report.document_requests) and bool(report.limitations))
        check('no_placeholder_links', '](#)' not in report.markdown)
        references = [ref for section in report.sections for ref in section.references]
        check('references_attributable', bool(references) and all(
            rag.validate_reference(ref.model_dump(), report.company.jurisdiction) for ref in references))
        check('source_metadata_resolves', all(
            ref.chunk_id in report.source_index
            and report.source_index[ref.chunk_id].url == ref.source_url
            and report.source_index[ref.chunk_id].document_date == ref.document_date
            and ref.source_url in report.markdown for ref in references))
        claims = [c for section in report.sections for c in section.verified_facts + section.potential_risks + section.reference_guidance]
        check('all_claim_sources_resolve', all(c.source_ids and all(i in report.source_index for i in c.source_ids) for c in claims))
        verified = [c for s in report.sections for c in s.verified_facts]
        check('facts_limited_to_fixture_consistency', bool(verified) and all(
            c.verification_status == 'synthetic_record_consistency' and all(
                report.source_index[i].kind == 'synthetic_registry' for i in c.source_ids if i in report.source_index)
            for c in verified) and all(not s.verified_facts for s in report.sections if s.topic != 'corporate_identity'))
        check('confidence_scope_explicit', all(c.confidence_basis for c in claims)
              and all(c.confidence != 'high' for s in report.sections for c in s.potential_risks + s.reference_guidance))
    return {'passed': not failures, 'execution_id': execution.get('id'),
            'last_node': execution.get('data', {}).get('resultData', {}).get('lastNodeExecuted'),
            'checks': checks, 'failed_checks': failures}
