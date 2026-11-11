"""Bounded issue support and immutable action states, not semantic proof.

Lexical discovery is conservative and multilingual. Material adverse statements
must be exact server-selected evidence excerpts; free adverse hypotheses are not
accepted. Questions remain explicitly unverified lawyer-review requests.
"""
import json
import re
import unicodedata
from typing import Literal

class ContentPolicyError(ValueError):
    pass


class ApprovalAssertionError(ContentPolicyError):
    pass


IssueCategory=Literal['mandate_intake','payment_dispute','representation_authority','conflict_review','corporate_identity',
    'missing_evidence','jurisdiction','fraud_allegation','creditor_evasion_allegation','criminal_allegation',
    'insolvency_misconduct_allegation','dishonesty_allegation','corporate_record_status']
AssertionType=Literal['source_excerpt','conditional_analysis','lawyer_review_request']
ActionState=Literal['not_performed_pending_lawyer_approval']

PATTERNS={
 'fraud_allegation':r'\bfraud\w*|\bdefraud\w*|\bbetr[uü]g\w*|\barglist\w*',
 'creditor_evasion_allegation':r'\b(?:evad\w*.{0,20}creditors?|creditor.{0,20}evasion|gläubigerbenachteilig\w*|gläubigerumgeh\w*|vermögensverschieb\w*|(?:conceal|hide).{0,25}assets)',
 'criminal_allegation':r'\b(?:tax evasion|steuerhinterzieh\w*|criminal\w*|crime\w*|straftat\w*|strafbar\w*|money laundering|geldwäsch\w*|embezzl\w*|theft|steal\w*|veruntreu\w*|brib\w*|corrupt\w*|korrupt\w*)',
 'insolvency_misconduct_allegation':r'\b(?:insolvency misconduct|wrongful trading|fraudulent trading|insolvenzverschlepp\w*)',
 'dishonesty_allegation':r'\b(?:dishonest\w*|intentional deception|deceiv\w*|deceit\w*|lied|lüg\w*|täusch\w*)',
}
OUT_OF_SCOPE=r'\b(?:patent\w*|trademark\w*|copyright\w*|markenverletz\w*|urheber\w*|employment dismissal|kartell\w*|antitrust)\b'
NEGATIVE=r'\b(?:no|not|never|denies|denied|rejects|withdrawn|withdraws|unfounded|kein\w*|nicht|bestreitet|bestritten|zurückgenommen)\b'
ALLEGED=r'\b(?:alleg\w*|suspect\w*|claims?|accus\w*|charged|convict\w*|investigated|committed|perpetrated|behaupt\w*|vorwurf\w*|vorwürf\w*|vermut\w*|wirft|begangen)\b'


def norm(text):return unicodedata.normalize('NFKC',text).casefold()


def adverse_categories(text):
    return {category for category,pattern in PATTERNS.items() if re.search(pattern,norm(text))}


def support_for(packet):
    sources=packet['sources']
    all_ids=list(sources)
    result={category:{'source_ids':all_ids,'evidence':[],'contradictions':[]} for category in
        ('mandate_intake','representation_authority','conflict_review','missing_evidence','jurisdiction')}
    matter='synthesis:intake:matter'
    matter_data=json.loads(sources[matter]['content'])
    text=' '.join(str(v) for v in matter_data.values())
    if re.search(r'payment|invoice|contract|zahlung|rechnung|forderung|vertrag',text,re.I):
        result['payment_dispute']={'source_ids':[matter],'evidence':[],'contradictions':[]}
    if packet['context']['client_type']=='company':
        result['corporate_identity']={'source_ids':all_ids,'evidence':[],'contradictions':[]}
    observations=[]
    for id,source in sources.items():
        classification=source['classification']
        if id==matter:
            values=list(matter_data.values())
        elif id.startswith('synthesis:corporate:') and id!='synthesis:corporate:coverage' and classification=='unverified_lead' and json.loads(source['content']).get('provider')=='Tavily cached excerpt':
            values=json.loads(source['content']).get('observations',[])
        elif classification=='official_record_reported':
            values=[]
            result['corporate_record_status']={'source_ids':[id],'evidence':[{'source_id':id,'quote':source['content'],'status':'official_record_reported'}],'contradictions':[]}
        else:continue
        for value in values:
            for sentence in re.split(r'(?<=[.!?])\s+',value):
                if sentence not in source['content']:continue
                for category in adverse_categories(sentence):
                    entry={'source_id':id,'quote':sentence,'status':'client_alleged' if classification=='unverified_intake' else 'unverified_lead'}
                    term=re.search(PATTERNS[category],norm(sentence))
                    before=norm(sentence)[:term.start()]
                    after=norm(sentence)[term.end():]
                    denied=bool(re.search(NEGATIVE+r'(?:\W+\w+){0,4}\W*$',before) or re.match(r'^(?:\W+\w+){0,3}\W+(?:denied|withdrawn|unfounded|not substantiated|bestritten|zurückgenommen)\b',after))
                    if denied:
                        observations.append((category,entry,False));continue
                    if not re.search(ALLEGED,norm(sentence)):continue
                    observations.append((category,entry,True))
    for category,entry,positive in observations:
        if positive:
            value=result.setdefault(category,{'source_ids':[],'evidence':[],'contradictions':[]})
            if entry['source_id'] not in value['source_ids']:value['source_ids'].append(entry['source_id'])
            if entry not in value['evidence']:value['evidence'].append(entry)
    for category,entry,positive in observations:
        if not positive and category in result:result[category]['contradictions'].append(entry)
    return result


def genuine_review_request(text):
    return text.endswith('?') and bool(re.match(r'^(?:Should|What|Which|How|Is|Are|Does|Do|Would|Could|Can|Ist|Sind|Soll|Sollte|Welche\w*|Wie|Muss|Müssen|Bedarf|Erfordert)\b',text,re.I))


def check_approval_language(text):
    value=norm(text)
    # State assertions, passive completion and urgent issuance are prohibited even
    # inside questions or source excerpts. Review requests do not change states.
    noun=r'(?:mandate|engagement|client|document|invoice|advance invoice|mandat\w*|mandatsannahme|mandantschaft|dokument\w*|rechnung\w*|vorschussrechnung\w*)'
    completed=r'\b'+noun+r'\b.{0,65}\b(?:is|are|was|were|has been|have been|ist|sind|wurde\w*|bereits|hat)\b.{0,35}\b(?:approved|accepted|issued|released|sent|angenommen|genehmigt|freigegeben|ausgestellt|erfolgt)\b'
    urgent=r'\b(?:invoice|rechnung|vorschussrechnung)\b.{0,70}\b(?:immediately|sofort|unverzüglich|umgehend)\b|\b(?:invoice)\b.{0,50}\b(?:should|must|is to)\b.{0,20}\bissued\b'
    declarative=r'\b(?:we|i)\s+(?:hereby\s+)?(?:approve|accept|issue)\b|\b(?:mandat|mandatsannahme)\w*.{0,50}\b(?:erfolgt|erteilt)\b'
    inverted=r'\b(?:is|are|has|have|was|were|ist|sind|wurde\w*)\b.{0,35}\b'+noun+r'\b.{0,40}\b(?:approved|accepted|issued|released|angenommen|genehmigt|freigegeben|ausgestellt)\b'
    if re.search(completed,value) or re.search(inverted,value) or re.search(urgent,value) or re.search(declarative,value):
        raise ApprovalAssertionError('Approval/acceptance/issuance assertion rejected')
    if re.match(r'^(?:approve|accept|issue|send|create|freigeben|genehmigen|ausstellen|versenden)\b',value):
        raise ApprovalAssertionError('Executable action instruction rejected')


def validate_content(item,field,packet):
    if item.action_state!='not_performed_pending_lawyer_approval':raise ContentPolicyError('Action state changed')
    check_approval_language(item.statement)
    for quote in item.evidence_quotes:check_approval_language(quote.quote)
    support=packet['issue_support'];category=item.issue_category
    if category not in support:raise ContentPolicyError('Issue outside supported taxonomy')
    ids=set(item.source_ids)
    detected=adverse_categories(item.statement)
    if re.search(OUT_OF_SCOPE,norm(item.statement)):raise ContentPolicyError('Issue outside controlled legal scope')
    for detected_category in detected:
        if detected_category not in support:raise ContentPolicyError('Unsupported adverse allegation')
        eligible=support[detected_category]['evidence']
        if not any(e['source_id'] in ids and any(q.source_id==e['source_id'] and q.quote==e['quote'] for q in item.evidence_quotes) for e in eligible):
            raise ContentPolicyError('Adverse issue requires specific supporting evidence, not a general citation')
    adverse=category in PATTERNS or category=='corporate_record_status'
    if detected and category not in detected:raise ContentPolicyError('Adverse content hidden under unrelated category')
    if adverse:
        evidence=support[category]['evidence']
        if not any(e['source_id'] in ids and any(q.source_id==e['source_id'] and q.quote==e['quote'] for q in item.evidence_quotes) for e in evidence):
            raise ContentPolicyError('Adverse category lacks specific support excerpt')
        if item.assertion_type=='source_excerpt':
            if not any(item.statement==e['quote'] and item.evidence_status==e['status'] and ids=={e['source_id']} for e in evidence):
                raise ContentPolicyError('Adverse facts require complete attributed evidence excerpts')
        elif item.assertion_type=='lawyer_review_request':
            if not genuine_review_request(item.statement) or item.evidence_status!='question':
                raise ContentPolicyError('Adverse issue is a lawyer question, not a finding')
            if category in PATTERNS and not re.search(r'alleg|unverified|uncertain|disput|behaupt|vorwurf|vorwürf|ungeklärt|ungeprüft|streitig',norm(item.statement)):
                raise ContentPolicyError('Adverse uncertainty/attribution missing')
        else:raise ContentPolicyError('Free adverse hypotheses are not permitted')
    if item.assertion_type=='lawyer_review_request' and not genuine_review_request(item.statement):
        raise ContentPolicyError('Assertion disguised as a question')
    return adverse


def validate_contradictions(output,packet):
    for category,support in packet['issue_support'].items():
        if not support['contradictions']:continue
        found=False
        for item in output.uncertainties_and_limitations:
            if item.issue_category!=category or item.assertion_type!='lawyer_review_request':continue
            quotes={(q.source_id,q.quote) for q in item.evidence_quotes}
            if any((e['source_id'],e['quote']) in quotes for e in support['evidence']) and any((e['source_id'],e['quote']) in quotes for e in support['contradictions']):found=True
        if not found:raise ContentPolicyError('Contradictory evidence requires explicit uncertainty and both sides')
