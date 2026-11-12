"""Offline intake preview. Local persistence only; no delivery/approval executor exists."""
from contextlib import closing
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid

from scripts.service_schemas import ServiceError
from scripts.local_rag import LocalRAG
from scripts.report_renderer import text
from scripts.onboarding_schemas import (OnboardingRequest, OnboardingBundle, ClientRecord, MatterRecord,
    AdvanceCalculation, DraftDocument, AssessmentFinding, AssessmentSource, MandateAssessment, ProposedAction)

ROOT=Path(__file__).resolve().parent.parent
DEFAULT_DB=ROOT/'data/legal_intake_mvp/onboarding.sqlite3'
CORPUS=ROOT/'references/mandate_intake.json'
LEGAL_CORPUS=ROOT/'references/legal_documents/corpus.json'
LABEL='Vorläufige Intake-Angaben; Identität, Sachverhalt und Rechtslage sind ungeprüft. Anwaltliche Prüfung erforderlich.'


def money(value):return format(value.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),'.2f')


def intake_fingerprint(request):
    """Keep existing persisted legacy request keys valid after optional schema additions."""
    data=request.model_dump(mode='json')
    if data.get('document_options') is None:data.pop('document_options',None)
    for person in ('client','firm'):
        if not isinstance(data.get(person),dict):continue
        for key,default in {'client_type':'unknown','registration_number':None,'register_court':None,'register_type':None,'approved_provider_id':None}.items():
            if data[person].get(key)==default:data[person].pop(key,None)
    if data['matter'].get('governing_law') is None:data['matter'].pop('governing_law',None)
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def advance(fees,*,synthetic=True):
    if fees is None or fees.net_hourly_rate is None:return None
    proposed=fees.proposed_advance_hours
    if proposed is None and synthetic is not False:proposed='5'
    if proposed is None:return None
    hours=Decimal(proposed)
    net=Decimal(fees.net_hourly_rate)*hours
    vat=None if fees.vat_mode=='unknown' else Decimal('0') if fees.vat_mode=='exempt' else (net*Decimal(fees.vat_percent)/Decimal('100')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    return AdvanceCalculation(hours=proposed,net_hourly_rate=money(Decimal(fees.net_hourly_rate)),net_fee=money(net),vat_mode=fees.vat_mode,
                              vat_percent=fees.vat_percent,vat_amount=money(vat) if vat is not None else None,
                              gross_total=money(net+vat) if vat is not None else None,tax_status='supplied_demo_treatment_unverified' if synthetic is True else 'supplied_treatment_unverified')


def assessment(request,rag):
    evidence=[('intake:client','client.name',request.client.name or 'Client identity was not established from the supplied intake.'),
              ('intake:matter','matter.summary',request.matter.summary),
              ('intake:scope','matter.requested_scope',request.matter.requested_scope),
              ('intake:fees','fees',request.fees.model_dump_json() if request.fees else 'Fee terms and rates were not supplied.'),
              ('intake:opponents','matter.opposing_parties',json.dumps(request.matter.opposing_parties,ensure_ascii=False)),
              ('intake:deadline','matter.claimed_deadline',json.dumps({'claimed_date':request.matter.claimed_deadline,'source':request.matter.deadline_source},ensure_ascii=False))]
    source_kind='synthetic_intake' if request.synthetic_data else 'intake'
    sources=[AssessmentSource(source_id=i,kind=source_kind,locator=loc,content=body) for i,loc,body in evidence]
    facts=[AssessmentFinding(description=('Unverified synthetic intake statement: ' if request.synthetic_data else '')+body,status='unverified_intake_statement',source_ids=[i]) for i,_,body in evidence[:3] if i!='intake:client' or request.client.name]
    legacy_synthetic_german=(request.synthetic_data and request.matter.governing_law is None and request.client.jurisdiction=='Germany' and request.client.client_type=='unknown')
    german_guidance=request.matter.governing_law=='Germany' or legacy_synthetic_german
    legal_rag=LocalRAG(LEGAL_CORPUS)
    references=(rag.query('mandate authority fee advance conflict confidentiality','Germany',top_k=5) if request.synthetic_data else legal_rag.query(request.matter.title+' '+request.matter.summary+' '+request.matter.requested_scope,'Germany',top_k=5)) if german_guidance else []
    if request.synthetic_data and german_guidance and len(references)!=4:raise ServiceError(503,'mandate_references_unavailable','The reviewed mandate reference set could not be retrieved.')
    guidance=[]
    for ref in references:
        source_id=ref['chunk_id']
        sources.append(AssessmentSource(source_id=source_id,kind='legal_reference',locator=ref['locator'],content=ref['text'],url=ref['source_url'],reviewed_at=ref['reviewed_at'],document_date=ref['document_date']))
        guidance.append(AssessmentFinding(description=ref['text'],status='reference_guidance',source_ids=[source_id]))
    gaps=['Original contract, correspondence and supporting documents have not been reviewed.',
          'Identity, signing authority, conflict check and mandate acceptance are not verified.',
          'Claim merits, applicable substantive law, limitation periods and procedural deadlines are not determined.']
    if request.fees is None:gaps.append('No hourly rate, advance amount or VAT treatment was supplied.')
    elif request.fees.proposed_advance_hours is None:gaps.append('No advance hours or amount was supplied; no fee calculation was made.')
    if not german_guidance:gaps.append('Governing law has not been confirmed; no jurisdiction-specific legal rules are assumed.')
    if not request.client.name:gaps.append('Client identity has not been established from the supplied inquiry.')
    if not request.matter.opposing_parties:gaps.append('Opposing parties are missing; a conflict search cannot be completed.')
    if not request.matter.claimed_deadline:gaps.append('No supported deadline date is supplied; no deadline has been calculated.')
    else:gaps.append('The supplied deadline is an unverified candidate; original notice/service evidence and lawyer confirmation are required.')
    lines=['# '+('DEMO Mandate Assessment Report' if request.synthetic_data else 'Preliminary Mandate Assessment'),'',LABEL,'','Conclusion: lawyer review required. Confidence: insufficient for legal conclusions.','','## Intake evidence — unverified','']
    for fact in facts:lines+=['- '+text(fact.description)+' ['+', '.join(fact.source_ids)+']']
    lines+=['','## Retrieved reference guidance — not findings about the matter','']
    for finding in guidance:lines+=['- '+text(finding.description)+' ['+', '.join(finding.source_ids)+']']
    lines+=['','## Missing information','']+['- '+text(g) for g in gaps]+['','## Sources','']
    for source in sources:
        lines+=['- '+text(source.source_id)+': '+text(source.locator)+(f' — [{text(source.locator)}]({source.url}); reviewed '+text(source.reviewed_at)+'; enactment date not supplied.' if source.url else '; '+('synthetic user-supplied intake, unverified.' if request.synthetic_data else 'user-supplied intake, unverified.'))]
    return MandateAssessment(factual_findings=facts,guidance=guidance,missing_information=gaps,sources=sources,
                            corpus_version=legal_rag.version,content_markdown='\n'.join(lines)+'\n')


def build_bundle(request,rag,include_documents=True):
    client_id=uuid.uuid5(uuid.NAMESPACE_URL,'incept-client:'+request.idempotency_key).hex
    matter_id=uuid.uuid5(uuid.NAMESPACE_URL,'incept-matter:'+request.idempotency_key).hex
    client=ClientRecord(**request.client.model_dump(),client_id=('demo-client-' if request.synthetic_data else 'client-')+client_id,synthetic_data=request.synthetic_data)
    matter=MatterRecord(**request.matter.model_dump(),client_id=client.client_id,matter_id=('demo-matter-' if request.synthetic_data else 'matter-')+matter_id)
    fee=advance(request.fees,synthetic=request.synthetic_data);report=assessment(request,rag)
    docs=[]
    if include_documents:
        from scripts.legal_documents import generate_documents
        if not request.synthetic_data and (not request.firm or not request.fees or not request.draft_date or not request.document_options):
            raise ServiceError(422,'document_inputs_incomplete','Firm identity, fee terms, draft date and document instructions are required for document generation.')
        docs=generate_documents(request,client,matter,fee)
        report.content_markdown+='\n## Document drafting validation — no legal approval\n\n'
        for doc in docs:
            report.content_markdown+='- '+doc.kind+': **'+doc.completeness_status+'**; template '+str(doc.template_version)+'. Lawyer approval pending; no issuance.\n'
            if doc.completeness_status!='DRAFT_COMPLETE_FOR_LAWYER_REVIEW':
                report.missing_information.append('Document '+doc.kind+': '+doc.completeness_status+'; missing fields: '+(', '.join(doc.missing_information) or 'individual legal review required')+'.')
    actions=[]
    for title,detail,sources in [('Konfliktprüfung und Mandatsannahme','Gegenparteien und verbundene Beteiligte ergänzen; keine Annahme vor Prüfung.',['intake:opponents']),
                                  ('Unterlagen und Vertretungsbefugnis prüfen','Originalvertrag, Korrespondenz, Identität und Zeichnungsberechtigung anfordern.',['intake:matter','intake:client']),
                                  ('Entwürfe und Steuerbehandlung prüfen','Vollmacht, Vergütung und Vorschuss gesondert anwaltlich prüfen; nichts ausstellen.',['intake:fees'])]:
        actions.append(ProposedAction(action_id=uuid.uuid4().hex,kind='task',title=title,detail=detail,source_ids=sources))
    actions.append(ProposedAction(action_id=uuid.uuid4().hex,kind='potential_deadline',title='Mögliche Frist anwaltlich prüfen',
                   detail='Nur Kandidat laut Intake; keine berechnete oder bestätigte Frist und kein Kalendereintrag. Originaldokument, Zugang/Zustellung und Rechtsgrundlage prüfen.',
                   source_ids=['intake:deadline'],candidate_date=request.matter.claimed_deadline))
    if request.synthetic_data:
        actions.append(ProposedAction(action_id=uuid.uuid4().hex,kind='draft_email',title='DEMO Onboarding-E-Mail',
          detail='Nur Entwurf; keine Zustellung und keine Mandatsannahme.',source_ids=['intake:client','intake:scope'],recipient=client.email,
          subject='DEMO — Unterlagen zur Mandatsprüfung: '+matter.title,
          body='Guten Tag '+(client.name or '' )+', wir haben Ihre fiktive Anfrage zur Angelegenheit '+matter.title+' als Demo erfasst. Bitte stellen Sie Originalunterlagen und Angaben zu möglichen Fristen bereit. Vollmacht, Stundenhonorar und Vorschuss sind ausschließlich ungeprüfte Entwürfe. Die Annahme des Mandats und jede externe Handlung bedürfen anwaltlicher Freigabe. Es wurde nichts versandt.'))
    return OnboardingBundle(document_generation_context=request.document_options,synthetic_data=request.synthetic_data,client=client,matter=matter,advance=fee,documents=docs,assessment=report,proposed_actions=actions)


class OnboardingService:
    def __init__(self,db_path=DEFAULT_DB):
        self.db_path=Path(db_path)
        self.rag=LocalRAG(CORPUS)

    def assess(self,request:OnboardingRequest):
        """Prepare the assessment without invoking the legal-document engine."""
        return build_bundle(request,self.rag,include_documents=False)

    def preview(self,request:OnboardingRequest):
        if (not request.synthetic_data and (request.firm is None or request.fees is None or request.fees.net_hourly_rate is None or
            request.fees.proposed_advance_hours is None or request.document_options is None or
            request.document_options.firm_policy is None or request.draft_date is None)):
            raise ServiceError(422,'document_inputs_incomplete','Firm details, fee policy, proposed advance hours and document instructions are required for document drafting.')
        fingerprint=intake_fingerprint(request)
        try:
            self.db_path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with closing(sqlite3.connect(self.db_path,timeout=10)) as db:
                db.execute('PRAGMA foreign_keys=ON');db.execute('BEGIN IMMEDIATE')
                try:
                    db.execute('CREATE TABLE IF NOT EXISTS clients(id TEXT PRIMARY KEY,payload TEXT NOT NULL)')
                    db.execute('CREATE TABLE IF NOT EXISTS matters(id TEXT PRIMARY KEY,client_id TEXT NOT NULL REFERENCES clients(id),payload TEXT NOT NULL)')
                    db.execute('CREATE TABLE IF NOT EXISTS previews(idempotency_key TEXT PRIMARY KEY,fingerprint TEXT NOT NULL,matter_id TEXT NOT NULL REFERENCES matters(id),bundle TEXT NOT NULL)')
                    old=db.execute('SELECT fingerprint,bundle FROM previews WHERE idempotency_key=?',(request.idempotency_key,)).fetchone()
                    if old:
                        if old[0]!=fingerprint:raise ServiceError(409,'idempotency_conflict','This idempotency key already belongs to a different intake.')
                        bundle=OnboardingBundle.model_validate_json(old[1])
                    else:
                        bundle=build_bundle(request,self.rag)
                        db.execute('INSERT INTO clients VALUES(?,?)',(bundle.client.client_id,bundle.client.model_dump_json()))
                        db.execute('INSERT INTO matters VALUES(?,?,?)',(bundle.matter.matter_id,bundle.client.client_id,bundle.matter.model_dump_json()))
                        db.execute('INSERT INTO previews VALUES(?,?,?,?)',(request.idempotency_key,fingerprint,bundle.matter.matter_id,bundle.model_dump_json()))
                    db.commit()
                except BaseException:db.rollback();raise
            os.chmod(self.db_path,0o600)
            return bundle
        except sqlite3.Error:
            raise ServiceError(503,'onboarding_store_unavailable','The local intake store could not complete the transaction.') from None
        except OSError:
            raise ServiceError(503,'onboarding_store_unavailable','The local intake store is unavailable.') from None
        except ServiceError:
            raise
        except Exception:
            raise ServiceError(503,'onboarding_preview_failed','The local preview could not be prepared; no external action was taken.') from None
