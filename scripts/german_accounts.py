"""Local German account ingestion with reviewed mappings; never performs network I/O."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from decimal import Decimal
from datetime import date
from urllib.parse import urlsplit, urlunsplit

from scripts.financial_analysis import analyze_financials, METRICS
from scripts.report_renderer import financial_section, text


def german_number(value):
    if not isinstance(value,str):raise ValueError('Amounts must be explicit German-formatted strings.')
    value=value.strip().replace('\u00a0','').replace('−','-')
    if value.startswith('(') and value.endswith(')'):value='-'+value[1:-1]
    if not re.fullmatch(r'[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?',value):
        raise ValueError('Missing or ambiguous amount; no conversion to zero is permitted.')
    return str(Decimal(value.replace('.','').replace(',','.')))


def pdf_pages(path):
    path=Path(path)
    if path.stat().st_size>20_000_000 or not path.read_bytes().startswith(b'%PDF-'):
        raise ValueError('PDF missing or larger than the local 20 MB limit.')
    from pypdf import PdfReader
    from pypdf.constants import UserAccessPermissions
    reader=PdfReader(path)
    if reader.is_encrypted and not reader.user_access_permissions & UserAccessPermissions.EXTRACT:
        raise ValueError('PDF permissions disallow automated extraction; use authorized visual transcription, not a bypass.')
    if len(reader.pages)>100:raise ValueError('Oversized PDF requires manual review.')
    pages=[p.extract_text(extraction_mode='layout') or '' for p in reader.pages]
    if not any(p.strip() for p in pages):raise ValueError('No text layer: scanned PDF requires human transcription; no OCR guessed.')
    return pages,hashlib.sha256(path.read_bytes()).hexdigest()


def safe_source(url):
    parts=urlsplit(url)
    if parts.scheme not in ('http','https') or parts.username or parts.password:raise ValueError('A public source URL is required.')
    # Session/signature parameters remain only in the supplied private manifest.
    return urlunsplit((parts.scheme,parts.netloc,parts.path,'',''))


def ingest(statement, *, pdf=None):
    """PDF mode uses explicit page/regex rules; structured mode uses checked transcriptions.

    A mapping is supplied/reviewed by a human. It is never inferred by an LLM.
    Ambiguous text matches, unit headers, periods and source hashes fail closed.
    """
    if statement.get('schema_version')!=1 or statement.get('reviewed') is not True:
        raise ValueError('A reviewed version-1 mapping/transcription is required.')
    company=statement['company'];source=statement['source'];source_url=safe_source(source['url'])
    private_reference=bool(urlsplit(source['url']).query or urlsplit(source['url']).fragment)
    if private_reference:source_url='Local document ID: '+source['document_id']
    if not isinstance(company,str) or not company.strip():raise ValueError('Company label is required.')
    pages=None
    digest=source.get('sha256')
    if pdf:
        pages,actual=pdf_pages(pdf)
        if actual!=digest:raise ValueError('Source PDF hash does not match the reviewed mapping.')
    if not isinstance(digest,str) or not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('Source SHA256 is required.')
    def page_text(page):
        if type(page) is not int or page<1 or pages is not None and page>len(pages):raise ValueError('Invalid source page.')
        return pages[page-1] if pages is not None else None
    # Context evidence prevents silently assigning periods/scope to a bare balance sheet.
    context=statement['context']
    if not context.get('quote'):raise ValueError('Period/scope context evidence is required.')
    context_text=page_text(context['page'])
    if context_text is not None and context['quote'] not in context_text:raise ValueError('Context evidence is absent from PDF.')
    periods=[]
    seen=set()
    for row in statement['periods']:
        start,end=date.fromisoformat(row['period_start']),date.fromisoformat(row['period_end'])
        scope=row['scope']
        if scope not in ('standalone','consolidated') or start>end:raise ValueError('Invalid period/scope.')
        if (str(end),scope) in seen:raise ValueError('Duplicate period/scope; resolve restatements.')
        seen.add((str(end),scope));facts={}
        for metric,rule in row['facts'].items():
            if metric not in METRICS:raise ValueError('Unsupported financial metric.')
            unit=rule['unit'];unit_page=page_text(unit['page'])
            currency=unit.get('currency');scale=unit.get('scale')
            # Missing units are retained, never inferred. Known units must be explicit.
            if currency is not None and currency not in ('EUR','GBP','USD','CHF'):raise ValueError('Unsupported explicit currency.')
            if scale is not None and (not isinstance(scale,(str,int)) or isinstance(scale,bool) or not Decimal(str(scale)).is_finite() or Decimal(str(scale))<=0):raise ValueError('Invalid scale.')
            header=unit.get('quote')
            if not header:raise ValueError('Unit/column evidence is required, including for unavailable units.')
            if unit_page is not None and not re.search(unit['pattern'],unit_page):raise ValueError('Unit/date header does not match PDF.')
            page=rule['page'];content=page_text(page)
            if content is None:
                raw_value=rule.get('raw_value');quote=rule.get('quote')
                if not quote:raise ValueError('Structured amount needs a source excerpt.')
                if raw_value is not None and raw_value not in quote:raise ValueError('Amount is absent from transcription excerpt.')
            else:
                matches=list(re.finditer(rule['pattern'],content,re.MULTILINE))
                if not matches:raise ValueError('Financial row absent; extraction withheld: '+metric)
                if len(matches)>1 and 'occurrence' not in rule:raise ValueError('Ambiguous financial row; explicit reviewed occurrence required.')
                index=rule.get('occurrence',0)
                match=matches[index];raw_value=match.group(rule['column']);quote=match.group(0).strip()
            if raw_value is None:continue
            facts[metric]={'value':german_number(raw_value),'currency':currency,'scale':scale,
                           'source_field':metric,'page':page,'source_quote':quote,'raw_value':raw_value,
                           'source_sha256':digest,'unit_evidence':header,'unit_page':unit['page'],
                           'precision':rule.get('precision','as_reported'),'reviewed_mapping':True}
        periods.append({'period_start':str(start),'period_end':str(end),'scope':scope,'facts':facts,
                        'short_year':row.get('short_year',False),'source':source_url,'report_id':source['document_id']})
    return {'provider':'Locally supplied German accounts','status':'available','company':company,
            'source':source_url,'source_sha256':digest,'document_id':source['document_id'],
            'retrieved_at':source.get('retrieved_at'),'context':context,'periods':periods,
            'limitations':statement.get('limitations',[]),'demo_label':statement.get('demo_label'),
            'private_source_reference':private_reference}


def report(data):
    analysis=analyze_financials(data)
    lines=['# M&A financial due diligence — '+text(data['company']),'',text(data.get('demo_label') or 'Local company accounts; no provider calls.'),
           '', '## Executive summary','',
           'Overall risk: **Undetermined**. Source-backed statement figures and calculations below are distinct from independent audit verification or legal findings.',
           '',('Source document ID: '+text(data['document_id'])+'; original URL retained in private manifest.' if data.get('private_source_reference') else f"Source: [{text(data['document_id'])}]({safe_source(data['source'])})"),
           'Source SHA256: '+data['source_sha256'],'Retrieved: '+text(data.get('retrieved_at')),
           '', '## Confirmed statement evidence','',
           'Confirmation means the reviewed mapping matches source text, not an assurance opinion. Comparative TEUR amounts are rounded; movements and ratios using them are approximate.']
    lines+=financial_section(analysis)
    lines+=['','## Page-level evidence','']
    for period in data['periods']:
        for metric,fact in period['facts'].items():
            lines+=['- '+text(period['period_end'])+' / '+text(metric)+' — PDF page '+str(fact['page'])+'; '+text(fact['source_quote'])+'; units: '+text(fact['unit_evidence'])+'; precision: '+text(fact['precision'])]
    lines+=['','## Potential buyer risks and follow-up','']
    for item in analysis['indicators']:
        lines+=['- '+text(item['description'])+' ('+text(item['period_end'])+'). Underlying evidence: '+text(json.dumps(item['evidence']))+'. Review trigger, not proof of distress.']
    valid=sorted((p for p in analysis['periods'] if p['valid_period']),key=lambda p:p['period_end'])
    for before,after in zip(valid,valid[1:]):
        a,b=before['ratios']['equity_ratio']['value'],after['ratios']['equity_ratio']['value']
        if a is not None and b is not None and before['scope']==after['scope'] and Decimal(b)<Decimal(a):
            lines+=['- Equity ratio decreased from '+format(Decimal(a)*100,'.2f')+'% to '+format(Decimal(b)*100,'.2f')+'% ('+text(before['period_end'])+' to '+text(after['period_end'])+'). Assets grew faster than equity; assess financing, provisions and grant balances. Comparative rounding applies.']
    for period in analysis['periods']:
        margin=period['ratios']['net_margin']['value']
        if margin is not None and Decimal(margin)<Decimal('0.05'):
            lines+=['- Thin net margin at '+text(period['period_end'])+': '+format(Decimal(margin)*100,'.2f')+'%; net income '+text(period['normalized_values']['net_income']['value'])+' / revenue '+text(period['normalized_values']['revenue']['value'])+' '+text(period['normalized_values']['revenue']['currency'])+'. The 5% screen is a review heuristic, not a distress threshold. Sensitivity to costs, grants and non-recurring income requires a bridge.']
    lines+=['', 'Specific buyer questions:',
            '- What explains cash movements despite accounting profits? Supply bank statements and an operating cash-flow / working-capital bridge.',
            '- Which receivables are overdue, disputed or owed by related parties? Obtain ageing, subsequent receipts and related-party settlement terms.',
            '- Reconcile adjusted EBITDA and sustainable earnings to the statutory P&L. Identify grants, one-off income and owner allocations.',
            '- Provide debt, provisions and maturity schedules before agreeing net debt, cash-free/debt-free and working-capital adjustments.',
            '- Are grants, charitable restrictions or intra-group arrangements affected by a change of control? Obtain legal review and consents.',
            '- Provide latest management accounts, forecasts, capex and subsequent events; historical accounts alone cannot establish current liquidity.',
            '', '## Unavailable information and limitations','',
            'Missing fields are unavailable, never zero. No inference from provider silence. No documents or records were fetched by this ingestion.',
            'No current ratio without explicit current liabilities; no EBITDA, free cash flow or debt-service coverage inferred from net income.',
            'A locally supplied source and human-reviewed mapping do not independently authenticate the company or accounts. Scans, ambiguous rows and unsupported layouts require manual transcription/review.']
    lines+=data.get('limitations',[])
    return '\n'.join(lines)+'\n',analysis


def main():
    parser=argparse.ArgumentParser(description='Offline German accounts ingestion/reporting; no network or paid tools')
    parser.add_argument('statement',type=Path);parser.add_argument('--pdf',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    data=ingest(json.loads(args.statement.read_text()),pdf=args.pdf)
    markdown,analysis=report(data);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(markdown);args.output.with_suffix('.json').write_text(json.dumps({'ingested':data,'analysis':analysis},indent=2))
    print('Saved local report:',args.output)


if __name__=='__main__':main()
