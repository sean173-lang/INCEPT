"""Version 2 model contract: select server excerpts; never write factual prose.

Quotation membership and bounded issue checks establish attribution, not general
semantic truth. All source acquisition/provenance is resolved before this layer.
"""
import hashlib
import json
import re
from typing import Literal
from pydantic import Field
from scripts.service_schemas import Schema
from scripts.ai_content_policy import IssueCategory,ActionState,adverse_categories

FACT_SECTIONS=('mandate_summary','factual_background')
REASON_SECTIONS=('preliminary_legal_issues','source_supported_analysis','missing_information',
                 'uncertainties_and_limitations','questions_requiring_lawyer_review','proposed_next_steps')


class ExcerptSelection(Schema):
    excerpt_id: str


class LegalEvidenceSelection(Schema):
    excerpt_id: str


class InquiryEvidenceSelection(Schema):
    excerpt_id: str


class Interpretation(Schema):
    statement: str=Field(min_length=10,max_length=900)
    issue_category: IssueCategory
    assertion_type: Literal['conditional_analysis','lawyer_review_request']
    action_state: ActionState
    evidence_references: list[ExcerptSelection]=Field(min_length=1,max_length=4)


class LegalIssueQuestion(Schema):
    statement: str=Field(min_length=10,max_length=900,pattern=r'^(?:Should|What|Which|How|Is|Are|Does|Do|Would|Could|Can|[Ww]\w*|Ist|Sind|Seid|Bist|Soll\w*|Kann\w*|Könn\w*|Muss\w*|Müss\w*|Darf\w*|Wär\w*|Besteht|Bestehen|Liegt|Liegen|Gibt|Lässt|Lassen|Handelt|Erfüllt|Kommt|Verlangt|Bedarf|Erfordert|Fehlt|Fehlen|Wurde|Werden|Ab wann|Bis wann|Unter welchen|Inwiefern)\b.*\?$')
    issue_category: IssueCategory
    assertion_type: Literal['lawyer_review_request']
    action_state: ActionState
    evidence_references: list[ExcerptSelection]=Field(min_length=1,max_length=4)


class SourceSupportedAnalysis(Schema):
    """A legal conclusion must bind one official rule to one selected inquiry excerpt."""
    statement: str=Field(min_length=10,max_length=900)
    issue_category: IssueCategory
    assertion_type: Literal['conditional_analysis']
    action_state: ActionState
    legal_evidence: LegalEvidenceSelection
    inquiry_evidence: InquiryEvidenceSelection


class ExcerptSynthesis(Schema):
    contract_version: Literal['2.0']
    client_id: str
    matter_id: str
    client_name: str
    opposing_parties: list[str]
    governing_law: str
    lawyer_review_required: Literal[True]
    mandate_accepted: Literal[False]
    documents_approved: Literal[False]
    invoice_issued: Literal[False]
    external_actions_executed: Literal[False]
    mandate_summary: ExcerptSelection
    factual_background: list[ExcerptSelection]=Field(min_length=1,max_length=5)
    preliminary_legal_issues: list[LegalIssueQuestion]=Field(max_length=5)
    source_supported_analysis: list[SourceSupportedAnalysis]=Field(max_length=5)
    missing_information: list[Interpretation]=Field(min_length=1,max_length=5)
    uncertainties_and_limitations: list[Interpretation]=Field(min_length=1,max_length=5)
    questions_requiring_lawyer_review: list[Interpretation]=Field(min_length=1,max_length=5)
    proposed_next_steps: list[Interpretation]=Field(min_length=1,max_length=5)


class ExcerptRecord(Schema):
    source_id: str
    excerpt_id: str
    text: str=Field(min_length=12,max_length=900)
    classification: Literal['unverified_intake','client_alleged','official_record_reported','source_guidance','cached_report','unverified_lead','question']
    issue_category: IssueCategory
    allowed_sections: list[Literal['mandate_summary','factual_background','reasoning']]
    role: str
    source_sha256: str
    provenance: dict


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def exact_sentences(value):
    """Split source text without treating German ordinal dates as sentence ends."""
    result=[];start=0
    for match in re.finditer(r'[.!?](?:[”"»)]*)\s+',value):
        end=match.start()+1
        before=value[start:end].rstrip()
        after=value[match.end():]
        if value[match.start()] == '.':
            if re.search(r'\b(?:Dr|Prof|Nr|Abs|Art|z|B)\.$',before):continue
            if re.search(r'\b\d{1,2}\.$',before) and re.match(r'(?:Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\b',after,re.I):continue
        sentence=value[start:end].strip()
        if sentence:result.append(sentence)
        start=match.end()
    tail=value[start:].strip()
    if tail:result.append(tail)
    return result


def build_excerpts(packet):
    """Exact spans only; coverage/guidance can support questions, never case facts."""
    result={};identities={};c=packet['context'];sources=packet['sources']
    def add(id,phrase,category,sections,role,classification=None):
        if not isinstance(phrase,str) or not 12<=len(phrase)<=900 or phrase not in sources[id]['content']:return
        s=sources[id];status=classification or s['classification']
        if sections and any(v in FACT_SECTIONS for v in sections) and adverse_categories(phrase):
            eligible=packet['issue_support'].get(category,{}).get('evidence',[])
            if not any(e['source_id']==id and e['quote']==phrase and e['status']==status for e in eligible):return
        digest=hashlib.sha256(s['content'].encode()).hexdigest()
        identity=hashlib.sha256(canonical([c['client_id'],c['matter_id'],id,digest,phrase,status,category,sections,role]).encode()).hexdigest()
        if identity in identities:return
        key=f'E{len(result)+1:03d}'
        record=ExcerptRecord(source_id=id,excerpt_id=key,text=phrase,classification=status,issue_category=category,
            allowed_sections=sections,role=role,source_sha256=digest,
            provenance={k:v for k,v in s.items() if k not in ('content','classification')}).model_dump()
        if key in result and result[key]!=record:raise ValueError('Excerpt identity collision')
        result[key]=record;identities[identity]=key
        if len(result)>160:raise ValueError('Evidence excerpt catalogue exceeds bounded scope')
    for id,s in sorted(sources.items()):
        category='mandate_intake';role='case_context';sections=['reasoning'];value=None
        if id=='synthesis:intake:client':
            value=json.loads(s['content']);role='client';sections=['factual_background','reasoning']
            add(id,value['name'],category,sections,role)
            if len(value['name'])<12:add(id,s['content'],category,sections,role)
        elif id=='synthesis:intake:opponents':
            role='counterparty';sections=['factual_background','reasoning']
            for name in json.loads(s['content']):add(id,name,category,sections,role)
            if not any(r['source_id']==id for r in result.values()):add(id,s['content'],category,sections,role)
        elif id=='synthesis:intake:matter':
            role='client_alleged_matter';value=json.loads(s['content']);sections=['mandate_summary','factual_background','reasoning']
            for key in ('summary','title','scope'):
                phrase=value[key]
                # Never give a multi-sentence client email the appearance of one
                # concise model-authored factual summary. Keep only exact spans.
                sentences=exact_sentences(phrase) if key=='summary' else [phrase]
                for sentence in sentences:add(id,sentence,category,sections,role)
        elif id=='synthesis:intake:coverage':
            value=json.loads(s['content']);role='coverage_limitation';category='missing_evidence'
            for key in ('missing_information','missing_evidence','discrepancies','limitations'):
                for phrase in value.get(key,[]):add(id,phrase,category,['reasoning'],role)
            for key in ('warnings','review_warnings'):
                for warning in value.get(key,[]):add(id,warning['message'],category,['reasoning'],role)
        elif s['classification']=='source_guidance':
            add(id,s['content'],category,['reasoning'],'legal_reference_not_case_finding')
        # A genuine adverse allegation uses its specific server-validated span and
        # attributed status. A denying span supports uncertainty, not promotion.
    for category,support in packet['issue_support'].items():
        for entry in support['evidence']+support['contradictions']:
            id=entry['source_id'];sections=['reasoning']
            if entry in support['evidence']:
                if id=='synthesis:intake:matter':sections=['mandate_summary','factual_background']+sections
            add(id,entry['quote'],category,sections,'attributed_allegation_or_denial',entry['status'])
    return result


def expand_selection(proposal,packet):
    """Normalize into unchanged v1 output, then run the unchanged safety validator."""
    from scripts.ai_synthesis import AISynthesis,validate_synthesis
    # Detect stale/modified catalogue entries even in direct internal callers.
    if packet.get('excerpts')!=build_excerpts(packet):raise ValueError('Server excerpt catalogue mismatch')
    catalog=packet['excerpts'];proof={}
    def resolve(selection,section):
        record=catalog.get(selection.excerpt_id)
        if not record:
            error=ValueError('Fabricated or mismatched excerpt selection');error.field=section;error.validator='excerpt_selection';raise error
        if section not in record['allowed_sections']:
            error=ValueError('Excerpt cannot support this section or role');error.field=section;error.validator='excerpt_selection';raise error
        return record
    data=proposal.model_dump(exclude={'contract_version'})
    for field in FACT_SECTIONS:
        selections=[proposal.mandate_summary] if field=='mandate_summary' else getattr(proposal,field);expanded=[]
        proof[field]=[v.model_dump() for v in selections]
        for selection in selections:
            e=resolve(selection,field)
            expanded.append({'statement':e['text'],'source_ids':[e['source_id']],
                'evidence_quotes':[{'source_id':e['source_id'],'quote':e['text']}],
                'evidence_status':e['classification'],'issue_category':e['issue_category'],
                'assertion_type':'source_excerpt','action_state':'not_performed_pending_lawyer_approval'})
        data[field]=expanded[0] if field=='mandate_summary' else expanded
    for field in REASON_SECTIONS:
        expanded=[]
        for item in getattr(proposal,field):
            if field=='source_supported_analysis':
                legal=catalog.get(item.legal_evidence.excerpt_id)
                inquiry=catalog.get(item.inquiry_evidence.excerpt_id)
                if not legal or legal.get('role')!='legal_reference_not_case_finding':
                    error=ValueError('Legal analysis requires a retrieved statutory excerpt');error.field=f'{field}[{len(expanded)}].legal_evidence.excerpt_id';error.validator='legal_evidence_binding';raise error
                if not inquiry or inquiry.get('role')!='client_alleged_matter':
                    error=ValueError('Legal analysis lacks selected inquiry evidence');error.field=f'{field}[{len(expanded)}].inquiry_evidence.excerpt_id';error.validator='inquiry_evidence_binding';raise error
                refs=[item.legal_evidence,item.inquiry_evidence]
            else:refs=item.evidence_references
            unique={ref.excerpt_id:ref for ref in refs}
            entries=[resolve(ref,'reasoning') for ref in unique.values()]
            ids=list(dict.fromkeys(e['source_id'] for e in entries))
            exclude={'legal_evidence','inquiry_evidence'} if field=='source_supported_analysis' else {'evidence_references'}
            expanded.append({**item.model_dump(exclude=exclude),'source_ids':ids,
                'evidence_quotes':[{'source_id':e['source_id'],'quote':e['text']} for e in entries],
                'evidence_status':'question' if item.assertion_type=='lawyer_review_request' else 'preliminary_analysis'})
        data[field]=expanded
    return validate_synthesis(AISynthesis.model_validate(data),packet),proof
