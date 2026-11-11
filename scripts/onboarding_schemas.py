"""Intake and document contracts; no caller can approve actions or spend credits."""
from datetime import date
from decimal import Decimal
from typing import Literal
from scripts.review_warnings import ReviewWarning
from pydantic import Field, ValidationInfo, field_validator, model_validator
from scripts.service_schemas import Schema
from scripts.document_schemas import DocumentOptions,DocumentIssue,Status


class IntakeText(Schema):
    @field_validator('*',mode='before',check_fields=False)
    @classmethod
    def no_controls(cls,value,info:ValidationInfo):
        if isinstance(value,str):
            allowed={'\n','\r','\t'} if info.field_name in ('summary','requested_scope') else set()
            if any((ord(c)<32 and c not in allowed) or ord(c)==127 for c in value):raise ValueError('Control characters are not permitted')
            return value.strip()
        return value


class ClientInput(IntakeText):
    name: str|None=Field(default=None,min_length=3,max_length=200)
    address: str|None=Field(default=None,max_length=400)
    email: str|None=Field(default=None,max_length=200,pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    jurisdiction: Literal['Germany','United Kingdom','UK','unknown','unsupported']='Germany'
    client_type: Literal['individual','company','unknown']='unknown'
    registration_number: str|None=Field(default=None,max_length=80)
    register_court: str|None=Field(default=None,max_length=150)
    register_type: Literal['HRB','HRA']|None=None
    approved_provider_id: str|None=Field(default=None,max_length=100,pattern=r'^[A-Za-z0-9][A-Za-z0-9_-]*$')


class FirmInput(ClientInput):
    lawyer_name: str|None=Field(default=None,min_length=3,max_length=150)


class MatterInput(IntakeText):
    title: str=Field(min_length=3,max_length=200)
    summary: str=Field(min_length=10,max_length=6000)
    requested_scope: str=Field(min_length=5,max_length=1000)
    opposing_parties: list[str]=Field(default_factory=list,max_length=10)
    claimed_deadline: str|None=Field(default=None,max_length=10)
    deadline_source: str|None=Field(default=None,max_length=500)
    governing_law: Literal['Germany','United Kingdom','unknown']|None=None

    @field_validator('opposing_parties')
    @classmethod
    def parties(cls,values):
        if any(not v.strip() or len(v)>200 or any(ord(c)<32 for c in v) for v in values):raise ValueError('Invalid party name')
        return values

    @model_validator(mode='after')
    def deadline(self):
        if self.claimed_deadline:
            date.fromisoformat(self.claimed_deadline)
            if not self.deadline_source:raise ValueError('Claimed deadlines need source descriptions')
        elif self.deadline_source:raise ValueError('Deadline source requires a claimed date')
        return self


class FeeInput(IntakeText):
    net_hourly_rate: str|None=Field(default=None,pattern=r'^\d{1,5}(?:\.\d{1,2})?$',max_length=8)
    proposed_advance_hours: str|None=Field(default=None,pattern=r'^\d{1,4}(?:\.\d{1,2})?$',max_length=8)
    currency: Literal['EUR']='EUR'
    vat_mode: Literal['unknown','taxable','exempt']
    vat_percent: str|None=Field(default=None,pattern=r'^\d{1,3}(?:\.\d{1,2})?$')
    vat_basis: str|None=Field(default=None,max_length=500)

    @model_validator(mode='after')
    def amounts(self):
        if self.net_hourly_rate is None:
            if self.proposed_advance_hours is not None or self.vat_mode!='unknown' or self.vat_percent is not None or self.vat_basis is not None:raise ValueError('Rate and tax treatment require supplied fee information')
            return self
        if Decimal(self.net_hourly_rate)<=0:raise ValueError('Hourly rate must be positive')
        if self.proposed_advance_hours is not None and Decimal(self.proposed_advance_hours)<=0:raise ValueError('Advance hours must be positive')
        if self.vat_mode=='taxable':
            if self.vat_percent is None or not 0<Decimal(self.vat_percent)<=100 or not self.vat_basis:
                raise ValueError('Explicit positive VAT percentage and supplied treatment basis required')
        elif self.vat_mode=='exempt':
            if self.vat_percent is not None or not self.vat_basis:raise ValueError('Exemption needs supplied basis; do not supply a rate')
        elif self.vat_percent is not None or self.vat_basis is not None:
            raise ValueError('Unknown VAT must not assert a rate or basis')
        return self


class OnboardingRequest(IntakeText):
    document_options: DocumentOptions|None=None
    synthetic_data: bool=False
    idempotency_key: str=Field(min_length=8,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')
    client: ClientInput
    firm: FirmInput|None=None
    matter: MatterInput
    fees: FeeInput|None=None
    draft_date: str|None=Field(default=None,min_length=10,max_length=10)

    @field_validator('draft_date')
    @classmethod
    def iso_date(cls,value):
        if value is not None:date.fromisoformat(value)
        return value


class ClientRecord(ClientInput):
    client_id: str
    synthetic_data: bool=False


class MatterRecord(MatterInput):
    matter_id: str
    client_id: str
    status: Literal['draft_pending_lawyer_review']='draft_pending_lawyer_review'


class DraftDocument(Schema):
    document_version: int=1
    template_id: str|None=None
    template_version: str|None=None
    source_version: str|None=None
    completeness_status: Status='LEGAL_REVIEW_REQUIRED'
    validation_issues: list[DocumentIssue]=Field(default_factory=list)
    missing_information: list[str]=Field(default_factory=list)
    lawyer_review_questions: list[str]=Field(default_factory=list)
    legal_source_ids: list[str]=Field(default_factory=list)
    ready_for_issuance: Literal[False]=False
    legally_approved: Literal[False]=False
    kind: Literal['vollmacht','fee_agreement','advance_invoice']
    state: Literal['pending_lawyer_approval']='pending_lawyer_approval'
    content_markdown: str


class AdvanceCalculation(Schema):
    hours: str|None=None
    net_hourly_rate: str|None=None
    currency: Literal['EUR']='EUR'
    net_fee: str
    vat_mode: Literal['unknown','taxable','exempt']
    vat_percent: str|None
    vat_amount: str|None
    gross_total: str|None
    tax_status: Literal['supplied_treatment_unverified','not_calculated','supplied_demo_treatment_unverified']='not_calculated'
    work_performed: Literal[False]=False


class AssessmentFinding(Schema):
    description: str
    status: Literal['unverified_intake_statement','reference_guidance','missing_information']
    source_ids: list[str]


class AssessmentSource(Schema):
    source_id: str
    kind: Literal['intake','synthetic_intake','legal_reference','corporate_record','public_search_lead']
    locator: str
    content: str
    url: str|None=None
    reviewed_at: str|None=None
    document_date: str|None=None


class MandateAssessment(Schema):
    review_warnings: list[ReviewWarning] = Field(default_factory=list)
    title: str='Preliminary Mandate Assessment'
    conclusion: Literal['lawyer_review_required']='lawyer_review_required'
    confidence: Literal['insufficient_for_legal_conclusions']='insufficient_for_legal_conclusions'
    factual_findings: list[AssessmentFinding]
    guidance: list[AssessmentFinding]
    missing_information: list[str]
    sources: list[AssessmentSource]
    corpus_version: str
    content_markdown: str


class ProposedAction(Schema):
    action_id: str
    kind: Literal['task','potential_deadline','draft_email']
    state: Literal['pending_lawyer_approval']='pending_lawyer_approval'
    title: str
    detail: str
    source_ids: list[str]
    due_date: str|None=None
    candidate_date: str|None=None
    recipient: str|None=None
    subject: str|None=None
    body: str|None=None
    executed: Literal[False]=False


class OnboardingBundle(Schema):
    document_generation_context: DocumentOptions|None=None
    schema_version: Literal[1]=1
    synthetic_data: bool=False
    status: Literal['preview_pending_lawyer_approval']='preview_pending_lawyer_approval'
    client: ClientRecord
    matter: MatterRecord
    advance: AdvanceCalculation|None=None
    documents: list[DraftDocument]
    assessment: MandateAssessment
    proposed_actions: list[ProposedAction]
    external_actions_executed: Literal[False]=False
    paid_api_calls: Literal[0]=0
