"""Phase 1 HTTP contracts. Extra fields cannot override server cost controls."""
import re
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Jurisdiction = Literal['Germany', 'UK']
VerificationStatus = Literal['verified', 'ambiguous', 'not_found', 'verification_failed']


class Schema(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class CompanyInput(Schema):
    company_name: str = Field(min_length=1, max_length=200)
    jurisdiction: Jurisdiction

    @field_validator('company_name', mode='after')
    @classmethod
    def clean_name(cls, value):
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError('Control characters are not permitted')
        value = ' '.join(value.split())
        if not value:
            raise ValueError('Company name is required')
        return value


class VerificationRequest(CompanyInput):
    provider_company_id: str | None = Field(default=None, min_length=1, max_length=100, pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')
    registration_number: str | None = Field(default=None, min_length=1, max_length=80)
    register_court: str | None = Field(default=None, min_length=1, max_length=150)
    register_type: str | None = Field(default=None, pattern=r'^(HRB|HRA)$')

    @field_validator('registration_number', 'register_court')
    @classmethod
    def clean_registration(cls, value):
        if value is None:
            return value
        if any(ord(c) < 32 or ord(c) == 127 for c in value) or not value.strip():
            raise ValueError('Non-empty registration text without controls is required')
        return ' '.join(value.split())

    @model_validator(mode='after')
    def country_constraints(self):
        if self.jurisdiction == 'UK':
            if self.provider_company_id and not re.fullmatch(r'[A-Za-z0-9]{8}', self.provider_company_id):
                raise ValueError('UK company identifiers must contain eight letters/digits')
            if self.register_type or self.register_court:
                raise ValueError('German register court/type do not apply to UK requests')
        elif self.provider_company_id and self.provider_company_id.startswith('GB-'):
            raise ValueError('Identifier conflicts with German jurisdiction')
        return self


class Candidate(Schema):
    provider_company_id: str
    name: str
    jurisdiction: Jurisdiction
    registration_number: str | None = None
    register_court: str | None = None
    register_type: str | None = None


class SearchResponse(Schema):
    status: Literal['candidates_found', 'not_found']
    candidates: list[Candidate]
    message: str
    development: bool


class CompanyIdentity(Candidate):
    provider: Literal['OpenRegister', 'Companies House']
    retrieved_at: str | None = None


class VerificationResponse(Schema):
    status: VerificationStatus
    verification_id: str | None = None
    company: CompanyIdentity | None = None
    candidates: list[Candidate] = Field(default_factory=list)
    checks: dict[str, bool] = Field(default_factory=dict)
    message: str
    development: bool
    verification_scope: Literal['provider_record_identity'] = 'provider_record_identity'


class ResearchRequest(Schema):
    verification_id: str = Field(pattern=r'^[a-f0-9]{32}$')


class ResearchSource(Schema):
    title: str | None = None
    url: str | None = None
    content: str | None = None
    score: float | None = None
    published_date: str | None = None


class AnnotatedSource(Schema):
    source: ResearchSource
    source_type: Literal['official', 'third_party', 'unknown']
    identity: Literal['unrelated', 'possible_match', 'unverified']
    freshness: str
    usable: bool
    registration_number_match: bool
    legal_evidence: str
    litigation_status: str
    verified_legal_finding: Literal[False]


class ResearchResponse(Schema):
    status: Literal['completed'] = 'completed'
    verification_id: str
    company: CompanyIdentity
    sources: list[AnnotatedSource]
    coverage_note: str
    missing_evidence: list[str]
    risk_assessment: Literal['Undetermined'] = 'Undetermined'
    development: bool


class ErrorDetail(Schema):
    code: str
    message: str
    retryable: bool = False
    fields: list[str] = Field(default_factory=list)


class ErrorResponse(Schema):
    status: Literal['verification_failed'] = 'verification_failed'
    error: ErrorDetail


class UsageResponse(Schema):
    session_id: str
    run_openregister_credits_estimated: int
    run_tavily_searches: int
    session_spending_estimated: str | None
    known_cost_subtotal_estimated: str
    currency: str
    cost_display: str
    unknown_cost_reservations: int
    billing_confirmed: Literal[False]
