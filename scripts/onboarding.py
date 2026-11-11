"""Offline intake preview. Local persistence only; no delivery/approval executor exists."""
from contextlib import closing
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid

from scripts.company_service import ServiceError
from scripts.local_rag import LocalRAG
from scripts.report_renderer import text
from scripts.onboarding_schemas import (OnboardingRequest, OnboardingBundle, ClientRecord, MatterRecord,
    AdvanceCalculation, DraftDocument, AssessmentFinding, AssessmentSource, MandateAssessment, ProposedAction)

ROOT=Path(__file__).resolve().parent.parent
DEFAULT_DB=ROOT/'data/legal_intake_mvp/onboarding.sqlite3'
CORPUS=ROOT/'references/mandate_intake.json'
LABEL='DEMO / ENTWURF — fiktive Daten; nicht unterschrieben, nicht versandt; anwaltliche Freigabe erforderlich.'


def money(value):return format(value.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP),'.2f')


def intake_fingerprint(request):
    """Keep existing persisted legacy request keys valid after optional schema additions."""
    data=request.model_dump(mode='json')
    for person in ('client','firm'):
        for key,default in {'client_type':'unknown','registration_number':None,'register_court':None,'register_type':None,'approved_provider_id':None}.items():
            if data[person].get(key)==default:data[person].pop(key,None)
    if data['matter'].get('governing_law') is None:data['matter'].pop('governing_law',None)
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def advance(fees):
    net=Decimal(fees.net_hourly_rate)*Decimal('5')
    vat=None if fees.vat_mode=='unknown' else Decimal('0') if fees.vat_mode=='exempt' else (net*Decimal(fees.vat_percent)/Decimal('100')).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
    return AdvanceCalculation(net_hourly_rate=money(Decimal(fees.net_hourly_rate)),net_fee=money(net),vat_mode=fees.vat_mode,
                              vat_percent=fees.vat_percent,vat_amount=money(vat) if vat is not None else None,
                              gross_total=money(net+vat) if vat is not None else None)


def assessment(request,rag):
    evidence=[('intake:client','client','Fiktive Mandantschaft laut Intake: '+request.client.name),
              ('intake:matter','matter.summary',request.matter.summary),
              ('intake:scope','matter.requested_scope',request.matter.requested_scope),
              ('intake:fees','fees',request.fees.model_dump_json()),
              ('intake:opponents','matter.opposing_parties',json.dumps(request.matter.opposing_parties,ensure_ascii=False)),
              ('intake:deadline','matter.claimed_deadline',json.dumps({'claimed_date':request.matter.claimed_deadline,'source':request.matter.deadline_source},ensure_ascii=False))]
    sources=[AssessmentSource(source_id=i,kind='synthetic_intake',locator=loc,content=body) for i,loc,body in evidence]
    facts=[AssessmentFinding(description='Unverified synthetic intake statement: '+body,status='unverified_intake_statement',source_ids=[i]) for i,_,body in evidence[:3]]
    legacy_german_demo=(request.matter.governing_law is None and request.client.jurisdiction=='Germany' and request.client.client_type=='unknown')
    german_guidance=request.matter.governing_law=='Germany' or legacy_german_demo
    references=rag.query('mandate authority fee advance conflict confidentiality','Germany',top_k=5) if german_guidance else []
    if german_guidance and len(references)!=4:raise ServiceError(503,'mandate_references_unavailable','The reviewed mandate reference set could not be retrieved.')
    guidance=[]
    for ref in references:
        source_id=ref['chunk_id']
        sources.append(AssessmentSource(source_id=source_id,kind='legal_reference',locator=ref['locator'],content=ref['text'],url=ref['source_url'],reviewed_at=ref['reviewed_at'],document_date=ref['document_date']))
        guidance.append(AssessmentFinding(description=ref['text'],status='reference_guidance',source_ids=[source_id]))
    gaps=['Original contract, correspondence and supporting documents have not been reviewed.',
          'Identity, signing authority, conflict check and mandate acceptance are not verified.',
          'Claim merits, applicable substantive law, limitation periods and procedural deadlines are not determined.',
          'VAT applicability, fee agreement enforceability and appropriateness of the five-hour advance require lawyer review.']
    if not german_guidance:gaps.append('Substantive '+str(request.matter.governing_law or 'unknown governing law')+' legal analysis is NOT VERIFIED / REQUIRES LAWYER REVIEW; German law is not assumed to govern this matter. DEMO engagement terms require jurisdiction-specific review.')
    if not request.matter.opposing_parties:gaps.append('Opposing parties are missing; a conflict search cannot be completed.')
    if not request.matter.claimed_deadline:gaps.append('No supported deadline date is supplied; no deadline has been calculated.')
    else:gaps.append('The supplied deadline is an unverified candidate; original notice/service evidence and lawyer confirmation are required.')
    lines=['# DEMO Mandate Assessment Report','',LABEL,'','Conclusion: lawyer review required. Confidence: insufficient for legal conclusions.','','## Intake evidence — unverified','']
    for fact in facts:lines+=['- '+text(fact.description)+' ['+', '.join(fact.source_ids)+']']
    lines+=['','## Retrieved reference guidance — not findings about the matter','']
    for finding in guidance:lines+=['- '+text(finding.description)+' ['+', '.join(finding.source_ids)+']']
    lines+=['','## Missing information','']+['- '+text(g) for g in gaps]+['','## Sources','']
    for source in sources:
        lines+=['- '+text(source.source_id)+': '+text(source.locator)+(f' — [{text(source.locator)}]({source.url}); reviewed '+text(source.reviewed_at)+'; enactment date not supplied.' if source.url else '; synthetic user-supplied intake, unverified.')]
    return MandateAssessment(factual_findings=facts,guidance=guidance,missing_information=gaps,sources=sources,
                            corpus_version=rag.version,content_markdown='\n'.join(lines)+'\n')


def build_bundle(request,rag):
    client=ClientRecord(**request.client.model_dump(),client_id='demo-client-'+uuid.uuid4().hex)
    matter=MatterRecord(**request.matter.model_dump(),client_id=client.client_id,matter_id='demo-matter-'+uuid.uuid4().hex)
    fee=advance(request.fees);report=assessment(request,rag)
    header=LABEL+'\n\nMandantschaft: '+text(client.name)+'; '+text(client.address)+'\nKanzlei: '+text(request.firm.name)+'; '+text(request.firm.address)+'\nRechtsanwalt/Rechtsanwältin (DEMO): '+text(request.firm.lawyer_name)+'\nAktenzeichen: '+matter.matter_id+'\nEntwurfsdatum: '+request.draft_date+'\n\n'
    authority='# DEMO Vollmacht\n\n'+header+'Die fiktive Mandantschaft beabsichtigt, die oben genannte fiktive anwaltliche Vertretung ausschließlich für folgende Angelegenheit zu bevollmächtigen:\n\n'+text(matter.title)+' — '+text(matter.requested_scope)+'\n\nUmfang, Prozessführung, Vergleichsabschluss, Empfang von Geldern und Untervollmacht sind NICHT freigegeben und bedürfen gesonderter anwaltlicher Festlegung. Keine Vergütungsvereinbarung ist Bestandteil dieses Entwurfs.\n\nUnterschrift Mandantschaft: __________________ (nicht geleistet)\n'
    agreement='# DEMO Vergütungsvereinbarung — Stundenhonorar\n\n'+header+'Gesonderter, noch nicht vereinbarter Entwurf zur Angelegenheit '+text(matter.title)+'.\n\nVorgesehener Netto-Stundensatz: '+fee.net_hourly_rate+' EUR. Abzurechnen wäre tatsächlicher, dokumentierter Zeitaufwand; Zeittakt, Auslagen und weitere Bedingungen sind vor Vereinbarung zu prüfen. Kein Erfolgshonorar.\n\nUmsatzsteuerbehandlung: '+text(request.fees.vat_mode)+'; angegebener Prozentsatz: '+text(request.fees.vat_percent)+'; vom Intake gelieferte Grundlage: '+text(request.fees.vat_basis)+'. Keine steuerliche Bestätigung.\n\nIm Erstattungsfall müssen Gegner, andere Verfahrensbeteiligte oder die Staatskasse regelmäßig nicht mehr als die gesetzliche Vergütung erstatten.\n\nAnwendbarkeit, Form, Hinweise und Angemessenheit durch die Kanzlei prüfen. Nicht Bestandteil der Vollmacht. Keine Unterschriften geleistet.\n'
    invoice='# DEMO Vorschussrechnung — DRAFT, NICHT AUSGESTELLT\n\n'+header+'Nur Entwurfsreferenz: DRAFT-'+matter.matter_id+' (keine fortlaufende Rechnungsnummer).\n\nVorschuss auf erwartete künftige anwaltliche Tätigkeit, KEINE bereits erbrachte Leistung. Fünf Stunden sind eine Demo-Kalkulationsannahme, keine bestätigte Aufwandsschätzung.\n\n5 Stunden × '+fee.net_hourly_rate+' EUR netto = '+fee.net_fee+' EUR netto.\nUmsatzsteuer ('+text(fee.vat_percent)+' %; '+text(fee.vat_mode)+'): '+text(fee.vat_amount)+' EUR.\nBrutto-Vorschuss: '+text(fee.gross_total)+' EUR.\n\nSteuerliche Grundlage nur laut Intake: '+text(request.fees.vat_basis)+'. Bei unbekannter Steuerbehandlung bleiben Steuerbetrag und Brutto offen. Keine erfundenen Steuer-/USt-IDs, Bankdaten, Leistungsdaten oder Zahlungsfristen. Pflichtangaben und Angemessenheit prüfen; nicht buchen, versenden oder bezahlen.\n'
    docs=[DraftDocument(kind=kind,content_markdown=body) for kind,body in (('vollmacht',authority),('fee_agreement',agreement),('advance_invoice',invoice))]
    actions=[]
    for title,detail,sources in [('Konfliktprüfung und Mandatsannahme','Gegenparteien und verbundene Beteiligte ergänzen; keine Annahme vor Prüfung.',['intake:opponents']),
                                  ('Unterlagen und Vertretungsbefugnis prüfen','Originalvertrag, Korrespondenz, Identität und Zeichnungsberechtigung anfordern.',['intake:matter','intake:client']),
                                  ('Entwürfe und Steuerbehandlung prüfen','Vollmacht, Vergütung und Vorschuss freigeben; keine Rechnung ausstellen.',['intake:fees'])]:
        actions.append(ProposedAction(action_id=uuid.uuid4().hex,kind='task',title=title,detail=detail,source_ids=sources))
    actions.append(ProposedAction(action_id=uuid.uuid4().hex,kind='potential_deadline',title='Mögliche Frist anwaltlich prüfen',
                   detail='Nur Kandidat laut Intake; keine berechnete oder bestätigte Frist und kein Kalendereintrag. Originaldokument, Zugang/Zustellung und Rechtsgrundlage prüfen.',
                   source_ids=['intake:deadline'],candidate_date=request.matter.claimed_deadline))
    actions.append(ProposedAction(action_id=uuid.uuid4().hex,kind='draft_email',title='DEMO Onboarding-E-Mail',
                   detail='Nur Entwurf; keine Zustellung und keine Mandatsannahme.',source_ids=['intake:client','intake:scope'],recipient=client.email,
                   subject='DEMO — Unterlagen zur Mandatsprüfung: '+matter.title,
                   body='Guten Tag '+client.name+', wir haben Ihre fiktive Anfrage zur Angelegenheit '+matter.title+' als Demo erfasst. Bitte stellen Sie Originalunterlagen und Angaben zu möglichen Fristen bereit. Vollmacht, Stundenhonorar und Vorschuss sind ausschließlich ungeprüfte Entwürfe. Die Annahme des Mandats und jede externe Handlung bedürfen anwaltlicher Freigabe. Es wurde nichts versandt.'))
    return OnboardingBundle(client=client,matter=matter,advance=fee,documents=docs,assessment=report,proposed_actions=actions)


class OnboardingService:
    def __init__(self,db_path=DEFAULT_DB):
        self.db_path=Path(db_path)
        self.rag=LocalRAG(CORPUS)

    def preview(self,request:OnboardingRequest):
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
            raise ServiceError(503,'onboarding_store_unavailable','The local demo store could not complete the preview transaction.') from None
        except OSError:
            raise ServiceError(503,'onboarding_store_unavailable','The local demo store is unavailable.') from None
        except ServiceError:
            raise
        except Exception:
            raise ServiceError(503,'onboarding_preview_failed','The local preview could not be prepared; no external action was taken.') from None
