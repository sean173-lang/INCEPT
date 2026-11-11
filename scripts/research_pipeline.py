"""Bounded, rule-based research tools. n8n calls plan/step; no recursive loop."""
import hashlib
from threading import RLock
import uuid

from scripts.company_service import ServiceError
from scripts.local_rag import LocalRAG, QUERIES
from scripts.research_schemas import RunPlan, ResearchReport, ReportSection, ReportClaim, ReportSource
from scripts.service_schemas import ResearchRequest
from scripts.report_renderer import text
from scripts.api_usage import use_tracker

DOCUMENT_REQUESTS = ['Current register extract, constitutional documents, ownership and signing-authority evidence.', 'Original legal documents, case identifiers and dated regulator correspondence.', 'Current sanctions/insolvency screening with entity identifiers; not automatically performed.']

MISSING = {
    'corporate_identity': 'Constitutional documents, beneficial ownership and signing authority have not been independently checked.',
    'litigation': 'Original claims, judgments and current litigation status have not been checked.',
    'regulatory_risks': 'No transaction facts, merger-control analysis, current sanctions or regulator decisions were verified.',
}


class ResearchPipeline:
    def __init__(self, companies, rag=None):
        self.companies = companies
        self.rag = rag or LocalRAG()
        self.runs = {}
        self.lock = RLock()

    def identity(self, verification_id):
        with self.companies.lock:
            stored = self.companies.verified.get(verification_id)
        if not stored:
            raise ServiceError(409, 'verification_required', 'A verified company handle is required.')
        if self.companies.clock() - stored[2] >= self.companies.verification_ttl:
            raise ServiceError(409, 'verification_expired', 'Company verification has expired.')
        return stored[0]

    def development_only(self):
        if not self.companies.tracker.development:
            raise ServiceError(403, 'development_required', 'Phase 2 research is restricted to development fixtures; no live tool execution is allowed.')

    def retrieve(self, request):
        self.development_only()
        company = self.identity(request.verification_id)
        return {'matches': self.rag.query(request.query, company.jurisdiction, request.topic, request.top_k),
                'corpus_version': self.rag.version}

    def create(self, request):
        self.development_only()
        company = self.identity(request.verification_id)
        identifier = uuid.uuid4().hex
        with self.lock:
            self.runs[identifier] = {'id': identifier, 'verification_id': request.verification_id, 'company': company,
                                     'max_iterations': min(request.max_iterations, 2), 'iteration': 0,
                                     'topics': list(dict.fromkeys(request.topics)), 'references': {}, 'research': None,
                                     'completed': {}, 'failed': False}
            return self._plan(self.runs[identifier])

    def _run(self, identifier):
        self.development_only()
        run = self.runs.get(identifier)
        if run is None:
            raise ServiceError(404, 'research_run_not_found', 'The research run does not exist in this service session.')
        self.identity(run['verification_id'])
        return run

    def _plan(self, run):
        reason = None
        tool = None
        if run['failed']:
            reason = 'tool_failed_manual_review'
        elif run['iteration'] >= run['max_iterations']:
            reason = 'iteration_limit' if run['research'] is None else 'approved_tools_complete'
        elif 'retrieve_references' not in run['completed']:
            tool = 'retrieve_references'
        elif 'company_research' not in run['completed']:
            tool = 'company_research'
        else:
            reason = 'no_new_approved_actions'
        token = hashlib.sha256(f"{run['id']}:{run['iteration']}:{tool}".encode()).hexdigest() if tool else None
        return RunPlan(run_id=run['id'], state='ready' if tool else 'complete', iteration=run['iteration'],
                       max_iterations=run['max_iterations'], next_tool=tool, plan_token=token, stop_reason=reason)

    def plan(self, identifier):
        with self.lock:
            return self._plan(self._run(identifier))

    def step(self, identifier, request):
        with self.lock:
            run = self._run(identifier)
            # Exact replay returns current state; it never repeats tool work.
            if run['completed'].get(request.tool) == request.plan_token:
                return self._plan(run)
            plan = self._plan(run)
            if request.tool != plan.next_tool or request.plan_token != plan.plan_token:
                raise ServiceError(409, 'research_action_rejected', 'Action is stale, out of order or outside the approved bounded plan.')
            run['iteration'] += 1  # Reserve before execution, even on failure.
            run['completed'][request.tool] = request.plan_token
            try:
                if request.tool == 'retrieve_references':
                    for topic in run['topics']:
                        run['references'][topic] = self.rag.query(QUERIES[topic], run['company'].jurisdiction, topic, 3)
                elif request.tool == 'company_research':
                    with use_tracker(self.companies.tracker):
                        run['research'] = self.companies.research(ResearchRequest(verification_id=run['verification_id']))
            except Exception:
                run['failed'] = True
                # Preserve partial results; no exception text enters reports.
            return self._plan(run)

    def report(self, identifier):
        with self.lock:
            run = self._run(identifier)
            plan = self._plan(run)
            if plan.state != 'complete':
                raise ServiceError(409, 'research_incomplete', 'The bounded research plan must stop before report generation.')
            sections = []
            evidence = run['research'].sources if run['research'] else []
            source_id = 'fixture:registry:' + run['company'].provider_company_id
            source_index = {source_id: ReportSource(kind='synthetic_registry', title='Synthetic registry identity fixture')}
            for index, item in enumerate(evidence, 1):
                source_index[f'company-search:{index}'] = ReportSource(kind='unverified_search', title=item.source.title or 'Untitled search excerpt',
                                                                 url=item.source.url, document_date=item.source.published_date)
            for topic in run['topics']:
                references = run['references'].get(topic, [])
                for ref in references:
                    if not self.rag.validate_reference(ref, run['company'].jurisdiction):
                        raise ServiceError(409, 'citation_validation_failed', 'A reference failed exact corpus attribution.')
                    source_index[ref['chunk_id']] = ReportSource(kind='curated_reference', title=ref['title'], url=ref['source_url'],
                                                                document_date=ref['document_date'], reviewed_at=ref['reviewed_at'])
                coverage_id = f"coverage:{identifier}:{topic}"
                source_index[coverage_id] = ReportSource(kind='coverage_record', title='This development run: ' + MISSING[topic])
                facts = []
                if topic == 'corporate_identity':
                    facts.append(ReportClaim(text='The synthetic company identity matched provider-record details and available registration constraints.',
                                verification_status='synthetic_record_consistency', confidence='high',
                                confidence_basis='High confidence only in fixture-record consistency, not real-world identity.', source_ids=[source_id]))
                risks = [ReportClaim(text=MISSING[topic], verification_status='missing_information', confidence='insufficient',
                                    confidence_basis='Missing evidence cannot establish that wrongdoing or legal liability exists.',
                                    source_ids=[coverage_id])]
                if topic in ('litigation', 'regulatory_risks'):
                    for index, item in enumerate(evidence):
                        if item.usable and item.legal_evidence == 'unverified_allegation':
                            risks.append(ReportClaim(text='A search lead contains allegation language; no legal finding or current proceeding status is verified.',
                                        verification_status='unverified_lead', confidence='low',
                                        confidence_basis='Search excerpts require original-source verification.', source_ids=[f'company-search:{index+1}']))
                missing = [MISSING[topic]]
                if not references:
                    missing.append('No relevant local reference passages were retrieved for this topic.')
                elif any(ref['document_date'] is None for ref in references):
                    missing.append('Some reference document dates are unknown; check current official text before reliance.')
                if run['research'] is None:
                    missing.append('The company research tool was not completed.')
                guidance = [ReportClaim(text=ref['text'], verification_status='reference_guidance', confidence='moderate',
                                        confidence_basis='Exact attribution to a curated card; not a verified legal opinion or company finding.',
                                        source_ids=[ref['chunk_id']]) for ref in references]
                sections.append(ReportSection(topic=topic, verified_facts=facts, potential_risks=risks, reference_guidance=guidance,
                                              missing_data=missing, references=references))
            limitations = ['Development fixtures are not real company evidence.',
                           'Reference cards are curated paraphrases, not verbatim statutory text; source law may have changed.',
                           'General legal guidance cannot establish company-specific conduct or transaction applicability.',
                           'Unknown original document dates remain null; review dates are not enactment or event dates.',
                           'Financial endpoints, paid providers, embeddings and model-generated conclusions are disabled.',
                           'Corpus and evidence coverage are deliberately small; original documents and professional review remain necessary.']
            report = ResearchReport(run_id=identifier, company=run['company'], sections=sections, evidence=evidence,
                                    source_index=source_index,
                                    document_requests=DOCUMENT_REQUESTS, limitations=limitations, iterations=run['iteration'],
                                    stop_reason=plan.stop_reason, corpus_version=self.rag.version, markdown='')
            report.markdown = render_research_report(report, source_id)
            return report


def render_research_report(report, registry_id):
    lines = ['# Development due diligence report', '', '**Synthetic data only.**', '',
             '## Executive Summary', '', 'Overall confidence: insufficient. Evidence gaps remain; no real-company legal finding is verified.',
             '', '## Corporate Identity', '', f'Company: {text(report.company.name)}; provider ID: {text(report.company.provider_company_id)}.',
             f'Registration: {text(report.company.registration_number)}; court: {text(report.company.register_court)}.',
             f'Source: {text(registry_id)} (synthetic provider fixture).', '']
    for section in report.sections:
        lines.extend(['## ' + section.topic.replace('_', ' ').title(), ''])
        for fact in section.verified_facts + section.potential_risks:
            lines.append('- ' + text(fact.text) + ' Confidence: ' + fact.confidence + '. ' + text(fact.confidence_basis))
        lines.extend(['', 'Missing data:'] + ['- ' + text(item) for item in section.missing_data] + [''])
        for ref in section.references:
            lines.extend([f"- [{text(ref.title)}](<{ref.source_url}>) — {text(ref.locator)}; document date: {ref.document_date or 'unknown'}; reviewed: {ref.reviewed_at}; chunk: {text(ref.chunk_id)}.",
                          '  Local curated reference: ' + text(ref.text)])
    lines.extend(['', '## Company Research Sources', ''])
    for index, source in enumerate(report.evidence, 1):
        lines.append(f'- company-search:{index}: {text(source.source.url)}; usable: {source.usable}; unverified excerpt.')
    if not report.evidence:
        lines.append('No company-specific search excerpts returned by the development fixtures; this is not proof of no adverse matters.')
    lines.extend(['', '## Document Requests', ''] + ['- ' + item for item in report.document_requests])
    lines.extend(['', '## Source Index', ''])
    for identifier, source in report.source_index.items():
        lines.append('- ' + text(identifier) + ': ' + text(source.title) + '; type: ' + source.kind
                     + ('; ' + text(source.url) if source.url else '')
                     + '; document date: ' + (source.document_date or 'unknown'))
    lines.extend(['', '## Limitations', ''] + ['- ' + item for item in report.limitations])
    lines.extend(['', '## Final Risk Assessment', '', '**Undetermined**. Financial indicators, legal findings, missing information and coverage must be assessed separately.',
                  f'Iterations: {report.iterations}; stop reason: {report.stop_reason}.', ''])
    return '\n'.join(lines)
