"""Reproducible synthetic document bundles; no network, provider or persistence calls."""
import copy,json,socket
from pathlib import Path
from unittest.mock import patch
from scripts.onboarding_schemas import OnboardingRequest,ClientRecord,MatterRecord
from scripts.onboarding import advance
from scripts.legal_documents import generate_documents,DocumentContext,cross_validate,DocumentRules
ROOT=Path(__file__).resolve().parents[1]


def scenarios():
    base=json.loads((ROOT/'examples/onboarding_preview.json').read_text());base['draft_date']='2026-11-11'
    base['fees']['vat_basis']='Ausdrücklich bestätigte synthetische Rechenkonfiguration: inländische steuerpflichtige anwaltliche Leistung, 19 Prozent; keine Feststellung für ein reales Mandat.'
    base['firm'].update(name='DEMO Kanzlei Lindenbogen (vollständig fiktiv)',address='Erfundener Kanzleiplatz 20, 00000 Musterort',lawyer_name='DEMO Rechtsanwältin Nora Linden (fiktiv)',email='kanzlei@lindenbogen.invalid')
    base['matter'].update(governing_law='Germany',claimed_deadline=None,deadline_source=None,opposing_parties=['DEMO Handelspartner Morgenfeld GmbH (fiktiv)'],requested_scope='Außergerichtliche Prüfung der Vertragsunterlagen und Korrespondenz sowie rechtliche Stellungnahme zur behaupteten Lieferforderung. Keine Prozessführung oder Vergleichsvollmacht.')
    base['document_options']={'place':'Musterort (Demo)','representation_scope':'out_of_court','requested_ancillary_powers':[],'engagement_law':'Germany','recipient_business_status':'consumer','supplier_domestic':True,'recipient_domestic':True,'firm_policy':{'policy_id':'SYNTHETIC-LINDENBOGEN-2026-v1','net_hourly_rate':'250.00','billing_method':'actual_minutes','time_recording':'Tätigkeitsnachweis mit Datum, bearbeitender Person, Tätigkeitsbeschreibung und tatsächlicher Dauer in Minuten; keine pauschale Aufrundung.','expenses_terms':'Auslagen werden nur nach vorheriger gesonderter Vereinbarung angesetzt; in diesem Entwurf ist keine Auslagenpauschale vereinbart.','payment_terms':'Synthetische Kanzleiregel zur Prüfung: Zahlung binnen 14 Kalendertagen nach Zugang einer ordnungsgemäßen, gesondert freigegebenen Abrechnung. Dieser Entwurf löst keine Zahlungsfrist aus.','other_professionals_terms':'Für andere Berufsträger sind keine Stundensätze vereinbart. Ein Einsatz mit zusätzlichen Kosten bedarf einer gesonderten Vereinbarung.','vat_configuration_confirmed_for_demo':True}}
    individual=copy.deepcopy(base);individual['idempotency_key']='document-quality-individual-v2';individual['client'].update(client_type='individual',name='DEMO Lena Wolkenfeld (vollständig fiktiv)',address='Erfundene Gartenzeile 7, 00000 Musterort',email='lena@wolkenfeld.invalid');individual['matter'].update(title='DEMO Zivilrecht — behauptete Lieferforderung',summary='Vollständig fiktives Privatmandat: Eine Zahlung aus einem behaupteten Liefervertrag soll außergerichtlich geprüft werden. Die Berechtigung der Forderung ist nicht festgestellt.')
    corporate=copy.deepcopy(base);corporate['idempotency_key']='document-quality-company-v2';corporate['client'].update(client_type='company',name='DEMO Nordfalter Projekt GmbH (vollständig fiktiv)',address='Erfundener Gewerbehof 8, 00000 Musterort',email='mandat@nordfalter.invalid');corporate['matter'].update(title='DEMO Gesellschaftsmandat — Liefervertragsprüfung',summary='Vollständig fiktive Gesellschaft beauftragt eine außergerichtliche Prüfung einer behaupteten Lieferforderung; Geschäftsführung und Mandatsfreigabe beruhen ausschließlich auf synthetischem Demonstrationsnachweis.');corporate['document_options'].update(recipient_business_status='business',representative={'name':'DEMO Jonas Nebel (fiktiv)','role':'Geschäftsführer (synthetisch)','authority_status':'synthetic_evidence_checked','evidence_reference':'DEMO-GESCHAEFTSFUEHRUNGSBESCHLUSS-2026-11-11: ausdrücklich synthetische Einzelvertretungs- und Mandatsfreigabe; keine echte Register- oder Urkundenprüfung.'})
    return {'individual':individual,'corporate':corporate}


def generate(output=None):
    out=Path(output) if output else ROOT/'examples/documents';out.mkdir(parents=True,exist_ok=True);summary={}
    with patch.object(socket.socket,'connect',side_effect=AssertionError('Offline documents only')):
        rules=DocumentRules()
        for name,body in scenarios().items():
            req=OnboardingRequest.model_validate(body);client=ClientRecord(**req.client.model_dump(),client_id='demo-document-client-'+name);matter=MatterRecord(**req.matter.model_dump(),client_id=client.client_id,matter_id='DEMO-AKTE-'+name.upper()+'-2026');fee=advance(req.fees);ctx=DocumentContext(req,client,matter,fee);docs=generate_documents(req,client,matter,fee)
            issues=cross_validate(docs,ctx);assert not issues
            folder=out/name;folder.mkdir(exist_ok=True);(folder/'input.json').write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
            validation={'scenario':'SYNTHETIC '+name,'template_version':rules.manifest['version'],'source_version':rules.version,'legally_approved':False,'ready_for_issuance':False,'external_actions':0,'advance':fee.model_dump(),'documents':[{k:v for k,v in d.model_dump().items() if k!='content_markdown'} for d in docs],'cross_document_errors':[i.model_dump() for i in issues]}
            (folder/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
            lines=['# Anwaltliche Prüf- und Freigabeliste','', 'DEMO — ausschließlich synthetischer Fall. Keine rechtliche Freigabe.','']
            for doc in docs:
                (folder/(doc.kind+'.md')).write_text(doc.content_markdown)
                lines+=['## '+doc.kind+' — '+doc.completeness_status,'']+['- '+i.field+': '+i.description for i in doc.validation_issues]+['- '+q for q in doc.lawyer_review_questions]+['']
            lines+=['## Rechtsquellen','']
            for kind in ('vollmacht','fee_agreement','advance_invoice'):
                for ref in rules.select(kind):lines+=['- '+ref['id']+': '+ref['source_url']+'; abgerufen '+ref['retrieved_at']+'; Anwendbarkeit anwaltlich prüfen.']
            (folder/'review_checklist.md').write_text('\n'.join(lines)+'\n');summary[name]={d.kind:d.completeness_status for d in docs}
    return summary

if __name__=='__main__':print(json.dumps(generate(),indent=2,ensure_ascii=False))
