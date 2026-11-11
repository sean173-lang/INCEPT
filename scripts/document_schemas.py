"""Document inputs describe supplied draft facts, never approval or issuance commands."""
from typing import Literal
from datetime import date
from pydantic import Field,field_validator,model_validator
from scripts.service_schemas import Schema

Status=Literal['DRAFT_COMPLETE_FOR_LAWYER_REVIEW','MISSING_INFORMATION','LEGAL_REVIEW_REQUIRED','NOT_READY_FOR_ISSUANCE','GENERATION_FAILED']

class DraftText(Schema):
    @field_validator('*',mode='before',check_fields=False)
    @classmethod
    def clean(cls,value):
        if isinstance(value,str):
            if not value.strip() or any(ord(c)<32 or ord(c)==127 for c in value):raise ValueError('Nonempty plain text without control characters required')
            return value.strip()
        return value

class Representative(DraftText):
    name: str=Field(min_length=3,max_length=200)
    role: str=Field(min_length=3,max_length=150)
    authority_status: Literal['unknown','asserted','evidence_checked']='unknown'
    evidence_reference: str|None=Field(default=None,max_length=400)
    @model_validator(mode='after')
    def evidence(self):
        if self.authority_status=='evidence_checked' and not self.evidence_reference:raise ValueError('Evidence checks require a reference')
        return self

class DocumentFirmPolicy(DraftText):
    policy_id: str=Field(min_length=3,max_length=100)
    net_hourly_rate: str=Field(pattern=r'^\d{1,5}(?:\.\d{1,2})?$')
    billing_method: Literal['actual_minutes','specified_increment','unknown']='unknown'
    billing_increment_minutes: int|None=Field(default=None,ge=1,le=60)
    time_recording: str|None=Field(default=None,max_length=600)
    expenses_terms: str|None=Field(default=None,max_length=600)
    payment_terms: str|None=Field(default=None,max_length=600)
    other_professionals_terms: str|None=Field(default=None,max_length=600)
    tax_identifier: str|None=Field(default=None,max_length=80)
    payment_instructions: str|None=Field(default=None,max_length=500)
    vat_configuration_confirmed: bool=False
    @model_validator(mode='after')
    def increment(self):
        if self.billing_method=='specified_increment' and self.billing_increment_minutes is None:raise ValueError('Explicit increment required')
        if self.billing_method!='specified_increment' and self.billing_increment_minutes is not None:raise ValueError('Unexpected increment; no implicit rounding')
        return self

class DocumentOptions(DraftText):
    representative: Representative|None=None
    representation_scope: Literal['unspecified','out_of_court','court','both']='unspecified'
    requested_ancillary_powers: list[Literal['settlement','receive_money','delegation','self_dealing']]=Field(default_factory=list,max_length=4)
    place: str|None=Field(default=None,max_length=150)
    engagement_law: Literal['Germany','unknown']='unknown'
    firm_policy: DocumentFirmPolicy|None=None
    invoice_number: str|None=Field(default=None,max_length=80)
    invoice_issue_date: str|None=None
    payment_received_date: str|None=None
    recipient_business_status: Literal['consumer','business','unknown']='unknown'
    supplier_domestic: bool|None=None
    recipient_domestic: bool|None=None
    previous_year_turnover_le_800000: bool|None=None
    @field_validator('payment_received_date','invoice_issue_date')
    @classmethod
    def payment_date(cls,value):
        if value is not None:date.fromisoformat(value)
        return value

class DocumentIssue(Schema):
    code: str
    field: str
    description: str
    severity: Literal['missing','review','error']
    source_ids: list[str]=Field(default_factory=list)
