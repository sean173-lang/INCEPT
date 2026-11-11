"""One allowlisted primary-source rule check. No networking or deadline arithmetic."""
from datetime import datetime, timezone
import base64
import binascii
import codecs
from hashlib import sha256
from html.parser import HTMLParser
import re
from typing import Literal
from pydantic import Field, field_validator
from scripts.service_schemas import Schema
from scripts.onboarding_schemas import OnboardingBundle, MatterInput, MandateAssessment, AssessmentFinding, AssessmentSource
from scripts.report_renderer import text

SOURCE_URL='https://www.gesetze-im-internet.de/bgb/__286.html'
RULES={
 '1':('Leistet der Schuldner auf eine Mahnung des Gläubigers nicht, die nach dem Eintritt der Fälligkeit erfolgt, so kommt er durch die Mahnung in Verzug.',
       'Under the general rule in BGB §286(1), non-performance following a creditor reminder made after maturity can establish default. Other statutory rules and exceptions require review.'),
 '4':('Der Schuldner kommt nicht in Verzug, solange die Leistung infolge eines Umstands unterbleibt, den er nicht zu vertreten hat.',
       'BGB §286(4) excludes default while non-performance results from a circumstance for which the debtor is not responsible. Attribution must be assessed from evidence.')}


class PrimaryResearchRequest(Schema):
    synthetic_data: Literal[True]
    matter: MatterInput
    bundle: OnboardingBundle|None=None
    source_url: str=Field(max_length=300)
    retrieved_at: str=Field(max_length=50)
    http_status: int|None=Field(default=None,ge=100,le=599)
    source_html: str=Field(default='',max_length=200000)
    source_bytes_base64: str=Field(default='',max_length=300000)
    source_content_type: str=Field(default='',max_length=200)
    retrieval_error: Literal['network_or_http_failure','oversized_response']|None=None

    @field_validator('synthetic_data',mode='before')
    @classmethod
    def synthetic(cls,value):
        if value is not True:raise ValueError('Only synthetic intake supported')
        return value


class VerifiedRule(Schema):
    source_id: str
    provision: str
    quote: str
    claim: str
    evidence_status: Literal['verified_source_rule_not_case_finding']='verified_source_rule_not_case_finding'


class DeadlineAnalysis(Schema):
    state: Literal['pending_lawyer_approval']='pending_lawyer_approval'
    candidate_date: str|None
    candidate_status: Literal['unverified_intake_only']='unverified_intake_only'
    confirmed_deadline: None=None
    calculated_deadline: None=None
    trigger_dates_verified: Literal[False]=False
    missing_trigger_evidence: list[str]
    source_ids: list[str]
    explanation: str


class PrimaryResearchResult(Schema):
    receipt_id: str|None=None
    status: Literal['verified','partially_verified','unavailable','not_applicable']
    source_url: str
    retrieved_at: str
    http_status: int|None
    source_sha256: str|None=None
    source_encoding: str|None=None
    source_evidence_status: str
    verified_rules: list[VerifiedRule]
    unresolved_research: list[str]
    case_findings_verified: Literal[False]=False
    max_external_requests: Literal[1]=1
    helper_performed_network_io: Literal[False]=False
    potential_deadline_analysis: DeadlineAnalysis
    enriched_assessment: MandateAssessment|None=None


class ProvisionParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.stack=[];self.paragraphs=[];self.heading=[];self.current=None
    def handle_starttag(self,tag,attrs):
        if tag in ('br','hr','img','meta','link','input'):return
        is_paragraph='jurAbsatz' in (dict(attrs).get('class') or '').split()
        self.stack.append((tag,is_paragraph))
        if is_paragraph:self.current=[]
    def handle_endtag(self,tag):
        if tag in ('br','hr','img','meta','link','input'):return
        while self.stack:
            actual,is_paragraph=self.stack.pop()
            if is_paragraph and self.current is not None:
                self.paragraphs.append(normal(' '.join(self.current)));self.current=None
            if actual==tag:break
    def handle_startendtag(self,tag,attrs):
        if tag not in ('br','hr','img','meta','link','input'):
            self.handle_starttag(tag,attrs);self.handle_endtag(tag)
    def handle_data(self,data):
        if any(t in ('script','style') for t,_ in self.stack):return
        if any(t=='h1' for t,_ in self.stack):self.heading.append(data)
        if self.current is not None:self.current.append(data)


def normal(value):return ' '.join(value.split())


def decoded_source(request):
    if not request.source_bytes_base64:
        if '\ufffd' in request.source_html:raise ValueError('Source text contains decoding replacement characters.')
        return request.source_html,request.source_html.encode('utf-8'),'submitted_unicode_text'
    if request.source_html:raise ValueError('Competing source text and bytes are ambiguous.')
    try:raw=base64.b64decode(request.source_bytes_base64,validate=True)
    except (ValueError,binascii.Error):raise ValueError('Invalid source byte encoding') from None
    if len(raw)>200000:raise ValueError('Oversized source bytes')
    header=re.findall(r'charset\s*=\s*["\']?([A-Za-z0-9_-]+)',request.source_content_type,re.I)
    meta=re.findall(r'charset\s*=\s*["\']?([A-Za-z0-9_-]+)',raw[:4096].decode('ascii',errors='ignore'),re.I)
    try:declared={codecs.lookup(v).name for v in header+meta}
    except LookupError:raise ValueError('Unsupported declared source charset') from None
    if len(declared)>1:raise ValueError('Conflicting source charset declarations')
    encoding=next(iter(declared),'utf-8')
    if encoding not in ('utf-8','iso8859-1','cp1252'):raise ValueError('Unapproved source charset')
    try:html=raw.decode(encoding,errors='strict')
    except UnicodeError:raise ValueError('Source bytes cannot be decoded without guessing') from None
    if '\ufffd' in html:raise ValueError('Source decoding is lossy')
    return html,raw,encoding


def relevant(matter):
    if matter.governing_law not in (None,'Germany'):return False
    value=(matter.title+' '+matter.summary+' '+matter.requested_scope).casefold()
    return bool(re.search(r'vertrag|liefer|contract',value) and re.search(r'forderung|zahlung|payment|invoice',value))


def verify_research(request,*,now=None):
    now=now or datetime.now(timezone.utc)
    unresolved=[];rules=[];digest=None;status='unavailable';encoding=None
    uk_without_explicit_law=(request.bundle is not None and request.bundle.client.jurisdiction in ('UK','United Kingdom') and request.matter.governing_law is None)
    if not relevant(request.matter) or uk_without_explicit_law:status='not_applicable';unresolved.append('This bounded research tool does not cover the supplied matter or unresolved governing law.')
    elif request.source_url!=SOURCE_URL:unresolved.append('Source URL is not the exact allowlisted official provision; no claim verified.')
    elif request.retrieval_error:unresolved.append('Orchestrator reports '+request.retrieval_error+'; source research unavailable.')
    elif request.http_status!=200:unresolved.append('Official source did not return HTTP 200; no retry or fallback result is treated as evidence.')
    else:
        try:
            when=datetime.fromisoformat(request.retrieved_at.replace('Z','+00:00'))
            if when.tzinfo is None or not 0<=(now-when).total_seconds()<=86400:raise ValueError()
        except (ValueError,TypeError):unresolved.append('Retrieval timestamp is invalid, future or older than the one-day verification window.')
        if not unresolved:
            try:html,raw,encoding=decoded_source(request)
            except ValueError:
                html='';raw=b'';unresolved.append('Source decoding is invalid, ambiguous or unsupported; no wording reconstructed.')
            parser=ProvisionParser();parser.feed(html)
            heading=normal(' '.join(parser.heading))
            if not all(part in heading for part in ('Bürgerliches Gesetzbuch','§ 286','Verzug des Schuldners')):
                unresolved.append('Retrieved page is unrelated or its expected provision heading changed.')
            else:
                digest=sha256(raw).hexdigest()
                for number,(quote,claim) in RULES.items():
                    matches=[p for p in parser.paragraphs if p.startswith('('+number+') ')]
                    if len(matches)!=1 or not matches[0].startswith('('+number+') '+normal(quote)):
                        unresolved.append('BGB §286('+number+') expected wording is absent, ambiguous or changed; claim withheld.')
                        continue
                    rules.append(VerifiedRule(source_id='primary:bgb286:'+number+':'+digest[:16],provision='BGB §286('+number+')',quote=quote,claim=claim))
                status='verified' if len(rules)==len(RULES) else 'partially_verified' if rules else 'unavailable'
    deadline=DeadlineAnalysis(candidate_date=request.matter.claimed_deadline,
        missing_trigger_evidence=['Original contract and evidence of maturity/due date.','Original demand/reminder and evidence of receipt.','Any original court document and service evidence, if applicable.','Applicability of statutory exceptions and responsibility for non-performance.'],
        source_ids=[r.source_id for r in rules],explanation='No legally confirmed date is calculated. The intake date is a candidate only. BGB §286 does not itself supply missing trigger dates; special rules and procedural deadlines need lawyer review.')
    enriched=request.bundle.assessment.model_copy(deep=True) if request.bundle else None
    if request.bundle and request.bundle.matter.model_dump(exclude={'matter_id','client_id','status'})!=request.matter.model_dump():
        # Never enrich a different matter with this case's source selection.
        raise ValueError('Research matter and onboarding bundle do not match')
    if enriched:
        lines=['','## Bounded primary-source research','', 'Research status: '+status+'. Case merits remain unverified.']
        for rule in rules:
            enriched.sources.append(AssessmentSource(source_id=rule.source_id,kind='legal_reference',locator=rule.provision,content=rule.quote,url=SOURCE_URL,reviewed_at=now.date().isoformat(),document_date=None))
            enriched.guidance.append(AssessmentFinding(description=rule.claim+' Verified source wording only; not a finding about this matter.',status='reference_guidance',source_ids=[rule.source_id]))
            lines+=['- '+text(rule.claim)+' ['+rule.source_id+']', '- Source: ['+text(rule.provision)+']('+SOURCE_URL+'); retrieved '+text(request.retrieved_at)+'; source SHA256 '+text(digest)+'.']
        lines+=['- Unavailable research: '+text(v) for v in unresolved]
        lines+=['','## Potential Deadline Analysis','', 'State: pending_lawyer_approval. Intake candidate: '+text(deadline.candidate_date)+'. Confirmed deadline: unavailable. Calculated deadline: none.', text(deadline.explanation)]
        lines+=['- Missing: '+text(v) for v in deadline.missing_trigger_evidence]
        enriched.missing_information+=deadline.missing_trigger_evidence+unresolved
        enriched.content_markdown+='\n'.join(lines)+'\n'
    return PrimaryResearchResult(status=status,source_url=request.source_url,retrieved_at=request.retrieved_at,http_status=request.http_status,
        source_sha256=digest,source_encoding=encoding,source_evidence_status='orchestrator_retrieved_text_checked_against_reviewed_provision_wording' if rules else 'unavailable_not_evidence_of_legal_position',
        verified_rules=rules,unresolved_research=unresolved,potential_deadline_analysis=deadline,enriched_assessment=enriched)
