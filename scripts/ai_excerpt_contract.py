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

FACT_SECTIONS=('mandate_summary','factual_background','corporate_intelligence_observations')
REASON_SECTIONS=('preliminary_legal_issues','source_supported_analysis','missing_information',
                 'uncertainties_and_limitations','questions_requiring_lawyer_review','proposed_next_steps')


class ExcerptSelection(Schema):
    source_id: str
    excerpt_id: str


class Interpretation(Schema):
    statement: str=Field(min_length=10,max_length=900)
    issue_category: IssueCategory
    assertion_type: Literal['conditional_analysis','lawyer_review_request']
    action_state: ActionState
    evidence_references: list[ExcerptSelection]=Field(min_length=1,max_length=4)


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
    corporate_intelligence_observations: list[ExcerptSelection]=Field(max_length=5)
    preliminary_legal_issues: list[Interpretation]=Field(max_length=5)
    source_supported_analysis: list[Interpretation]=Field(max_length=5)
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
    allowed_sections: list[Literal['mandate_summary','factual_background','corporate_intelligence_observations','reasoning']]
    role: str
    jurisdiction: str
    source_sha256: str
    provenance: dict


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'))


def build_excerpts(packet):
    """Exact spans only; coverage/guidance can support questions, never case facts."""
    result={};c=packet['context'];sources=packet['sources']
    def add(id,phrase,category,sections,role,classification=None):
        if not isinstance(phrase,str) or not 12<=len(phrase)<=900 or phrase not in sources[id]['content']:return
        s=sources[id];status=classification or s['classification']
        if sections and any(v in FACT_SECTIONS for v in sections) and adverse_categories(phrase):
            eligible=packet['issue_support'].get(category,{}).get('evidence',[])
            if not any(e['source_id']==id and e['quote']==phrase and e['status']==status for e in eligible):return
        digest=hashlib.sha256(s['content'].encode()).hexdigest()
        key='excerpt:'+hashlib.sha256(canonical([c['client_id'],c['matter_id'],id,digest,phrase,status,category,sections,role]).encode()).hexdigest()[:32]
        record=ExcerptRecord(source_id=id,excerpt_id=key,text=phrase,classification=status,issue_category=category,
            allowed_sections=sections,role=role,jurisdiction=c['governing_law'],source_sha256=digest,
            provenance={k:v for k,v in s.items() if k not in ('content','classification')}).model_dump()
        if key in result and result[key]!=record:raise ValueError('Excerpt identity collision')
        result[key]=record
        if len(result)>160:raise ValueError('Evidence excerpt catalogue exceeds bounded scope')
    for id,s in sources.items():
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
                phrase=value[key];add(id,phrase,category,sections,role)
                # Sentence excerpts remain original contiguous spans, not summaries.
                for sentence in re.split(r'(?<=[.!?])\s+',phrase):add(id,sentence,category,sections,role)
        elif id in ('synthesis:intake:coverage','synthesis:corporate:coverage'):
            value=json.loads(s['content']);role='coverage_limitation';category='missing_evidence'
            for key in ('missing_information','missing_evidence','discrepancies','limitations'):
                for phrase in value.get(key,[]):add(id,phrase,category,['reasoning'],role)
            for key in ('warnings','review_warnings'):
                for warning in value.get(key,[]):add(id,warning['message'],category,['reasoning'],role)
        elif s['classification']=='source_guidance':
            add(id,s['content'],category,['reasoning'],'legal_reference_not_case_finding')
        elif id.startswith('synthesis:corporate:'):
            role='corporate_record_not_sender_authority';category='corporate_identity';sections=['corporate_intelligence_observations','reasoning']
            if s['classification']=='official_record_reported':
                add(id,s['content'],'corporate_record_status',sections,role)
            else:
                for phrase in json.loads(s['content']).get('observations',[]):add(id,phrase,category,sections,role)
        # A genuine adverse allegation uses its specific server-validated span and
        # attributed status. A denying span supports uncertainty, not promotion.
    for category,support in packet['issue_support'].items():
        for entry in support['evidence']+support['contradictions']:
            id=entry['source_id'];sections=['reasoning']
            if entry in support['evidence']:
                sections=(['mandate_summary','factual_background'] if id=='synthesis:intake:matter' else ['corporate_intelligence_observations'])+sections
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
        if not record or record['source_id']!=selection.source_id:raise ValueError('Fabricated or mismatched excerpt selection')
        if section not in record['allowed_sections']:raise ValueError('Excerpt cannot support this section or role')
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
            entries=[resolve(ref,'reasoning') for ref in item.evidence_references]
            pairs=[(e['source_id'],e['excerpt_id']) for e in entries]
            if len(set(pairs))!=len(pairs):raise ValueError('Duplicate excerpt citation')
            ids=list(dict.fromkeys(e['source_id'] for e in entries))
            expanded.append({**item.model_dump(exclude={'evidence_references'}),'source_ids':ids,
                'evidence_quotes':[{'source_id':e['source_id'],'quote':e['text']} for e in entries],
                'evidence_status':'question' if item.assertion_type=='lawyer_review_request' else 'preliminary_analysis'})
        data[field]=expanded
    return validate_synthesis(AISynthesis.model_validate(data),packet),proof
