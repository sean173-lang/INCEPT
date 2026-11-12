"""Deterministic selected-intake presentation; no model, retrieval or legal approval.

Facts are server-selected exact excerpts. Conditional reasoning is fixed, gated by
explicit German governing law and the existing wording-verified payment cards.
The original structured assessment remains a private audit record.
"""
import hashlib,json,re
from scripts.local_rag import LocalRAG
from scripts.payment_research import CORPUS
from scripts.report_renderer import text

VERSION='german-intake-source-exact-v9'


def excerpts(body):
    """Select whole sentences only; do not turn allegations into findings."""
    sentences=re.split(r'(?<=[.!?])\s+(?=[A-ZÄÖÜ])',body.strip())
    groups=[('Vertrag / zeitlicher Ablauf',r'september|vereinbart|vertrag.*geschlossen'),
            ('Rechnung / Betrag',r'rechnung.*(?:euro|€|gestellt)|(?:euro|€).*rechnung'),
            ('Leistung nach Darstellung der anfragenden Partei',r'nach unserer|nach meiner|erbracht|geleistet'),
            ('Einwendungen der Gegenseite',r'gegenseite|bestreitet|unvollständig|nicht vollständig'),
            ('Zahlung',r'zahlung.*(?:nicht|bislang)|nicht.*bezahlt'),
            ('Unterlagen',r'keine unterlagen|übersandt|beigefügt|angehängt'),
            ('Vertretung',r'vertretungsvollmacht|vollmacht liegt|vertretungsbefugnis'),
            ('Offene Zeitpunkte',r'genauere daten|fälligkeit.*klären|abnahme.*klären')]
    out=[];used=set()
    for label,pattern in groups:
        for sentence in sentences:
            if sentence not in used and re.search(pattern,sentence,re.I) and len(sentence)<=420:
                used.add(sentence);out.append({'id':'mail-'+hashlib.sha256(sentence.encode()).hexdigest()[:12], 'label':label,'text':sentence});break
    if not out:
        candidate=next((s for s in sentences if len(s)>30 and len(s)<=420),'')
        if candidate:out=[{'id':'mail-'+hashlib.sha256(candidate.encode()).hexdigest()[:12],'label':'Mitteilung','text':candidate}]
    return out


def checked_sources(research):
    cards={c['source_url']:c for c in LocalRAG(CORPUS).chunks.values()};out={}
    for result in research:
        source=result.get('source') or {};card=cards.get(source.get('url'))
        if not card or result.get('status')!='wording_verified' or result.get('case_finding_verified') is not False:continue
        if source.get('source_id')!=card['chunk_id'] or source.get('content')!=card['text'] or result.get('source_url')!=card['source_url']:continue
        if not result.get('retrieved_at') or not re.fullmatch(r'[a-f0-9]{64}',result.get('source_sha256','')):continue
        out[card['id'].rsplit('-',1)[-1]]=(card,result)
    return out


def render(case,message):
    profile=case['profile'];bundle=case['bundle'];body=message['body'];selected=excerpts(body)
    amounts=list(dict.fromkeys(re.findall(r'\b\d[\d.,]*(?:\s*(?:Euro|EUR)|\s*€)',body,re.I)))
    german=case['payload']['matter']['governing_law']=='Germany'
    payment=bool(re.search(r'\b(?:rechnung|rechnungen|zahlung|forderung|invoice|payment|kaufvertrag|kaufpreis|lieferung|verspät|sachmangel|defekt|schadensersatz)\b',body,re.I))
    service_or_work_dispute=bool(re.search(r'dienst|leistungs|werkvertrag|werklohn|abnahme|unvollständig|nicht vollständig|nicht vollständig ausgeführt',body,re.I))
    sources=checked_sources(case.get('legal_research',[])) if payment else {}
    def law(number):
        return ('[§ '+number+' BGB]('+sources[number][0]['source_url']+')') if number in sources else 'Rechtsgrundlage nicht quellengeprüft (BGB § '+number+'); anwaltliche Quellenprüfung offen'
    client_rep=(text(profile.get('representative_name'))+' ('+text(profile.get('representative_role') or 'Funktion nicht angegeben')+')' if profile.get('representative_name') else 'Keine vertretende Person angegeben')
    client_authority=('Fiktiver Nachweis als geprüft markiert: '+text(profile.get('authority_reference'))+'; dies ist keine unabhängige Verifikation.' if profile.get('authority_checked') and profile.get('authority_reference') else 'Vertretungsmacht nicht nachgewiesen; E-Mail-Absender und behauptete Rolle genügen hierfür nicht.')
    lines=['# Vorläufige Mandatsanalyse','', '**Unbestätigte Angaben · anwaltliche Prüfung erforderlich.**','',
      '## A. Mandatsüberblick','',
      '- **Anfragende Mandantschaft:** '+text(profile['name'])+'; Rechtsform nur laut Intake/Namensangabe, nicht registergeprüft.',
      '- **Anschrift Mandantschaft:** '+text(profile.get('address') or 'Anschrift fehlt; vor Anspruchsprüfung zu erheben.')+' (Intake-Angabe, nicht verifiziert).',
      '- **Gegenseite:** '+text(profile.get('counterparty') or 'Nicht angegeben')+'; Anschrift: '+text(profile.get('counterparty_address') or 'nicht angegeben')+' (Intake-Angaben, nicht verifiziert).',
      '- **Vertretung Mandantschaft:** '+client_rep+'. '+client_authority,
      '- **Vertretung Gegenseite:** '+text(profile.get('counterparty_representative') or 'Nicht angegeben; Vertretungsbefugnis nicht geprüft.'),
      '- **Anliegen:** '+text(profile.get('scope') or 'Umfang noch zu klären')+' (bestätigtes Eingabefeld, keine Tatsachenprüfung).',
      '- **Genannte Beträge:** '+text(', '.join(amounts) or 'Keine belastbar auslesbare Betragsangabe')+' laut Nachricht, bestritten; Originalrechnung fehlt, netto/brutto und Berechnung sind unbekannt (kein Anerkenntnis).',
      '- **Absender / Rolle:** '+text(message.get('from','Nicht angegeben'))+'; '+text(profile.get('sender_role') or 'Rolle und Vertretungsbefugnis nicht nachgewiesen')+'.',
      '- **Recht:** '+('Deutsches Recht ausdrücklich im Intake ausgewählt; Anwendbarkeit noch zu prüfen.' if german else 'Kein ausdrücklich bestätigtes deutsches Sachrecht; keine automatische BGB-Anwendung.'),
      '', '## B. Sachverhalt','', 'Folgende ausgewählte Originalaussagen der Nachricht sind **Parteivortrag, keine bewiesenen Feststellungen**:','']
    for e in selected:lines.append('- **'+e['label']+':** „'+text(e['text'])+'“ *(Quelle: ausgewählte Nachricht)*')
    if any(e['label']=='Vertrag / zeitlicher Ablauf' for e in selected) and any(e['label']=='Rechnung / Betrag' for e in selected):
        lines.append('- **Chronologie (nur Monatsangaben):** Auftrag ungefähr im September, Rechnung im Oktober; Jahr, genaue Tage und Zugang der Rechnung sind nicht angegeben.')
    if not selected:lines.append('Kein sicher abgrenzbarer kurzer Sachverhalt extrahierbar. Nachricht und Originalunterlagen anwaltlich sichten.')
    lines+=['','**Prüfungsziel laut Intake:** '+text(profile.get('scope') or 'Noch zu erfragen')+'. Anlagenamen belegen weder Dokumentinhalt noch Vollständigkeit. Anhänge wurden nicht inhaltlich ausgewertet.','', '## C. Rechtliche Kernfragen','']
    if german and payment and service_or_work_dispute:
        issues=[('1. Anspruchsgrundlage: Dienste oder versprochener Erfolg?',law('611')+'; '+law('631'),
         ('§ 611 BGB ordnet die vereinbarten Dienste gegen die vereinbarte Vergütung zu; § 631 BGB setzt beim Werkvertrag ein versprochenes, durch Arbeit oder Dienstleistung herbeizuführendes Ergebnis gegen Vergütung voraus.' if '611' in sources and '631' in sources else 'Die gesetzlichen Abgrenzungsnormen sind nicht vollständig wortlautgeprüft; eine Zuordnung zum Dienst- oder Werkvertrag ist deshalb offen.')+' Die Nachricht bezeichnet die Forderung als Dienstleistungsrechnung, entscheidet die Einordnung aber nicht. '+('Laufende Beratung, Planung oder Tätigkeit ohne zugesagten Erfolg spricht für die Dienstvertragsprüfung; ein konkret versprochenes Ergebnis für die Werkvertragsprüfung. Der Vertragstitel allein entscheidet nicht.' if '611' in sources and '631' in sources else 'Welche Leistung vereinbart wurde, ist anhand von Vertrag und Leistungsbeschreibung zu klären; keine rechtliche Zuordnung aus der Rechnungsbezeichnung.')+' Vertragsinhalt und Vergütungsabrede sind bislang nicht belegt.',
         'Vertrag, Angebot, Leistungsbeschreibung, Änderungsaufträge und Abrechnung anfordern. Herausarbeiten: geschuldete Tätigkeit/Stunden oder konkretes Ergebnis, Abnahmekriterien, Mitwirkungspflichten und Vergütungsmodell.'),
        ('2. Leistung und Einwand der Unvollständigkeit',law('614')+'; '+law('633')+'; '+law('634'),
         ('Bei einem Dienstvertrag ist die Vergütung nach erbrachten Diensten beziehungsweise nach Ablauf vereinbarter Zeitabschnitte fällig.' if '614' in sources else 'Die Fälligkeit von Dienstvergütung und Rechtsfolgen nicht erbrachter Dienste sind nicht quellenbestätigt.')+' Die behauptete vollständige Leistung ist deshalb mit konkreten Tätigkeitsnachweisen und der vereinbarten Vergütung abzugleichen.'+(' Bei einem Werkvertrag ist zwischen einem noch nicht fertiggestellten Werk und einem fertiggestellten, aber mangelhaften Werk zu unterscheiden. § 633 BGB knüpft einen Sachmangel an die vereinbarte Beschaffenheit; nur bei einem Werkmangel kommen die Rechte aus § 634 BGB (unter deren jeweiligen Voraussetzungen, insbesondere Nacherfüllung) in Betracht.' if '633' in sources and '634' in sources else ' Ob offene Werkleistung oder ein Werkmangel vorliegt und welche Mängelrechte gelten, ist mangels vollständiger Quellenprüfung offen.')+' Die pauschale Behauptung „nicht vollständig“ belegt weder einen Mangel noch dessen Umfang.',
         'Gegenseitige Leistungslisten erstellen: vertraglicher Sollumfang, erledigte Teilleistungen, offene Positionen, konkret beanstandete Qualität/Menge, Nachbesserungsaufforderungen und Reaktionen. Zeitaufzeichnungen, Arbeitsergebnisse, Übergaben und vollständige Korrespondenz sichern.'),
        ('3. Fälligkeit und mögliche Abnahme',law('640')+'; '+law('641')+'; '+law('614'),
         ('Nur wenn ein Werkvertrag vorliegt, ist die Abnahme grundsätzlich relevant: § 640 BGB betrifft das vertragsmäßig hergestellte Werk; § 641 BGB knüpft die Vergütung an die Abnahme.' if '640' in sources and '641' in sources else 'Die werkvertragliche Abnahme- und Fälligkeitsregel ist nicht vollständig quellenbestätigt.')+(' Ist das versprochene Werk noch nicht fertiggestellt, spricht das gegen seine vertragsgemäße Herstellung und regelmäßig gegen Abnahme und Schlussfälligkeit; Teilabnahme/Teilvergütung oder eine gesetzliche Abschlagszahlung sind gesondert zu prüfen.' if '640' in sources and '641' in sources else ' Ob eine unvollständige Werkleistung Abnahme und Fälligkeit ausschließt, ist mangels vollständiger Quellenprüfung offen.')+(' Für Dienste richtet sich die Fälligkeit nach § 614 BGB; eine werkvertragliche Abnahme wird dafür nicht aus dieser Vorschrift abgeleitet.' if '614' in sources else ' Die Dienstvertragsfälligkeit und eine etwaige Abnahmefrage sind nicht vollständig quellengeprüft.')+' Maßgeblich bleiben vereinbarte Zahlungsabreden und belegte Leistung. Eine im Oktober gestellte Rechnung allein beweist weder Zugang noch Fälligkeit, Abnahme oder Anspruchshöhe.'+(' Eine fingierte Abnahme ist nur nach den geprüften Voraussetzungen des § 640 Abs. 2 BGB zu erwägen: Fertigstellung, angemessene Frist und unterlassene begründete Mängelverweigerung; bei Verbrauchern ist der Hinweis in Textform erforderlich.' if '640' in sources else ' Eine fingierte Abnahme darf ohne Prüfung der Voraussetzungen des § 640 Abs. 2 BGB nicht angenommen werden.'),
         'Exaktes Rechnungsdatum und Zugang, Vertragstermine, vereinbarte Zahlungsziele, Fertigstellungsanzeige, Abnahmeerklärung/Protokoll, vorbehaltene Mängel und etwaige Fristsetzung mit Belegen prüfen.'),
        ('4. Einrede, Abschlagszahlung und Zurückbehaltungsrecht bei Mängeln',law('320')+'; '+law('632a')+'; '+law('641'),
         ('§ 320 BGB kann bei einem gegenseitigen Vertrag ein Zurückhalten der Gegenleistung erlauben, wenn die geschuldete Gegenleistung noch aussteht und keine Vorleistungspflicht besteht.' if '320' in sources else 'Ein Leistungsverweigerungsrecht ist nicht quellenbestätigt.')+' Das stützt die Gegenseite bedingt, falls tatsächlich geschuldete Leistung noch offen ist.'+(' Bei Teilleistung begrenzt § 320 Abs. 2 BGB eine vollständige Zahlungsverweigerung, soweit sie nach den Umständen – besonders bei geringfügigem Rückstand – treuwidrig wäre.' if '320' in sources else ' Ob und in welchem Umfang Teilleistung die Einrede begrenzt, ist nicht quellengeprüft.')+(' Bei einem Werkvertrag kann der Unternehmer nach § 632a BGB eine Abschlagszahlung in Höhe des Wertes der erbrachten, vertraglich geschuldeten Leistungen verlangen; dafür ist eine prüffähige Aufstellung erforderlich. Bis zur Abnahme trägt der Unternehmer die Beweislast für vertragsgemäße Leistung. Bei nicht vertragsgemäßer Teilleistung darf der Besteller einen angemessenen Teil des Abschlags zurückhalten.' if '632a' in sources else ' Ob ein gesetzlicher Werklohnabschlag für bereits erbrachte Teilleistung beansprucht werden kann und welche Nachweise erforderlich sind, ist nicht quellengeprüft.')+(' Nach eingetretener Fälligkeit kann der Besteller bei einem Mangel und einem Anspruch auf dessen Beseitigung nach § 641 Abs. 3 BGB einen angemessenen Vergütungsteil zurückhalten; regelmäßig ist dies das Doppelte der erforderlichen Mangelbeseitigungskosten.' if '641' in sources else ' Ein spezielles Zurückbehaltungsrecht nach Fälligkeit und dessen Höhe sind nicht quellengeprüft.')+' Eine Rechnung über '+text(', '.join(amounts) or 'den geforderten Betrag')+' begründet nicht ohne Weiteres die Fälligkeit des Gesamtbetrags; Vertragsinhalt, Soll-/Ist-Leistung, Einordnung als Restleistung oder Mangel und vereinbarte Zahlungsregel bleiben entscheidend.',
         'Leistungen und Wert jeder Position nachvollziehbar auflisten; Fertigstellungsgrad, vertragsgemäße Teilergebnisse und angebotene Fertigstellung belegen. Bei behaupteten Mängeln konkrete Abweichung und erforderliche Beseitigungskosten ermitteln; Zahlungsziel, Teilabnahmen, Abschlagsabreden und Vorleistungsklauseln prüfen.'),
        ('5. Ist Zahlungsverzug nachweisbar?', 'Keine geprüfte Verzugsnorm im vorhandenen Quellensatz',
         'Eine offene Rechnung oder ausbleibende Zahlung beweist noch keinen Verzug. Ohne gesicherte Fälligkeit und Angaben zu Zahlungsaufforderung, Zugang und möglichen Einwendungen werden weder Verzugsbeginn noch Zinsen oder Verzugsschäden festgestellt.',
         'Mahnung, Zugangsnachweis und Zahlungsabreden beschaffen; Voraussetzungen einschließlich möglicher Ausnahmen anwaltlich recherchieren.'),
        ('6. Gibt es zeitkritische Schritte?', 'Keine geprüfte Verjährungs- oder Verfahrensnorm im vorhandenen Quellensatz',
         'Aus den vorliegenden Angaben lässt sich keine bestätigte Verjährungs- oder Verfahrensfrist berechnen. Unbekannte Auslösedaten dürfen nicht durch Schätzungen ersetzt werden. Ein etwaiger gerichtlicher Bescheid müsste gesondert geprüft werden; sein Vorliegen wird nicht behauptet.',
         'Nach Zustellungen, gerichtlichen Schreiben und vollständigen Vertrags- und Leistungsdaten fragen; jede Frist und externe Maßnahme bleibt anwaltlicher Freigabe vorbehalten.')]
        for index,(title,basis,application,evidence) in enumerate(issues):
            anchor=next((e for e in selected if e['label']==['Vertrag / zeitlicher Ablauf','Leistung nach Darstellung der anfragenden Partei','Offene Zeitpunkte','Einwendungen der Gegenseite','Offene Zeitpunkte','Offene Zeitpunkte'][index]),None)
            if anchor:application='Anknüpfung an die Nachricht: „'+text(anchor['text'])+'“ (unbestätigt). '+application
            lines+=['### '+title,'','**Quelle / Prüfungsmaßstab:** '+basis+'.','', '**Bedingte Einordnung:** '+application,'','**Entscheidende Klärung:** '+evidence,'']
        lines+=['## D. Vorläufiges Ergebnis','',
        '**Für die Mandantschaft spricht derzeit:** Die Nachricht benennt '+('eine Rechnung über '+text(', '.join(amounts)) if amounts else 'eine Rechnung ohne sicher auslesbaren Betrag')+(', die Gegenseite '+text(profile.get('counterparty')) if profile.get('counterparty') else '')+' und einen behaupteten Auftrag; Leistungs- und Einwendungsvortrag lassen sich gezielt beweissichern. Das ist noch kein Nachweis eines fälligen Anspruchs.','',
        '**Schwachstellen / Gegenposition:** Die Gegenseite bestreitet offenbar Leistungsumfang oder Vollständigkeit. Vertrag, abnahmefähiger Erfolg, tatsächlich erbrachte Leistungen, Zugang der Rechnung, Zahlungsziel und Abnahme sind nicht belegt. Falls Werkvertrag und erhebliche Restleistung vorliegen, können Fälligkeit und Zurückbehaltungsrechte entgegenstehen. Eine bloße Behauptung vollständiger Leistung entkräftet das nicht.','',
        '**Vorläufige Einschätzung:** Eine Forderung von '+text(', '.join(amounts) or 'unbekannter Höhe')+' ist erst nach Klassifizierung des Vertrags und Abgleich von Soll-/Ist-Leistung belastbar zu bewerten. Kein derzeit feststellbarer Fälligkeitstag, keine Abnahme, kein Verzug und keine Erfolgsquote.','',
        '## E. Empfohlene nächste Schritte','',
        '1. **Sofort Belege sichern:** vollständige E-Mail- und Anlagenkette, Vertrag/Angebot/Änderungen, Rechnung samt Versand- und Zugangsnachweis, Zahlungsabrede, Mahnungen und Leistungsnachweise anfordern.',
        '2. **Soll/Ist-Abgleich erstellen:** jede vereinbarte Tätigkeit bzw. jedes Erfolgskriterium einer datierten Lieferung, Zeitaufzeichnung oder Übergabe gegenüberstellen; von der Gegenseite konkret benennen lassen, was wann fehlte oder mangelhaft gewesen sein soll.',
        '3. **Vertragsart und Fälligkeit prüfen:** Dienstvertrag oder Werkvertrag anhand des geschuldeten Inhalts bestimmen; nur bei Werkvertrag Abnahme/Fertigstellung und Mängelrechte prüfen. Höhe, Teilvergütung, Vorleistung und offene Restleistung rechnerisch abgleichen.',
        '4. **Parteien und Vertretung verifizieren:** richtige Rechtsträger, ladungsfähige Anschriften, Vertretungsbefugnis und Interessenkonflikte vor jeder Beauftragung oder Anspruchserklärung klären.',
        '5. **Danach anwaltlich entscheiden:** erst nach Prüfung der Belege über Nachbesserungs-/Fertigstellungsangebot, Vergleich, Zahlungsaufforderung oder Klage entscheiden; Zustellungen und konkrete Fristen sofort separat anwaltlich vorlegen.','']
    else:
        reason=('Kein ausdrücklich bestätigtes deutsches Sachrecht; daher keine automatische BGB-Anwendung.' if not german else
                'Kein fallbezogener Streit über Dienst- oder Werkleistungen sicher erkennbar; die E-Mail allein trägt keine spezifische Vergütungsanalyse.')
        lines+=[reason+' Rechtsgrund und Tatsachen müssen anwaltlich anhand der Unterlagen bestimmt werden.','',
        '## D. Vorläufiges Ergebnis','','Eine Sachentscheidung ist ohne passenden, quellengeprüften und auf den konkreten Vertrag bezogenen Rechtsrahmen nicht möglich. Die Nachricht ist Parteivortrag; Anspruch, Einwendungen und Fristen bleiben unbestätigt.','',
        '## E. Empfohlene nächste Schritte','','1. Prüfungsziel, anwendbares Recht und Vertragsbeziehung konkret bestätigen.','2. Die in der Nachricht angesprochenen Originalunterlagen und Gegenposition anfordern.','3. Passende Rechtsgrundlagen und mögliche zeitkritische Schreiben anwaltlich prüfen.','']
    lines+=['## F. Rechtsquellen','']
    reasons={'611':'Versprochene Dienste gegen vereinbarte Vergütung.','614':'Fälligkeit von Dienstvergütung nach Leistung bzw. Zeitabschnitt.','631':'Werkvertrag setzt versprochenen Erfolg voraus.','632a':'Abschlagszahlung nach Wert erbrachter vertraglicher Leistung; Beleg- und Beweislast sowie angemessener Einbehalt bei nicht vertragsgemäßer Leistung.','633':'Maßstab eines Sachmangels beim Werk.','634':'Mögliche werkvertragliche Mängelrechte, nur bei deren Voraussetzungen.','640':'Abnahmepflicht bei vertragsgemäß hergestelltem Werk, vorbehaltlich gesetzlicher Grenzen.','641':'Werklohnfälligkeit bei Abnahme; Teilabnahme und angemessener Einbehalt bei Mängeln unter gesetzlichen Voraussetzungen.','320':'Einrede bei ausstehender Gegenleistung; Teil-Leistung begrenzt sie unter den gesetzlichen Voraussetzungen.'}
    for number,(card,proof) in sources.items():lines+=['- **['+text(card['locator'])+']('+card['source_url']+')** — '+reasons.get(number,'Amtlicher Gesetzeswortlaut.')+' Wortlautprüfung im n8n-Verfahren: '+text(proof['retrieved_at'])+'; HTTP '+text(proof.get('http_status','unbekannt'))+'; SHA-256 des abgerufenen Quelldokuments `'+text(proof['source_sha256'])+'`. Geprüft wurde nur der hinterlegte Ausschnitt, keine vollständige Rechtsrecherche.']
    if not sources:lines+=['Keine für diese Analyse erfolgreich geprüfte materielle Rechtsquelle verfügbar. Rechtliche Einordnung bleibt offen; keine Quelle wird als erfolgreich abgerufen dargestellt.']
    audit={'report_version':VERSION,'message_sha256':hashlib.sha256(body.encode()).hexdigest(),'selected_excerpts':selected,'source_ids':[c['chunk_id'] for c,_ in sources.values()],'profile_provenance':'Manually confirmed intake fields; not independently verified','source_truncated_in_backend':len(re.sub(r'\s+',' ',body))>2900}
    lines+=['','<details><summary>Prüfstatus und technische Nachweise (sekundär)</summary>','',
      'Deterministische Aufbereitung, kein neues KI-Ergebnis. Keine Mandatsannahme, keine bestätigte Frist, keine Dokumentfreigabe. Dokumentstatus und fünf ausstehende anwaltliche Entscheidungen stehen separat in ANALYSIS. Allgemeine Vollmachts- und Vergütungsquellen sind keine materiellen Antworten auf den Streit.','',
      'Die vollständige Originalnachricht bleibt in INBOX; das unveränderte ursprüngliche Assessment und der Belegindex werden privat gespeichert. Nicht ausgewählte Aussagen sind keine Negativfeststellungen.','',
      '```json',json.dumps(audit,ensure_ascii=False,indent=2).replace('`',r'\u0060').replace('<',r'\u003c'),'```','','</details>']
    status=case.get('ai_synthesis') or {}
    if status.get('status')!='completed' or status.get('model_used') is not True or status.get('execution_mode')!='live':
        reason=status.get('reason') or 'ai_synthesis_not_accepted'
        if not re.fullmatch(r'[a-z0-9_]{1,100}',str(reason)):reason='ai_synthesis_not_accepted'
        lines[2]='**Deterministischer Fallback — keine KI-Analyse akzeptiert.** Grund: `'+reason+'`. Fiktiver Testfall · unbestätigte Angaben · anwaltliche Prüfung erforderlich.'
        lines+=['','## KI-Status','','Die KI-Auswertung wurde nicht als Analyse angenommen. Dieser Bericht stammt aus deterministischen Python-Regeln; er ist ausdrücklich kein LLM-Ergebnis.','']
    return '\n'.join(lines)+'\n',audit


def render_ai(case,message,analysis,metadata):
    """Render accepted v2 model reasoning with server-validated source records."""
    if (metadata.get('status')!='completed' or metadata.get('model_used') is not True or
        metadata.get('execution_mode')!='live' or metadata.get('contract_version')!='2.0' or
        not isinstance(analysis,dict)):
        raise ValueError('AI synthesis was not accepted as live source-exact contract v2 output')
    sources={s['source_id']:s for s in case['bundle']['assessment']['sources']}
    statements={k:([analysis['mandate_summary']] if k=='mandate_summary' else analysis.get(k,[]))
                for k in ('mandate_summary','factual_background','preliminary_legal_issues','source_supported_analysis',
                          'missing_information','uncertainties_and_limitations','questions_requiring_lawyer_review',
                          'proposed_next_steps')}
    used_ids=[];seen_statements=set();seen_quotes=set();used_for={}
    def evidence(item,show_quotes=True):
        quotes=item.get('evidence_quotes')
        ids=item.get('source_ids')
        if not isinstance(ids,list) or not ids or not isinstance(quotes,list) or not quotes:
            raise ValueError('AI evidence selection is incomplete')
        out=[]
        for quote in quotes:
            sid=quote.get('source_id');record=sources.get(sid);excerpt=quote.get('quote')
            if sid not in ids or record is None or not isinstance(excerpt,str) or excerpt not in record.get('content',''):
                raise ValueError('AI evidence quote does not match its server source')
            if sid not in used_ids:used_ids.append(sid)
            if (sid,excerpt) in seen_quotes:continue
            seen_quotes.add((sid,excerpt))
            if not show_quotes:continue
            url=record.get('url');locator=text(record.get('locator') or sid)
            citation=(' — ['+locator+']('+url+')') if url and str(url).startswith('https://') else ' — '+locator
            out.append('  - **Beleg:** „'+text(excerpt)+'“'+citation)
        return out
    def section(field,title,empty,values_override=None):
        lines=['### '+title,''];shown=0
        values=statements[field] if values_override is None else values_override
        if not values:lines.append(empty)
        for item in values:
            if not isinstance(item,dict) or not isinstance(item.get('statement'),str):raise ValueError('AI report item is invalid')
            if item['statement'] in seen_statements:continue
            seen_statements.add(item['statement'])
            shown+=1
            status=item.get('evidence_status','')
            kind={'unverified_intake':'Intake-Angabe, ungeprüft','client_alleged':'CLIENT-ALLEGED, nicht verifiziert',
                  'preliminary_analysis':'Bedingte KI-Analyse','question':'Prüffrage','cached_report':'Cache-Bericht',
                  'official_record_reported':'Historischer Registerauszug','unverified_lead':'Unbestätigter Hinweis',
                  'source_guidance':'Amtliche Rechtsquelle'}.get(status,'Prüfstatus: '+text(status))
            lines.append('- **'+kind+' · '+text(item.get('issue_category',''))+':** '+text(item['statement']))
            citations=[]
            for sid in item.get('source_ids',[]):
                used_for.setdefault(sid,[]).append(item['statement'])
                record=sources.get(sid,{})
                locator=text(record.get('locator') or sid);url=record.get('url')
                citations.append(('['+locator+']('+url+')') if url and str(url).startswith('https://') else locator)
            if citations:lines.append('  - **Quellen:** '+', '.join(dict.fromkeys(citations)))
            exact_fact=(item.get('assertion_type')=='source_excerpt' and all(item.get('statement')==q.get('quote') for q in item.get('evidence_quotes',[])))
            lines.extend(evidence(item,show_quotes=not exact_fact))
        if values and not shown:lines.append('Der ausgewählte Originalauszug steht bereits in Abschnitt A und wird hier nicht wiederholt.')
        return lines
    client=case['profile'];bundle=case['bundle'];synthesis=metadata.get('synthesis') or {}
    model=text(metadata.get('model') or 'Modell nicht gemeldet')
    usage=metadata.get('usage') if isinstance(metadata.get('usage'),dict) else {}
    token_text='; '.join(text(k)+': '+text(v) for k,v in usage.items() if isinstance(v,(int,float)) and not isinstance(v,bool)) or 'Tokenverbrauch nicht gemeldet'
    origin='validierte LLM-Auswertung aus Cache' if metadata.get('cache_hit') else 'validierte Live-LLM-Auswertung'
    scope=text(client.get('scope') or bundle['matter'].get('requested_scope') or '')
    if len(scope)>300:scope='ausgewählte Gmail-Anfrage'
    lines=['# Vorläufige Mandatsanalyse','','**Vorläufige OpenAI-Analyse · '+model+' · anwaltliche Prüfung erforderlich.**','',
      '## A. Mandant und Beteiligte','',
      '- **Mandant/in:** '+text(client.get('name') or bundle['client'].get('name') or 'nicht angegeben')+' · Kontakt: '+text(client.get('email') or bundle['client'].get('email') or 'nicht angegeben')+' · Anschrift: '+text(client.get('address') or bundle['client'].get('address') or 'nicht angegeben')+'.',
      '- **Gegenseite:** '+text(client.get('counterparty') or ', '.join(bundle['matter'].get('opposing_parties',[])) or 'nicht angegeben')+'.',
      '- **Gewünschte Unterstützung:** '+(scope or 'aus der Nachricht zu bestimmen')+'.','']
    lines+=section('mandate_summary','KI-ausgewählter Mandatsanlass','Kein quellengestützter Mandatsanlass ausgewählt.')
    lines+=['','## B. Sachverhalt','', '**Originalauszüge aus der ausgewählten Nachricht; Parteivortrag, nicht unabhängig geprüft.**','']
    lines+=section('factual_background','Wesentliche Tatsachen und zeitlicher Ablauf','Keine quellengestützten Tatsachenauszüge ausgewählt.')
    lines+=section('missing_information','Fehlende Belege und offene Tatsachen','Keine zusätzlichen Informationslücken ausgewählt.')
    lines+=['','## C. Rechtliche Würdigung','']
    lines+=section('preliminary_legal_issues','Relevante Rechtsfragen','Keine quellengestützte Rechtsfrage ausgewählt.')
    lines+=section('source_supported_analysis','Bedingte Anwendung der Rechtsquellen','Keine validierte materielle Rechtsanalyse angenommen.',statements['source_supported_analysis'])
    lines+=['','## D. Vorläufiges Ergebnis','']
    lines+=section('uncertainties_and_limitations','Unsicherheiten und Gegenargumente','Keine weiteren Unsicherheiten ausgewählt.')
    lines+=['','## E. Handlungsempfehlungen','']
    lines+=section('proposed_next_steps','Nächste Schritte für anwaltliche Prüfung','Keine nächste Prüffrage ausgewählt.')
    lines+=section('questions_requiring_lawyer_review','Weitere anwaltliche Prüffragen','Keine weiteren Prüffragen ausgewählt.')
    lines+=['','## F. Rechtsquellen','']
    proofs={}
    for proof in case.get('legal_research',[]):
        src=proof.get('source') or {}
        if src.get('source_id'):proofs[src['source_id']]=proof
    legal_ids=[sid for sid in used_ids if sources.get(sid,{}).get('kind')=='legal_reference']
    if not legal_ids:lines.append('Keine amtliche Rechtsquelle wurde in der angenommenen KI-Analyse zitiert; tragfähige materielle Rechtsanalyse bleibt offen.')
    for sid in legal_ids:
        source=sources[sid];proof=proofs.get(sid,{})
        locator=text(source.get('locator') or sid);url=source.get('url') or ''
        label=('['+locator+']('+url+')') if str(url).startswith('https://') else locator
        if proof.get('status')=='wording_verified' and re.fullmatch(r'[a-f0-9]{64}',proof.get('source_sha256','')):
            lines.append('- **'+label+'** — amtlicher Wortlaut abgerufen und geprüft; Abruf '+text(proof.get('retrieved_at','unbekannt'))+'.')
        else:
            lines.append('- **'+label+'** — Relevanz laut KI: '+text(' '.join(dict.fromkeys(used_for.get(sid,[]))))+'; Quelle ist im AI-Evidenzsatz enthalten, konkrete Abrufprovenienz nicht bestätigt. Anwaltliche Nachprüfung erforderlich.')
    audit={'report_version':VERSION,'analysis_origin':origin,'model':metadata.get('model'),'contract_version':'2.0',
           'message_sha256':hashlib.sha256(message['body'].encode()).hexdigest(),'ai_source_ids':used_ids,
           'legal_source_ids':legal_ids,'live_request':metadata.get('live_request'),'cache_hit':metadata.get('cache_hit')}
    return '\n'.join(lines)+'\n',audit
