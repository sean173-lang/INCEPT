"""Optional corporate intake intelligence reusing existing adapters; cache misses cannot call APIs."""
import copy
from datetime import datetime,timezone
import hashlib
import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from pydantic import Field,field_validator
from scripts.service_schemas import Schema,VerificationRequest,ResearchRequest
from scripts.onboarding_schemas import ClientInput
from scripts.api_usage import UsageTracker,UsageBlocked,use_tracker
from scripts.corporate_cache import CorporateCacheRecord, captured_record
from scripts.review_warnings import ReviewWarning, corporate_warnings
from scripts.company_service import CompanyService
from scripts.local_rag import LocalRAG
from scripts.report_renderer import text

ROOT=Path(__file__).resolve().parent.parent
DEMO=ROOT/'references/incept_corporate_demo.json'


class CorporateRequest(Schema):
    synthetic_data: Literal[True]
    client_id: str=Field(min_length=1,max_length=150)
    matter_id: str=Field(min_length=1,max_length=150)
    client: ClientInput
    source_policy: Literal['cache_only','approved_demo_fixture']='cache_only'
    max_external_requests: Literal[0]=0
    max_cached_operations: int=Field(default=3,ge=1,le=3)
    max_search_results: int=Field(default=5,ge=1,le=5)

    @field_validator('synthetic_data',mode='before')
    @classmethod
    def explicit_demo(cls,value):
        if value is not True:raise ValueError('Explicit synthetic mandate acknowledgement required')
        return value


class CorporateClaim(Schema):
    description: str
    category: Literal['REPORTED','CACHED','UNVERIFIED','UNAVAILABLE','NEEDS_REVIEW']
    source_ids: list[str]


class CorporateSource(Schema):
    source_id: str
    provider: str
    source_type: Literal['official','third_party','unknown']|None=None
    locator: str
    retrieved_at: str|None=None
    url: str|None=None
    published_date: str|None=None
    category: Literal['CACHED','UNVERIFIED']
    freshness: str
    synthetic: bool
    cache_accessed_at: str|None=None
    cache_age_seconds: float|None=None
    verification_status: str = 'unverified'


class CorporateResult(Schema):
    client_id: str
    matter_id: str
    status: Literal['not_applicable','CACHED','UNVERIFIED','UNAVAILABLE','NEEDS_REVIEW']
    identity_verification_status: str
    provider: str|None=None
    verified_legal_name: str|None=None
    registration_number: str|None=None
    register_authority: str|None=None
    registered_address: dict|None=None
    management: list[dict]=Field(default_factory=list)
    findings: list[CorporateClaim]=Field(default_factory=list)
    background_leads: list[CorporateClaim]=Field(default_factory=list)
    discrepancies: list[str]=Field(default_factory=list)
    missing_evidence: list[str]=Field(default_factory=list)
    sources: list[CorporateSource]=Field(default_factory=list)
    reference_guidance: list[dict]=Field(default_factory=list)
    section_markdown: str|None=None
    confidence: Literal['insufficient','cached_record_consistency_only']='insufficient'
    current_registry_verification: Literal[False]=False
    synthetic_evidence: bool=False
    provider_requests: Literal[0]=0
    financial_requests: Literal[0]=0
    cached_operations: int=0
    limitations: list[str]=Field(default_factory=list)
    warnings: list[ReviewWarning]=Field(default_factory=list)


class CacheOnlyTracker(UsageTracker):
    cache_only = True
    def __init__(self,records,limit,**kwargs):
        super().__init__(development=False,approved=False,max_openregister_credits=0,max_tavily_searches=0,max_session_spend=0,ledger_path=None,**kwargs)
        self.records=records;self.limit=limit;self.operations=0;self.last_raw=None
    def execute(self,provider,operation,identity,call,**kwargs):
        allowed=(provider,operation) in {('OpenRegister','company_details'),('Companies House','public_data'),('Tavily','search_basic')}
        if not allowed or self.operations>=self.limit:raise UsageBlocked('Cache-only operation unavailable or budget reached')
        if provider=='Companies House':
            endpoint=identity.get('endpoint','')
            if not re.fullmatch(r'/company/[A-Za-z0-9]{8}(?:/officers)?',endpoint):raise UsageBlocked('Only profile/officer caches allowed')
        key=self.key(provider,operation,identity)
        if key not in self.records:
            candidate=self.cache.get(key,86400)
            provenance=candidate.get('provenance',{}) if isinstance(candidate,dict) else {}
            if provenance.get('origin')!='live_provider_response' or provenance.get('provider')!=provider or provenance.get('synthetic') is not False:
                raise UsageBlocked('Approved cached evidence unavailable; no provider call executed')
            self.records[key]=candidate.get('payload',candidate)
        self.operations+=1;value=copy.deepcopy(self.records[key])
        if provider=='OpenRegister':
            raw=value['payload'];self.last_raw=copy.deepcopy(raw)
            if raw.get('register') and raw.get('company_register') and raw['register']!=raw['company_register']:
                raise UsageBlocked('Conflicting registration schema fields require review')
            if 'register' in raw and 'company_register' not in raw:raw['company_register']=copy.deepcopy(raw['register'])
        elif provider=='Companies House' and not identity['endpoint'].endswith('/officers'):self.last_raw=copy.deepcopy(value.get('payload',value))
        return value


def supported_jurisdiction(value):return {'Germany':'Germany','UK':'UK','United Kingdom':'UK'}.get(value)


def public_url(value):
    try:
        if not isinstance(value,str) or any(ord(c)<=32 or c in '<>\\' for c in value):return None
        p=urlsplit(value or '')
        if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:return None
        if any(w in p.query.lower() for w in ('token','signature','x-amz','credential','secret')):return None
        return value
    except ValueError:return None


class CorporateIntelligence:
    def __init__(self,cache_dir=ROOT/'data/api_cache',*,allow_demo=False,clock=None):
        self.cache_dir=Path(cache_dir);self.allow_demo=allow_demo;self.clock=clock or (lambda:datetime.now(timezone.utc))
    def collect(self,request):
        result=CorporateResult(client_id=request.client_id,matter_id=request.matter_id,status='NEEDS_REVIEW',identity_verification_status='insufficient_identity',
          limitations=['Register records do not establish the authority of the person instructing the firm.','Corporate intelligence is not professional conflict-of-interest clearance.',
          'No financial data, annual accounts, ratios or provider network requests are part of this path.','Cached information is historical provider reporting, not fresh official verification.'])
        c=request.client
        if c.client_type=='individual':result.status='not_applicable';result.identity_verification_status='not_requested';return result
        if c.client_type!='company':result.missing_evidence=['Explicit client type (individual/company) is required; no suffix inference.'];return self.render(result)
        jurisdiction=supported_jurisdiction(c.jurisdiction)
        if not jurisdiction:result.missing_evidence=['Supported corporate jurisdiction must be explicit; no country inference from the company suffix.'];return self.render(result)
        provider='OpenRegister' if jurisdiction=='Germany' else 'Companies House';result.provider=provider
        identifier=c.approved_provider_id or (c.registration_number if jurisdiction=='UK' else None)
        if identifier and jurisdiction=='UK':identifier=identifier.upper()
        if not identifier or not c.registration_number or (jurisdiction=='Germany' and not c.register_court):
            result.missing_evidence=['Known approved provider ID plus registration number/court are required for cache-only detail verification. No speculative search performed.'];return self.render(result)
        records={};retrieved=None;synthetic=False;source_locator='';cached_record=None
        if request.source_policy=='approved_demo_fixture':
            if not self.allow_demo:result.missing_evidence=['Demo evidence is disabled on this server.'];return self.render(result)
            catalog=json.loads(DEMO.read_text())
            entry=catalog['records'].get(identifier)
            if not entry or entry['jurisdiction']!=jurisdiction:result.status='UNAVAILABLE';result.missing_evidence=['No separately catalogued demo evidence for this identifier.'];return self.render(result)
            retrieved=entry['retrieved_at'];synthetic=True;raw=copy.deepcopy(entry['record']);source_locator='Explicit synthetic demo catalogue: '+identifier
            fixture=captured_record(provider,identifier,raw,synthetic=True)
            fixture['retrieved_at']=retrieved
            cached_record=CorporateCacheRecord.model_validate(fixture)
            for cache in entry.get('operation_records',[]):records[UsageTracker.key(cache['provider'],cache['operation'],cache['identity'])]=copy.deepcopy(cache['value'])
        else:
            op='company_details' if jurisdiction=='Germany' else 'public_data'
            identity=identifier if jurisdiction=='Germany' else {'endpoint':'/company/'+identifier,'params':None}
            key=UsageTracker.key(provider,op,identity)
            try:
                envelope=json.loads((self.cache_dir/(key+'.json')).read_text());value=envelope['value']
                cached_record=CorporateCacheRecord.model_validate(value).require_identity(provider,jurisdiction,identifier,live_only=True)
                retrieved=cached_record.retrieved_at
                raw=copy.deepcopy(cached_record.payload);source_locator='Attested existing provider cache: '+identifier
            except (OSError,ValueError,TypeError,KeyError,AttributeError):
                result.status='UNAVAILABLE';result.missing_evidence=['No reusable provenance-attested identity cache. Provider absence has not been established.'];return self.render(result)
        try:
            when=datetime.fromisoformat(retrieved.replace('Z','+00:00'));age=(self.clock()-when).total_seconds()
            if when.tzinfo is None or age<0:raise ValueError()
        except (ValueError,TypeError,AttributeError):result.missing_evidence=['Missing/invalid original source retrieval timestamp.'];return self.render(result)
        stale=age>30*86400
        key=UsageTracker.key(provider,'company_details',identifier) if jurisdiction=='Germany' else UsageTracker.key(provider,'public_data',{'endpoint':'/company/'+identifier.upper(),'params':None})
        records[key]=cached_record.model_dump(mode='json') if cached_record else ({'payload':raw,'retrieved_at':retrieved} if jurisdiction=='Germany' else raw)
        tracker=CacheOnlyTracker(records,request.max_cached_operations,cache_dir=self.cache_dir if not synthetic else None)
        service=CompanyService(tracker)
        source_id='corporate:'+hashlib.sha256(json.dumps(raw,sort_keys=True).encode()).hexdigest()[:16]
        result.synthetic_evidence=synthetic
        result.sources=[CorporateSource(source_id=source_id,provider=provider,source_type='official' if provider=='Companies House' else 'third_party',locator=source_locator,retrieved_at=retrieved,
             category='UNVERIFIED' if synthetic else 'CACHED',freshness='stale' if stale else 'recent_cache_not_current_verification',synthetic=synthetic,
             cache_accessed_at=self.clock().isoformat(),cache_age_seconds=age,verification_status='synthetic_unverified' if synthetic else cached_record.verification_status)]
        try:
            with use_tracker(tracker):
                verified=service.verify(VerificationRequest(company_name=c.name,jurisdiction=jurisdiction,provider_company_id=identifier,
                    registration_number=c.registration_number,register_court=c.register_court if jurisdiction=='Germany' else None,register_type=c.register_type if jurisdiction=='Germany' else None))
                result.identity_verification_status=verified.status
                if verified.status!='verified':
                    result.discrepancies=[k for k,value in verified.checks.items() if not value];result.missing_evidence=[verified.message];return self.render(result)
                result.status='NEEDS_REVIEW' if stale else 'UNVERIFIED' if synthetic else 'CACHED'
                result.confidence='cached_record_consistency_only';result.verified_legal_name=verified.company.name
                result.registration_number=verified.company.registration_number;result.register_authority=verified.company.register_court if jurisdiction=='Germany' else 'Companies House'
                address=raw.get('address') if jurisdiction=='Germany' else raw.get('registered_office_address')
                result.registered_address=address if isinstance(address,dict) else None
                officers=raw.get('representation',[]) if jurisdiction=='Germany' else raw.get('officers',[])
                for officer in officers if isinstance(officers,list) else []:
                    if not isinstance(officer,dict):continue
                    result.management.append({**{k:officer[k] for k in ('name','role','appointed_on','resigned_on','start_date','end_date') if k in officer},'source_id':source_id,'reported_at':retrieved,'evidence_status':'UNVERIFIED' if synthetic else 'REPORTED'})
                result.findings=[CorporateClaim(description='Legal name and supplied register constraints match the cached provider record: '+verified.company.name,
                    category='UNVERIFIED' if synthetic else 'CACHED',source_ids=[source_id])]
                if stale:result.missing_evidence.append('Cached record is older than 30 days; current identity/status/officer information requires fresh authorized verification.')
                if not result.management:result.missing_evidence.append('No dated officer/director evidence is available in this cached record.')
                try:
                    background=service.research(ResearchRequest(verification_id=verified.verification_id,max_results=request.max_search_results))
                    if background.development:
                        result.synthetic_evidence=True
                        result.missing_evidence.append('Public research contains SYNTHETIC TEST DATA; no live web findings are established.')
                    for index,item in enumerate(background.sources):
                        if not item.usable:
                            result.missing_evidence.append('Public search result excluded: identity/content/source evidence insufficient ('+item.identity+').')
                            continue
                        source=item.source;sid='corporate:background:'+str(index)
                        result.sources.append(CorporateSource(source_id=sid,provider='Tavily cached excerpt',source_type=item.source_type,locator=source.title or 'Untitled search lead',url=public_url(source.url),published_date=source.published_date,retrieved_at=source.retrieved_at,category='UNVERIFIED',freshness=item.freshness,synthetic=synthetic or background.development))
                        result.background_leads.append(CorporateClaim(description=('SYNTHETIC TEST DATA — ' if synthetic or background.development else '')+'Unverified public search lead: '+(source.title or 'Untitled'),category='UNVERIFIED',source_ids=[sid]))
                    result.missing_evidence+=background.missing_evidence
                except UsageBlocked:result.missing_evidence.append('Bounded Tavily cache unavailable; no paid research request was attempted.')
                except Exception as error:result.missing_evidence.append('Public research unavailable ('+type(error).__name__+'); registry findings retained. No automatic retry.')
        except Exception as error:
            result.status='UNAVAILABLE';result.identity_verification_status='verification_failed';result.missing_evidence.append('Cached provider verification unavailable ('+type(error).__name__+'); no provider call made.')
        finally:result.cached_operations=tracker.operations
        result.reference_guidance=LocalRAG().query('corporate identity registration representation authority',jurisdiction,'corporate_identity',2)
        return self.render(result)

    def render(self,result):
        if result.status=='not_applicable':return result
        result.warnings=corporate_warnings(result)
        def warning_line(w):return '['+w.warning_id+'] '+w.category+': '+text(w.message)
        authority={w.message:warning_line(w) for w in result.warnings if w.category=='authority'}
        sections=['Corporate Identity and Registration','Registered Address and Public Records','Management and Representation Information','Identity Discrepancies','Public Background Research','Missing Evidence and Verification Questions','Source Freshness and Limitations']
        lines=['','## Corporate Client Intelligence','', 'Evidence status: '+result.status+'. Identity check: '+result.identity_verification_status+'. Current registry verification: false.']
        content=[['- '+text(f.description)+' ['+', '.join(f.source_ids)+']' for f in result.findings],
                 ['Reported cached address: '+text(json.dumps(result.registered_address,ensure_ascii=False))+' ['+', '.join(s.source_id for s in result.sources[:1])+']'],
                 ['Reported management (not proof of instruction authority): '+text(json.dumps(result.management,ensure_ascii=False))+' ['+', '.join(s.source_id for s in result.sources[:1])+']'],
                 [warning_line(w) for w in result.warnings if w.category=='identity_conflict'],
                 ['- '+text(x.description)+' ['+', '.join(x.source_ids)+']' for x in result.background_leads],
                 [warning_line(w) for w in result.warnings if w.category not in ('identity_conflict','authority')],
                 [text(s.source_id)+': '+text(s.provider)+'; '+text(s.locator)+'; retrieved '+text(s.retrieved_at)+'; published '+text(s.published_date)+'; source type '+text(s.source_type)+'; '+s.category+'; '+s.freshness+((' — [source](<'+public_url(s.url)+'>)') if public_url(s.url) else '') for s in result.sources]+[authority.get(value,text(value)) for value in result.limitations]]
        for title,items in zip(sections,content):lines+=['','### '+title,'']+(items or ['UNAVAILABLE / REQUIRES LAWYER REVIEW.'])
        result.section_markdown='\n'.join(lines)+'\n';return result
