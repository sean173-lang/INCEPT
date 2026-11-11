"""Controlled German draft documents: no model calls, network, approval or issuance."""
from dataclasses import dataclass
from decimal import Decimal
from datetime import date
from pathlib import Path
from string import Template
import hashlib
import json
from scripts.document_schemas import DocumentOptions,DocumentIssue
from scripts.onboarding_schemas import DraftDocument,OnboardingRequest,ClientRecord,MatterRecord,AdvanceCalculation
from scripts.local_rag import LocalRAG
from scripts.report_renderer import text

ROOT=Path(__file__).resolve().parents[1]
TEMPLATES=ROOT/'templates/german_legal/v2'
CORPUS=ROOT/'references/legal_documents/corpus.json'
KINDS=('vollmacht','fee_agreement','advance_invoice')
NOTICE='Die gegnerische Partei, ein Verfahrensbeteiligter oder die Staatskasse muss im Falle der Kostenerstattung regelmäßig nicht mehr als die gesetzliche Vergütung erstatten.'

class DocumentRules:
    def __init__(self):
        self.manifest=json.loads((TEMPLATES/'manifest.json').read_text())
        if hashlib.sha256(CORPUS.read_bytes()).hexdigest()!=self.manifest['source_corpus_sha256']:raise ValueError('Document corpus integrity mismatch')
        self.rag=LocalRAG(CORPUS)
        self.version=json.loads(CORPUS.read_text())['version']+'/'+self.rag.version[:12]
    def select(self,kind):
        entry=self.manifest['templates'][kind];rules=[]
        for id in entry['legal_rule_ids']:
            matches=[r for r in self.rag.chunks.values() if r['id']==id and kind in r['document_types']]
            if len(matches)!=1:raise ValueError('Required document-specific rule unavailable')
            rule=matches[0];snapshot=CORPUS.parent/rule['snapshot_path']
            if rule['verification_status']!='source_text_checked' or hashlib.sha256(snapshot.read_bytes()).hexdigest()!=rule['snapshot_sha256'] or not self.rag.validate_reference(rule,'Germany'):raise ValueError('Legal source integrity mismatch')
            rules.append(rule)
        if not rules:raise ValueError('No verified document rules')
        return rules
    def template(self,kind):
        entry=self.manifest['templates'][kind];raw=(TEMPLATES/entry['file']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Template integrity mismatch')
        return Template(raw.decode())

@dataclass(frozen=True)
class DocumentContext:
    request: OnboardingRequest
    client: ClientRecord
    matter: MatterRecord
    advance: AdvanceCalculation
    @property
    def options(self):return self.request.document_options or DocumentOptions()


def issue(code,field,description,severity='missing',sources=()):
    return DocumentIssue(code=code,field=field,description=description,severity=severity,source_ids=list(sources))


def einvoice_assessment(ctx):
    o=ctx.options;year=date.fromisoformat(ctx.request.draft_date).year
    if o.recipient_business_status=='consumer':
        return 'Fallangabe: Privatmandat. Die allgemeine inländische B2B-E-Rechnungspflicht wird daraus nicht abgeleitet; sonstige Rechnungs-, Steuer- und Zustimmungsvoraussetzungen bleiben zu prüfen.'
    if o.recipient_business_status=='business' and o.supplier_domestic is True and o.recipient_domestic is True:
        transition=('Ein Entwurfsdatum vor 2025 belegt keine Anwendbarkeit der späteren E-Rechnungspflicht. Zeitbezogene Rechtslage und tatsächlichen Umsatz gesondert prüfen.' if year<2025 else 'Für Umsätze 2025/2026 kann § 27 Abs. 38 UStG eine Übergangsregelung eröffnen; Leistungszeitraum, Ausgabezeitpunkt und erforderliche Zustimmung sind zu prüfen.' if year<=2026 else
          'Für Umsätze 2027 ist insbesondere die Übergangsregelung bei einem Vorjahresgesamtumsatz bis 800.000 EUR sowie gegebenenfalls EDI zu prüfen; eine Ausnahme wird nicht automatisch bestätigt.' if year==2027 else
          'Die allgemeinen Übergangszeiträume 2026/2027 sind abgelaufen; konkrete gesetzliche Ausnahmen und aktuelle Rechtslage sind zu prüfen.')
        return 'Fallangabe: inländisches B2B-Mandat. Strukturierte E-Rechnung nach § 14 UStG grundsätzlich zu prüfen. '+transition+' Die BMF-FAQ enthält ergänzende Hinweise zu Anzahlungs-, Voraus- und Abschlagsrechnungen. Strukturierte Rechnungsfähigkeit: NICHT BESTÄTIGT.'
    return 'MISSING_INFORMATION: Unternehmereigenschaft, Ansässigkeit und Umsatz-/Leistungszeitraum sind nicht abschließend eingeordnet. E-Rechnungspflicht, Ausnahmen und Übergangsrecht bedürfen individueller Prüfung; keine Formatkonformität bestätigt.'


def amounts(value):return format(Decimal(value),',.2f').replace(',','X').replace('.',',').replace('X','.')


def variables(ctx,rules):
    r=ctx.request;o=ctx.options;p=o.firm_policy;f=ctx.advance
    def supplied(value,label):return text(value) if value is not None else '['+label+' – ERFORDERLICH]'
    representative=''
    if ctx.client.client_type=='company':
        rep=o.representative
        representative=('**Vertreten durch:** '+text(rep.name)+', '+text(rep.role)+'  \n**Befugnisnachweis:** '+supplied(rep.evidence_reference,'NACHWEIS DER VERTRETUNGSBEFUGNIS')+' (Status: '+('synthetischer Nachweis im Demo geprüft; keine reale Bestätigung' if rep.authority_status=='synthetic_evidence_checked' else 'anwaltlich ungeprüft')+')') if rep else '**Vertreten durch:** [NAME, FUNKTION UND BEFUGNISNACHWEIS – ERFORDERLICH]'
    authority=('Vorgesehene Vollmachtserklärung (noch nicht abgegeben): Die oben bezeichnete Mandantschaft bevollmächtigt die genannte Kanzlei, handelnd durch die benannte Rechtsanwältin beziehungsweise den benannten Rechtsanwalt, ausschließlich zur außergerichtlichen Beratung und Vertretung in der unter Ziffer 2 bezeichneten Angelegenheit. Vor Erteilung und Verwendung ist die Erklärung anwaltlich freizugeben.' if o.representation_scope=='out_of_court' else
      '[UMFANG DER VERTRETUNG – ERFORDERLICH]. Für gerichtliche Vertretung oder einen nicht festgelegten Umfang enthält dieses Muster noch keine freigegebene Ermächtigung.')
    if f.vat_mode=='taxable':
        vat='Als ausdrücklich bereitgestellte, noch anwaltlich/steuerlich zu bestätigende Rechenannahme sind '+text(f.vat_percent)+' % Umsatzsteuer vorgesehen. Der rechnerische Stundensatz einschließlich dieser Steuer beträgt '+amounts(Decimal(f.net_hourly_rate)*(1+Decimal(f.vat_percent)/100))+' EUR. Grundlage laut Konfiguration: '+text(r.fees.vat_basis).rstrip('.')+'.'
        vat_line=text(f.vat_percent)+' % · '+amounts(f.vat_amount)+' EUR'
    elif f.vat_mode=='exempt':
        vat='Als zu prüfende Fallangabe ist eine Steuerbefreiung vorgesehen: '+text(r.fees.vat_basis)+'. Eine rechtliche Bestätigung der Befreiung erfolgt nicht.'
        vat_line='nach bereitgestellter, ungeprüfter Befreiungsangabe: 0,00 EUR'
    else:
        vat='[UMSATZSTEUERBEHANDLUNG – ERFORDERLICH]. Steuersatz, Steuerbetrag und Bruttobetrag werden bis zur Klärung nicht festgelegt.';vat_line='[STEUERSATZ UND BETRAG – OFFEN]'
    billing=('Vorgesehen ist die minutengenaue Abrechnung des tatsächlichen Zeitaufwands ohne Aufrundung auf größere Zeiteinheiten.' if p and p.billing_method=='actual_minutes' else
      'Bereitgestellte Abrechnungseinheit: '+str(p.billing_increment_minutes)+' Minuten. [RUNDUNGSVERFAHREN UND ZULÄSSIGKEIT – ZU PRÜFEN]' if p and p.billing_method=='specified_increment' else '[ABRECHNUNGSEINHEIT UND METHODE – ERFORDERLICH]')
    return {'client_name':text(ctx.client.name),'client_address':text(ctx.client.address),'firm_name':text(r.firm.name),'firm_address':text(r.firm.address),'lawyer':text(r.firm.lawyer_name),
       'matter_id':text(ctx.matter.matter_id),'matter_title':text(ctx.matter.title),'opponents':'; '.join(text(x) for x in ctx.matter.opposing_parties) or '[GEGENPARTEI/BETEILIGTE – ERFORDERLICH]',
       'scope':text(ctx.matter.requested_scope),'representative':representative,'authority_clause':authority,'place':supplied(o.place,'ORT'),
       'signer':text(o.representative.name)+' / '+text(o.representative.role) if o.representative and ctx.client.client_type=='company' else text(ctx.client.name) if ctx.client.client_type=='individual' else '[UNTERZEICHNENDE PERSON UND FUNKTION – ERFORDERLICH]',
       'draft_date':r.draft_date,'template_version':rules.manifest['version'],'source_version':rules.version,
       'hourly_net':amounts(f.net_hourly_rate),'net_fee':amounts(f.net_fee),'gross_fee':amounts(f.gross_total)+' EUR' if f.gross_total is not None else '[BRUTTOBETRAG – OFFEN]',
       'vat_clause':vat,'vat_line':vat_line,'billing_clause':billing,
       'time_recording':supplied(p.time_recording if p else None,'ZEITERFASSUNG'),
       'other_professionals':text(p.other_professionals_terms) if p and p.other_professionals_terms else 'Keine zusätzlichen Stundensätze festgelegt; ein Einsatz weiterer Berufsträger bedarf vorheriger gesonderter Klärung.',
       'expenses_terms':supplied(p.expenses_terms if p else None,'AUSLAGENREGELUNG'),'payment_terms':supplied(p.payment_terms if p else None,'ZAHLUNGSBEDINGUNGEN'),
       'payment_instructions':text(p.payment_instructions) if p and p.payment_instructions else 'Nicht bereitgestellt; keine Kontoverbindung und keine Zahlungsanweisung freigegeben.',
       'tax_identifier':supplied(p.tax_identifier if p else None,'STEUERNUMMER ODER UST-IDNR.'),'invoice_number':supplied(o.invoice_number,'EINMALIGE RECHNUNGSNUMMER'),
       'issue_date':supplied(o.invoice_issue_date,'AUSSTELLUNGSDATUM'),
       'payment_received_date':text(o.payment_received_date) if o.payment_received_date else 'Kein Zahlungseingang bestätigt; tatsächlichen Zeitpunkt nur bei feststehender Vereinnahmung ergänzen.',
       'einvoice_clause':einvoice_assessment(ctx)}


def required_checks(kind,ctx):
    o=ctx.options;p=o.firm_policy;items=[]
    if ctx.client.client_type=='unknown':items.append(issue('client_type','client.client_type','Mandantschaft als natürliche Person oder Gesellschaft einordnen.'))
    if not ctx.matter.opposing_parties:items.append(issue('opponents','matter.opposing_parties','Gegenpartei/Beteiligte für Mandat und Konfliktprüfung ergänzen.'))
    if ctx.client.client_type=='company':
        if o.representative is None:items.append(issue('representative','document_options.representative','Person, Funktion und Befugnisnachweis fehlen.',sources=['bgb-164','bgb-167'] if kind=='vollmacht' else []))
        elif o.representative.authority_status!='synthetic_evidence_checked':items.append(issue('authority_unverified','document_options.representative.authority_status','Vertretungsbefugnis wurde nicht anhand eines Nachweises geprüft.','review',['bgb-164'] if kind=='vollmacht' else []))
    if ctx.client.client_type=='company' and o.representative and not o.representative.evidence_reference:
        items.append(issue('representative_evidence','document_options.representative.evidence_reference','Befugnisnachweis der benannten Person fehlt.',sources=['bgb-164'] if kind=='vollmacht' else []))
    if kind=='fee_agreement' and not o.place:items.append(issue('place','document_options.place','Ort der vorgesehenen Erklärung ergänzen.'))
    if kind=='vollmacht':
        if o.engagement_law!='Germany':items.append(issue('power_law_unresolved','document_options.engagement_law','Anwendbares Vollmachtsrecht und Form für den konkreten Gebrauch prüfen.','review',['bgb-167']))
        if not o.place:items.append(issue('place','document_options.place','Ort der Erklärung ergänzen.'))
        if o.representation_scope=='unspecified':items.append(issue('authority_scope','document_options.representation_scope','Vertretungsumfang ausdrücklich festlegen.',sources=['bgb-167']))
        elif o.representation_scope!='out_of_court':items.append(issue('procedural_scope','document_options.representation_scope','Gerichtliche Vollmacht benötigt eine gesonderte geprüfte Vorlage; keine Prozessmacht gerendert.','review',['bgb-167','bgb-174']))
        if o.requested_ancillary_powers:items.append(issue('extra_powers','document_options.requested_ancillary_powers','Zusatzbefugnisse sind nicht von dieser Vorlage freigegeben und werden nicht erteilt.','review',['bgb-181']))
    else:
        if o.engagement_law!='Germany':items.append(issue('fee_law_unresolved','document_options.engagement_law','Anwendbares anwaltliches Vergütungsrecht und Zulässigkeit der Vereinbarung prüfen.','review',['rvg-3a'] if kind=='fee_agreement' else ['rvg-9']))
        if not p:items.append(issue('firm_policy','document_options.firm_policy','Bereitgestellte Kanzleiregeln fehlen.'))
        else:
            if Decimal(p.net_hourly_rate)!=Decimal(ctx.request.fees.net_hourly_rate):items.append(issue('fee_policy_mismatch','document_options.firm_policy.net_hourly_rate','Kanzleikonfiguration und Mandatsstundensatz widersprechen sich.','error'))
            if kind=='fee_agreement':
                for field in ('time_recording','expenses_terms','payment_terms'):
                    if getattr(p,field) is None:items.append(issue(field,'document_options.firm_policy.'+field,'Regelung ausdrücklich bereitstellen: '+field))
                if p.billing_method=='unknown':items.append(issue('billing_method','document_options.firm_policy.billing_method','Keine Abrechnungseinheit oder Methode festgelegt.'))
                if p.billing_method=='specified_increment':items.append(issue('rounding_method','document_options.firm_policy.billing_method','Rundungsverfahren und rechtliche Zulässigkeit gesondert prüfen.','review',['rvg-3a']))
        if ctx.request.fees.vat_mode=='unknown':items.append(issue('vat_unknown','fees.vat_mode','Steuerbehandlung und Bruttoentgelt sind offen.',sources=['ustg-14'] if kind=='advance_invoice' else ['ustg-12','ustg-19']))
        elif not p or not p.vat_configuration_confirmed_for_demo:items.append(issue('vat_unconfirmed','document_options.firm_policy.vat_configuration_confirmed_for_demo','Übernommene Steuerannahme ist nicht ausdrücklich für den Demo-Fall bestätigt.','review',['ustg-12','ustg-19']))
    if kind=='advance_invoice':
        if o.payment_received_date and date.fromisoformat(o.payment_received_date)>date.fromisoformat(ctx.request.draft_date):items.append(issue('future_receipt','document_options.payment_received_date','Ein künftiges Datum darf nicht als bereits erfolgte Vereinnahmung dargestellt werden.','error',['ustg-14','ustg-13']))
        for field,value in [('invoice_issue_date',o.invoice_issue_date),('invoice_number',o.invoice_number),('firm_policy.tax_identifier',p.tax_identifier if p else None)]:
            if value is None or 'DEMO' in value.upper() or '[' in value:items.append(issue('invoice_'+field,'document_options.'+field,'Pflichtangabe vor Ausstellung ergänzen: '+field,sources=['ustg-14']))
        items.append(issue('einvoice_review','document_options.recipient_business_status',einvoice_assessment(ctx),'review',['ustg-14','ustg-27','bmf-einvoice']))
    return items


def validate_document(kind,body,ctx,rules=None):
    rules=rules or DocumentRules();refs=rules.select(kind);items=required_checks(kind,ctx)
    expected=rules.template(kind).substitute(variables(ctx,rules))
    if body!=expected:items.append(issue('template_integrity','content_markdown','Text weicht von kontrollierter Vorlage oder validierten Mandatsdaten ab.','error'))
    for field,expected_value in [('client',ctx.request.client.name),('client_address',ctx.request.client.address),('firm',ctx.request.firm.name),('matter',ctx.matter.matter_id)]:
        if text(expected_value) not in body:items.append(issue('identity_'+field,field,'Partei oder Mandatsreferenz fehlt oder wurde verändert.','error'))
    if any(getattr(ctx.client,key)!=value for key,value in ctx.request.client.model_dump().items()) or ctx.matter.client_id!=ctx.client.client_id or any(getattr(ctx.matter,key)!=value for key,value in ctx.request.matter.model_dump().items()):items.append(issue('context_mismatch','document_context','Client-/Matter-Daten stimmen nicht mit dem validierten Intake überein.','error'))
    from scripts.onboarding import advance
    if ctx.advance!=advance(ctx.request.fees):items.append(issue('arithmetic_mismatch','advance','Berechnungen weichen von Decimal-Ausgangsdaten ab.','error'))
    if kind=='fee_agreement' and NOTICE not in body:items.append(issue('mandatory_notice','content_markdown','Kostenerstattungshinweis fehlt.','error',['rvg-3a']))
    if kind=='vollmacht' and ('Vorgesehener Stundensatz' in body or 'Hinweis zur Kostenerstattung' in body):items.append(issue('fee_in_power','content_markdown','Vergütungsvereinbarung darf nicht Teil der Vollmacht sein.','error',['rvg-3a']))
    return items


def validate_vollmacht(body,ctx):return validate_document('vollmacht',body,ctx)
def validate_fee_agreement(body,ctx):return validate_document('fee_agreement',body,ctx)
def validate_advance_invoice(body,ctx):return validate_document('advance_invoice',body,ctx)


def cross_validate(documents,ctx):
    issues=[]
    if len(documents)!=3 or {d.kind for d in documents}!=set(KINDS):issues.append(issue('document_set','documents','Genau drei unterschiedliche Dokumenttypen erforderlich.','error'))
    for d in documents:
        issues.extend(i for i in validate_document(d.kind,d.content_markdown,ctx) if i.severity=='error')
    return issues


def generate_documents(request,client,matter,fee):
    ctx=DocumentContext(request,client,matter,fee);rules=DocumentRules();docs=[]
    for kind in KINDS:
        refs=rules.select(kind);body=rules.template(kind).substitute(variables(ctx,rules));items=validate_document(kind,body,ctx,rules)
        errors=any(i.severity=='error' for i in items);missing=[i.field for i in items if i.severity=='missing']
        status='GENERATION_FAILED' if errors else 'NOT_READY_FOR_ISSUANCE' if kind=='advance_invoice' else 'MISSING_INFORMATION' if missing else 'LEGAL_REVIEW_REQUIRED' if any(i.severity=='review' for i in items) else 'DRAFT_COMPLETE_FOR_LAWYER_REVIEW'
        if errors:body='# DEMO — Dokumenterzeugung abgebrochen\n\nWidersprüchliche Mandats-, Parteien- oder Vergütungsdaten verhindern einen konsistenten Entwurf. Anwaltliche Klärung erforderlich; keine Freigabe oder externe Handlung.'
        docs.append(DraftDocument(document_version=2,kind=kind,template_id='de-'+kind,template_version=rules.manifest['version'],source_version=rules.version,completeness_status=status,validation_issues=items,missing_information=missing,lawyer_review_questions=[i.description for i in items if i.severity=='review']+['Vorlage und Einzelfall professionell prüfen; automatische Validierung ist keine Rechtsfreigabe.'],legal_source_ids=[r['id'] for r in refs],content_markdown=body))
    if all(d.completeness_status!='GENERATION_FAILED' for d in docs) and cross_validate(docs,ctx):
        raise ValueError('Cross-document validation failed')
    return docs
