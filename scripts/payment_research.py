"""Allowlisted payment-dispute wording checks. The orchestrator fetches sources."""
from datetime import datetime,timezone
from hashlib import sha256
from pathlib import Path
from typing import Literal
from pydantic import Field
from scripts.local_rag import LocalRAG
from scripts.primary_research import ProvisionParser,normal,decoded_source
from scripts.service_schemas import Schema
from scripts.onboarding_schemas import AssessmentSource

CORPUS=Path(__file__).resolve().parents[1]/'references/payment_dispute.json'

class PaymentSourceRequest(Schema):
    provision: Literal['611','614','631','633','634','640','641','632a','320','433','434','437','439','280','281','286','323']
    source_url: str=Field(max_length=200)
    retrieved_at: str=Field(max_length=50)
    http_status: int
    source_html: str=Field(default='',max_length=200000)
    source_bytes_base64: str=Field(default='',max_length=300000)
    source_content_type: str=Field(default='',max_length=200)


def verify_payment_source(request):
    card=next(c for c in LocalRAG(CORPUS).chunks.values() if c['id']=='payment-bgb-'+request.provision)
    when=datetime.fromisoformat(request.retrieved_at.replace('Z','+00:00'))
    if when.tzinfo is None or not 0<=(datetime.now(timezone.utc)-when).total_seconds()<=86400:raise ValueError('Invalid retrieval time')
    html,raw,encoding=decoded_source(request)
    parser=ProvisionParser();parser.feed(html)
    retrieved_text=normal(' '.join(parser.paragraphs))
    valid=request.source_url==card['source_url'] and request.http_status==200 and ('§ '+request.provision in normal(' '.join(parser.heading)) or '§'+request.provision in normal(' '.join(parser.heading))) and normal(card['text']) in retrieved_text
    source=AssessmentSource(source_id=card['chunk_id'],kind='legal_reference',locator=card['locator'],content=card['text'],url=card['source_url'],reviewed_at=card['reviewed_at'],document_date=card['document_date']) if valid else None
    return {'status':'wording_verified' if valid else 'unavailable','source':source.model_dump() if source else None,
            'source_url':request.source_url,'retrieved_at':request.retrieved_at,'http_status':request.http_status,
            'source_sha256':sha256(raw).hexdigest(),'source_encoding':encoding,'evidence_status':'submitted_official_wording_not_independent_acquisition' if valid else 'unavailable',
            'case_finding_verified':False,'confirmed_deadline':None,'lawyer_review_required':True,
            'limitation':'Contract classification, performance, acceptance, maturity and objections require original evidence. No default or deadline conclusion.'}
