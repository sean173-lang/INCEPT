"""Isolated, explicitly approved one-request financial test. No import-time I/O."""
import argparse
import copy
from contextlib import closing, contextmanager
from datetime import datetime, timezone, date
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sqlite3
import time

import requests
from scripts.volkswagen_profile import ROOT, STATE_DIR, ProfileError, RegisterTransport, matches_target, timestamp
from scripts.volkswagen_continuation import DIRECT_ID
from scripts.financial_analysis import analyze_financials, METRICS, OPENREGISTER_FIELDS, number
from scripts.german_register import _validate_financial_payload, _financial_http_failure
from scripts.api_usage import JsonCache, UsageTracker
from scripts.report_renderer import text, financial_section, document_reference

SOURCE='https://api.openregister.de/v1/company/'+DIRECT_ID+'/financials'
DIRECTORY=ROOT/'data/volkswagen_financial_test'
ACK=f'{DIRECT_ID} | financials only | one request | separate 10-credit budget'
POLICY={'company_id':DIRECT_ID,'endpoint':SOURCE,'max_credits':10,'max_requests':1,
        'verified_on':'2026-11-10','valid_until':'2026-11-17',
        'pricing_source':'https://docs.openregister.de/pricing'}


def validate_raw(raw):
    raw=_validate_financial_payload(raw)
    if raw.get('error') or raw.get('company_id',DIRECT_ID)!=DIRECT_ID or raw.get('id',DIRECT_ID)!=DIRECT_ID:
        raise ValueError('Conflicting financial identity or error envelope')
    reports=raw['reports'];ids=[r['report_id'] for r in reports if r.get('report_id')]
    if len(ids)!=len(set(ids)):raise ValueError('Duplicate report identifiers')
    for report in reports:
        if report.get('consolidated') is not None and type(report['consolidated']) is not bool:
            raise ValueError('Unsupported reporting scope')
        sources=report.get('sources',[])
        if not isinstance(sources,list) or any(not isinstance(s,dict) or not isinstance(s.get('html_url'),str) for s in sources):
            raise ValueError('Unsupported document references')
    for row in raw['indicators']:
        for key in OPENREGISTER_FIELDS.values():
            if row.get(key) is not None and number(row[key]) is None:raise ValueError('Invalid reported number')
    # Retain only financial fields used by the existing analyzer; omit personal auditor data.
    reduced={k:raw[k] for k in ('currency','scale') if k in raw}
    reduced['reports']=[{k:r[k] for k in ('report_id','consolidated','report_start_date','report_end_date','published_at','sources','currency','scale') if k in r} for r in reports]
    for report in reduced['reports']:
        if 'sources' in report:report['sources']=[{'html_url':s['html_url']} for s in report['sources']]
    reduced['indicators']=[{k:r[k] for k in ('report_id','date','short_year','currency','scale',*OPENREGISTER_FIELDS.values()) if k in r} for r in raw['indicators']]
    json.dumps(reduced,allow_nan=False)
    return reduced


class FinancialTransport(RegisterTransport):
    def request(self):
        key=self.preflight()
        try:
            with requests.Session() as session:
                session.trust_env=False
                session.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
                response=session.get(SOURCE,headers={'Authorization':'Bearer '+key,'Accept':'application/json'},timeout=30,allow_redirects=False)
                if response.status_code!=200:
                    body=None
                    if response.status_code==404:
                        try:body=response.json()
                        except ValueError:pass
                    failure=_financial_http_failure({},response.status_code,body=body)
                    raise ProfileError(failure['error_code'],failure['reason'],502)
                return response.json()
        except requests.RequestException:
            raise ProfileError('network_failure','Financial transport failed; processing/billing is uncertain. No retry permitted.',502) from None


class FinancialTest:
    def __init__(self, *, directory=DIRECTORY, identity_db=STATE_DIR/'state.sqlite3', cache_dir=ROOT/'data/financials',
                 usage_cache_dir=ROOT/'data/api_cache', transport=None, clock=time.time):
        self.directory=Path(directory);self.identity_db=Path(identity_db);self.cache_dir=Path(cache_dir)
        self.usage_cache_dir=Path(usage_cache_dir);self.clock=clock;self.transport=transport or FinancialTransport()
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700);os.chmod(self.directory,0o700)
        self.db=self.directory/'state.sqlite3';self.grant=self.directory/'approval.local'
        if self.db.resolve()==self.identity_db.resolve():raise ProfileError('ledger_isolation_required','Financial and identity ledgers must differ.')
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS approval(id INTEGER PRIMARY KEY CHECK(id=1),digest TEXT,expires REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS attempt(id INTEGER PRIMARY KEY CHECK(id=1),state TEXT,credits INTEGER,started_at TEXT,completed_at TEXT,result TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS policy(value TEXT)')
            fingerprint=json.dumps(POLICY,sort_keys=True)
            row=db.execute('SELECT value FROM policy').fetchone()
            if row and row[0]!=fingerprint:raise ProfileError('policy_changed','Financial policy changed; manual review required.')
            if not row:db.execute('INSERT INTO policy VALUES(?)',(fingerprint,))
        os.chmod(self.db,0o600)

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.db,timeout=5)) as db:
            db.execute('BEGIN IMMEDIATE')
            try:yield db;db.commit()
            except BaseException:db.rollback();raise

    def check_policy(self):
        today=datetime.fromtimestamp(self.clock(),timezone.utc).date()
        if not date.fromisoformat(POLICY['verified_on'])<=today<=date.fromisoformat(POLICY['valid_until']):
            raise ProfileError('pricing_expired','Financial credit documentation requires renewed review; execution blocked.',503)

    def identity(self):
        try:
            with closing(sqlite3.connect(self.identity_db.resolve().as_uri()+'?mode=ro',uri=True)) as db:
                row=db.execute('SELECT result FROM continuation WHERE id=1').fetchone()
            result=json.loads(row[0]);company=result['company']
            target={'company':{'allowed_legal_names':['Volkswagen AG','Volkswagen Aktiengesellschaft'],'register_court':'Amtsgericht Braunschweig'}}
            if (result['status']!='verified' or result.get('synthetic') is not False or result.get('development') is not False
                    or company.get('provider_company_id')!=DIRECT_ID or not company.get('country') or not matches_target(company,target)
                    or not any(e.get('provider')=='OpenRegister' and e.get('origin')=='live_provider_response' and e.get('retrieved_at') for e in result.get('evidence',[]))):raise ValueError()
            return {'company':company,'identity_evidence':result['evidence']}
        except (sqlite3.Error,OSError,ValueError,TypeError,KeyError):
            raise ProfileError('identity_unverified','Verified live Volkswagen detail evidence is required; no identity calls will be made.',403) from None

    def cache(self):
        values=[]
        try:values.append(json.loads((self.cache_dir/(DIRECT_ID+'.json')).read_text())['result'])
        except (OSError,ValueError,KeyError,TypeError):pass
        value=JsonCache(self.usage_cache_dir,self.clock).get(UsageTracker.key('OpenRegister','financials',DIRECT_ID),86400)
        if value:values.append(value)
        for value in values:
            try:
                provenance=value.get('provenance',{})
                when=datetime.fromisoformat(value['retrieved_at'])
                if (value.get('company_id')!=DIRECT_ID or value.get('source')!=SOURCE or value.get('provider')!='OpenRegister'
                    or value.get('request_status')!='succeeded' or value.get('http_status')!=200
                    or value.get('synthetic') is True or value.get('development') is True
                    or provenance.get('origin')!='live_provider_response' or provenance.get('provider')!='OpenRegister'
                    or when.tzinfo is None or not 0<=self.clock()-when.timestamp()<86400):continue
                return {**value,'raw':validate_raw(value['raw']),'cache_hit':True}
            except (ValueError,TypeError,KeyError,AttributeError):continue
        return None

    def status(self):
        with self.transaction() as db:row=db.execute('SELECT state,credits,started_at,completed_at,result FROM attempt WHERE id=1').fetchone()
        return {'company_id':DIRECT_ID,'state':row[0] if row else 'not_started','estimated_credits_reserved':row[1] if row else 0,
                'max_credits':10,'max_requests':1,'cost':'Cost unknown','billing_confirmed':False,
                'started_at':row[2] if row else None,'completed_at':row[3] if row else None}

    def preview(self):
        identity=self.identity();cached=self.cache()
        return {**self.status(),'verified_company':identity['company'],'cache_reusable':bool(cached),
                'estimated_new_credits':0 if cached else 10,'provider_requests_made':0,
                'pricing_valid_until':POLICY['valid_until']}

    def approve(self, acknowledgement):
        self.check_policy();self.identity()
        if acknowledgement!=ACK:raise ProfileError('approval_required','The exact financial-test acknowledgement is required.',403)
        nonce=secrets.token_urlsafe(32)
        with self.transaction() as db:
            if db.execute('SELECT 1 FROM attempt').fetchone():raise ProfileError('duplicate_request_blocked','Financial test already started; no reset or reapproval.')
            db.execute('INSERT OR REPLACE INTO approval VALUES(1,?,?)',(hashlib.sha256(nonce.encode()).hexdigest(),self.clock()+3600))
            fd=os.open(self.grant,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as stream:stream.write(nonce)
            os.chmod(self.grant,0o600)
        return {'approved':True,'expires_in_seconds':3600,'max_credits':10,'provider_requests_made':0}

    def run(self, nonce):
        self.check_policy();identity=self.identity()
        with self.transaction() as db:
            approval=db.execute('SELECT digest,expires FROM approval WHERE id=1').fetchone()
            if not approval or not isinstance(nonce,str) or not hmac.compare_digest(approval[0],hashlib.sha256(nonce.encode()).hexdigest()):
                raise ProfileError('approval_required','Separate explicit financial approval is required.',403)
            if self.clock()>approval[1]:raise ProfileError('approval_expired','Financial approval expired.',403)
            old=db.execute('SELECT result FROM attempt WHERE id=1').fetchone()
            if old:
                if old[0]:return json.loads(old[0])
                raise ProfileError('duplicate_request_blocked','Financial test pending or uncertain; manual review required.')
            cached=self.cache()
            if not cached:self.transport.preflight()
            # Single persistent row is both the request limit and full reservation.
            db.execute('INSERT INTO attempt VALUES(1,?,?,?,NULL,NULL)',('pending',0 if cached else 10,timestamp(self.clock())))
        try:
            if cached:data=cached
            else:
                raw=validate_raw(self.transport.request())
                data={'provider':'OpenRegister','company_id':DIRECT_ID,'source':SOURCE,'http_status':200,'request_status':'succeeded',
                      'status':'available' if raw['indicators'] else 'unavailable','raw':raw,'publication_status':'unknown',
                      'financial_data_status':'figures_returned' if raw['indicators'] else 'no_figures_returned',
                      'retrieved_at':timestamp(self.clock()),'cache_hit':False,'development':False,'synthetic':False,
                      'provenance':{'provider':'OpenRegister','origin':'live_provider_response','endpoint':SOURCE}}
            analysis=analyze_financials(data,today=datetime.fromtimestamp(self.clock(),timezone.utc).date())
            has_figures=any(fact['value'] is not None for period in analysis['periods'] for fact in period['facts'].values())
            if not has_figures:
                analysis['coverage']='No reported financial figures extracted; statement publication remains unknown.'
                analysis['financial_data_status']='no_figures_extracted'
            result={'status':'completed','financial_data':data,'analysis':analysis,**identity,
                    'credit_usage':self.status(),'overall_risk':'Undetermined','legal_findings':[]}
        except BaseException as error:
            if not isinstance(error,Exception):raise
            result={'status':'manual_review','financial_data_status':'unknown','publication_status':'unknown',
                    'error_code':error.code if isinstance(error,ProfileError) else 'unsupported_or_uncertain_response',
                    'reason':'Financial retrieval or analysis failed; no retry permitted. This does not prove statements are unavailable.',
                    'credit_usage':self.status(),**identity,'overall_risk':'Undetermined'}
        with self.transaction() as db:
            result['credit_usage']['state']=result['status']
            db.execute('UPDATE attempt SET state=?,completed_at=?,result=? WHERE id=1',
                       (result['status'],timestamp(self.clock()),json.dumps(result)))
        self.write_report(result)
        if result['status']=='completed' and not cached:
            self.cache_dir.mkdir(parents=True,exist_ok=True)
            path=self.cache_dir/(DIRECT_ID+'.json');tmp=path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'company_id':DIRECT_ID,'saved_at':timestamp(self.clock()),'result':data}));os.chmod(tmp,0o600);tmp.replace(path)
        return result

    def write_report(self, result):
        lines=['# Volkswagen financial due diligence — controlled test','',f'Company: {DIRECT_ID}; Germany; Amtsgericht Braunschweig HRB 100484.',
               '',f'Source: [OpenRegister financial API]({SOURCE})','Provider data is not independently audited evidence.',
               'No synthetic research or legal guidance is treated as company evidence.','',
               'Overall risk: **Undetermined**. Financial indicators are not legal findings.',
               'Credit usage (estimated, not confirmed billing): '+text(result['credit_usage']['estimated_credits_reserved'])+' / 10. Cost unknown.','']
        analysis=result.get('analysis',{});data=result.get('financial_data',{})
        lines+=['Retrieval timestamp: '+text(data.get('retrieved_at')),'Cache hit: '+text(data.get('cache_hit')),'',
                '## Reported periods and figures','']
        if analysis:
            lines+=financial_section(analysis)
            for period in analysis['periods']:
                lines+=['Report ID: '+text(period.get('report_id'))]
                lines+=['- '+text(metric)+' source field: '+text(fact.get('source_field')) for metric,fact in period['facts'].items() if fact.get('value') is not None]
        lines+=['','## Provider report references','']
        for report in data.get('raw',{}).get('reports',[]):
            lines+=['Report '+text(report.get('report_id'))+'; period '+text(report.get('report_start_date'))+' to '+text(report.get('report_end_date'))+'; published '+text(report.get('published_at'))]
            lines+=['- '+document_reference(report.get('report_id'),index) for index, source in enumerate(report.get('sources',[]),1)]
        lines+=['','## Missing evidence and limitations','',text(result.get('reason') or analysis.get('coverage')),
                'Absent figures are unavailable, not zero. No figures returned does not prove no statements were published.',
                'Missing currency or scale blocks ratios and monetary comparisons. Estimates and ambiguous table labels are excluded.',
                'No independent accounts, audit opinions, liquidity forecasts or subsequent events have been reviewed.',
                'Year-over-year interpretation requires consecutive comparable full-year periods; review gaps manually.']
        lines+=analysis.get('limitations',[])
        path=self.directory/'report.md';path.write_text('\n'.join(lines)+'\n');os.chmod(path,0o600)
        return path

    def regenerate_report(self):
        """Offline reanalysis of the saved response; original attempt/result remains immutable."""
        with self.transaction() as db:
            row=db.execute('SELECT result FROM attempt WHERE id=1').fetchone()
        if not row or not row[0]:raise ProfileError('report_unavailable','No completed result is available.')
        result=copy.deepcopy(json.loads(row[0]))
        data=result.get('financial_data')
        if data:
            data['raw']=validate_raw(data['raw'])
            result['analysis']=analyze_financials(data,today=datetime.fromtimestamp(self.clock(),timezone.utc).date())
        result['report_regenerated_at']=timestamp(self.clock())
        # Derived private artifact, separate from the immutable request ledger/cache.
        path=self.directory/'reanalysis.json'
        path.write_text(json.dumps(result,indent=2));os.chmod(path,0o600)
        return self.write_report(result)


def main():
    parser=argparse.ArgumentParser(description='Separate Volkswagen financial test: no paid calls except approved run --enable-live-test')
    commands=parser.add_subparsers(dest='command',required=True)
    for command in ('preview','status','report'):commands.add_parser(command)
    approve=commands.add_parser('approve');approve.add_argument('--acknowledge',required=True)
    run=commands.add_parser('run');run.add_argument('--enable-live-test',action='store_true')
    args=parser.parse_args()
    try:
        profile=FinancialTest()
        if args.command=='approve':result=profile.approve(args.acknowledge)
        elif args.command=='preview':result=profile.preview()
        elif args.command=='status':result=profile.status()
        elif args.command=='report':
            result={'report':str(profile.regenerate_report())}
        else:
            if not args.enable_live_test:raise ProfileError('live_test_disabled','Explicit --enable-live-test is required.',403)
            result=profile.run(profile.grant.read_text().strip())
            # Raw data stays private; terminal output contains only diagnostics/usage.
            result={k:result[k] for k in ('status','error_code','reason','credit_usage') if k in result}
        print(json.dumps(result,indent=2))
        if result.get('status')=='manual_review':raise SystemExit(1)
    except Exception as error:
        print(json.dumps({'status':'blocked','error_code':error.code if isinstance(error,ProfileError) else 'local_failure',
                          'message':error.message if isinstance(error,ProfileError) else 'Inspect local state; no automatic retry was made.'}))
        raise SystemExit(1)


if __name__=='__main__':main()
