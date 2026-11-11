"""Read-only trusted evidence resolution; no provider transport or caller attestation.

Primary receipts attest server-checked submitted wording, not independent HTTP
acquisition. Only the existing research verifier writes these private receipts.
"""
from datetime import date,datetime,timezone
import hashlib
import json
from pathlib import Path
import re
from scripts.api_usage import JsonCache,UsageTracker
from scripts.corporate_cache import CorporateCacheRecord
from scripts.corporate_intelligence import CorporateIntelligence,CorporateRequest,DEMO
from scripts.local_rag import LocalRAG
from scripts.onboarding import CORPUS
from scripts.primary_research import SOURCE_URL,RULES


class ProvenanceError(ValueError):
    pass


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def source_metadata(source):
    return source.model_dump(exclude={'cache_accessed_at','cache_age_seconds'})


class EvidenceResolver:
    def __init__(self,cache_dir='data/api_cache',receipt_dir='data/ai_synthesis/evidence_receipts',*,allow_demo=True,clock=None):
        self.cache_dir=Path(cache_dir);self.receipt_dir=Path(receipt_dir)
        self.allow_demo=allow_demo;self.clock=clock or (lambda:datetime.now(timezone.utc))
        self.known={**LocalRAG(CORPUS).chunks,**LocalRAG().chunks}

    def legal(self,source,bundle,primary=None):
        card=self.known.get(source.source_id)
        if card:
            expected={'content':card['text'],'url':card['source_url'],'locator':card['locator'],
                      'reviewed_at':card['reviewed_at'],'document_date':card['document_date']}
            if any(getattr(source,k)!=v for k,v in expected.items()):
                raise ProvenanceError('Legal source metadata differs from trusted corpus')
            for key in ('reviewed_at','document_date'):
                if expected[key] and date.fromisoformat(expected[key])>self.clock().date():
                    raise ProvenanceError('Future legal reference date')
            return {**expected,'title':card['title'],'jurisdiction':card['jurisdiction'],
                    'retrieved_at':None,'source_sha256':None,'acquisition':'trusted_local_reference_corpus'}
        if not primary or not primary.receipt_id or not re.fullmatch(r'[a-f0-9]{64}',primary.receipt_id):
            raise ProvenanceError('Unknown legal source or missing server receipt')
        try:
            entry=json.loads((self.receipt_dir/(primary.receipt_id+'.json')).read_text())['value']
            if hashlib.sha256(canonical(entry).encode()).hexdigest()!=primary.receipt_id:
                raise ValueError()
            if entry['client_id']!=bundle.client.client_id or entry['matter_id']!=bundle.matter.matter_id:
                raise ValueError()
            fields=('status','source_url','retrieved_at','http_status','source_sha256','source_encoding','source_evidence_status','verified_rules')
            submitted=primary.model_dump(mode='json')
            if any(submitted[k]!=entry['result'][k] for k in fields):raise ValueError()
            expected=entry['sources'][source.source_id]
            if source.model_dump(mode='json')!=expected:raise ValueError()
            when=datetime.fromisoformat(entry['result']['retrieved_at'].replace('Z','+00:00'))
            if when.tzinfo is None or when>self.clock():raise ValueError()
            if expected['reviewed_at'] and date.fromisoformat(expected['reviewed_at'])>self.clock().date():raise ValueError()
            return {**expected,'title':source.locator,'jurisdiction':'Germany','retrieved_at':entry['result']['retrieved_at'],
                    'source_sha256':entry['result']['source_sha256'],'acquisition':'server_receipt_for_submitted_wording_not_independent_http_attestation'}
        except (OSError,ValueError,TypeError,KeyError):
            raise ProvenanceError('Primary source receipt missing or mismatched') from None

    def record_primary(self,result,bundle):
        """Internal callback after verify_research; never a general evidence-write API."""
        if not bundle or result.status not in ('verified','partially_verified'):
            return result
        when=datetime.fromisoformat(result.retrieved_at.replace('Z','+00:00'))
        if when.tzinfo is None or not 0<=(self.clock()-when).total_seconds()<=86400:
            raise ProvenanceError('Invalid source receipt time')
        if result.source_url!=SOURCE_URL or result.http_status!=200 or not result.source_sha256 or not re.fullmatch(r'[a-f0-9]{64}',result.source_sha256):
            raise ProvenanceError('Invalid source receipt metadata')
        ids=set()
        for rule in result.verified_rules:
            if not any(rule.source_id=='primary:bgb286:'+n+':'+result.source_sha256[:16] and rule.quote==quote for n,(quote,_) in RULES.items()):
                raise ProvenanceError('Invalid source receipt rule')
            ids.add(rule.source_id)
        sources={s.source_id:s.model_dump(mode='json') for s in result.enriched_assessment.sources if s.source_id in ids}
        if set(sources)!=ids:raise ProvenanceError('Incomplete source receipt')
        fields=('status','source_url','retrieved_at','http_status','source_sha256','source_encoding','source_evidence_status','verified_rules')
        raw=result.model_dump(mode='json')
        entry={'client_id':bundle.client.client_id,'matter_id':bundle.matter.matter_id,
               'result':{k:raw[k] for k in fields},'sources':sources}
        key=hashlib.sha256(canonical(entry).encode()).hexdigest()
        self.receipt_dir.mkdir(parents=True,exist_ok=True,mode=0o700)
        JsonCache(self.receipt_dir).put(key,entry)
        return result.model_copy(update={'receipt_id':key})

    def corporate(self,submitted,bundle):
        if submitted.client_id!=bundle.client.client_id or submitted.matter_id!=bundle.matter.matter_id:
            raise ProvenanceError('Corporate case binding mismatch')
        client=bundle.client;identifier=client.approved_provider_id or client.registration_number
        catalogue=json.loads(DEMO.read_text())['records']
        fixture=identifier in catalogue
        if fixture and not self.allow_demo:raise ProvenanceError('Server demo evidence disabled')
        trusted=CorporateIntelligence(self.cache_dir,allow_demo=self.allow_demo,clock=self.clock).collect(CorporateRequest(
            synthetic_data=True,client_id=bundle.client.client_id,matter_id=bundle.matter.matter_id,client=client,
            source_policy='approved_demo_fixture' if fixture else 'cache_only'))
        # Never use caller flags, dates, assertions or warning lists as attestation.
        fields=('status','identity_verification_status','provider','verified_legal_name','registration_number','register_authority',
                'synthetic_evidence','current_registry_verification','registered_address','management','findings','background_leads',
                'discrepancies','missing_evidence','warnings','reference_guidance')
        a=submitted.model_dump(mode='json');b=trusted.model_dump(mode='json')
        if any(a[k]!=b[k] for k in fields) or [source_metadata(s) for s in submitted.sources]!=[source_metadata(s) for s in trusted.sources]:
            raise ProvenanceError('Corporate evidence differs from server records')
        record=None
        if not fixture and trusted.sources:
            jurisdiction='Germany' if client.jurisdiction=='Germany' else 'UK'
            provider='OpenRegister' if jurisdiction=='Germany' else 'Companies House'
            identifier=identifier if jurisdiction=='Germany' else identifier.upper()
            identity=identifier if jurisdiction=='Germany' else {'endpoint':'/company/'+identifier,'params':None}
            key=UsageTracker.key(provider,'company_details' if jurisdiction=='Germany' else 'public_data',identity)
            try:
                value=json.loads((self.cache_dir/(key+'.json')).read_text())['value']
                record=CorporateCacheRecord.model_validate(value).require_identity(provider,jurisdiction,identifier,live_only=True)
                expected='corporate:'+hashlib.sha256(json.dumps(record.payload,sort_keys=True).encode()).hexdigest()[:16]
                if trusted.sources[0].source_id!=expected:raise ValueError()
            except (OSError,ValueError,KeyError,TypeError):
                raise ProvenanceError('Corporate cache changed or lost provenance') from None
        return trusted,record
