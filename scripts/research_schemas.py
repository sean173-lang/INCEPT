"""Phase 2 contracts: no arbitrary tools, URLs, financial calls or model prompts."""
from typing import Literal
from pydantic import Field
from scripts.service_schemas import Schema, ResearchRequest, CompanyIdentity, AnnotatedSource

Topic = Literal['corporate_identity', 'financial_disclosures', 'litigation', 'regulatory_risks']
Tool = Literal['retrieve_references', 'company_research']


class RetrievalRequest(ResearchRequest):
    query: str = Field(min_length=1, max_length=500)
    topic: Topic | None = None
    top_k: int = Field(default=3, ge=1, le=5)


class Reference(Schema):
    id: str
    title: str
    jurisdiction: str
    topics: list[str]
    source_url: str
    locator: str
    document_date: str | None
    reviewed_at: str
    content_kind: Literal['curated_paraphrase']
    keywords: str
    text: str
    chunk_id: str
    content_sha256: str
    reference_not_company_evidence: Literal[True]
    retrieval_score: float


class RetrievalResponse(Schema):
    matches: list[Reference]
    corpus_version: str
    warning: str = 'Curated reference paraphrases, not company-specific evidence or a current legal opinion.'


class CreateResearchRun(ResearchRequest):
    max_iterations: int = Field(default=2, ge=1, le=2)
    topics: list[Topic] = Field(default_factory=lambda: ['corporate_identity', 'financial_disclosures', 'litigation', 'regulatory_risks'], min_length=1, max_length=4)


class RunPlan(Schema):
    run_id: str
    state: Literal['ready', 'complete']
    iteration: int
    max_iterations: int
    next_tool: Tool | None
    plan_token: str | None
    stop_reason: str | None
    development: Literal[True] = True


class ToolRequest(Schema):
    tool: Tool
    plan_token: str = Field(pattern=r'^[a-f0-9]{64}$')


class ReportClaim(Schema):
    text: str
    verification_status: Literal['synthetic_record_consistency', 'unverified_lead', 'missing_information', 'reference_guidance']
    confidence: Literal['high', 'moderate', 'low', 'insufficient']
    confidence_basis: str
    source_ids: list[str]


class ReportSection(Schema):
    topic: Topic
    verified_facts: list[ReportClaim]
    potential_risks: list[ReportClaim]
    reference_guidance: list[ReportClaim]
    missing_data: list[str]
    references: list[Reference]


class ReportSource(Schema):
    kind: Literal['synthetic_registry', 'curated_reference', 'coverage_record', 'unverified_search']
    title: str
    url: str | None = None
    document_date: str | None = None
    reviewed_at: str | None = None


class ResearchReport(Schema):
    run_id: str
    development: Literal[True] = True
    company: CompanyIdentity
    title: str = 'Development preliminary M&A due diligence report'
    risk_assessment: Literal['Undetermined'] = 'Undetermined'
    overall_confidence: Literal['insufficient'] = 'insufficient'
    sections: list[ReportSection]
    evidence: list[AnnotatedSource]
    source_index: dict[str, ReportSource]
    document_requests: list[str]
    limitations: list[str]
    iterations: int
    stop_reason: str
    corpus_version: str
    markdown: str
