"""One-shot, durable Volkswagen register test. No generic provider/tool router.

Reservations commit before I/O. A crash, timeout or failed request cannot be
retried through a new process or approval. No reset operation is provided.
"""
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
from dotenv import dotenv_values
from scripts.api_usage import JsonCache, UsageTracker
from scripts.company_service import normalized, court, registration, valid_provider_id

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / 'config/volkswagen_live_test.json'
STATE_DIR = ROOT / 'data/volkswagen_live_test'
BASE = 'https://api.openregister.de'
OPERATIONS = {'company_search': ('/v1/autocomplete/company', 1),
              'company_details': ('/v1/company/{company_id}', 10)}


class ProfileError(Exception):
    def __init__(self, code, message, status=409):
        self.code, self.message, self.status = code, message, status


def timestamp(now):
    return datetime.fromtimestamp(now, timezone.utc).isoformat()


def load_policy(path=CONFIG, now=None):
    try:
        policy = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        raise ProfileError('pricing_or_policy_unverified', 'The reviewed policy file cannot be read; requests are blocked.', 503) from None
    today = datetime.fromtimestamp(time.time() if now is None else now, timezone.utc).date()
    expected = {'name':'Volkswagen AG','allowed_legal_names':['Volkswagen AG','Volkswagen Aktiengesellschaft'],
                'jurisdiction':'Germany','register_court':'Amtsgericht Braunschweig','register_type':'HRB','register_number':'100484'}
    try:
        if (policy['profile_id'] != 'volkswagen-register-test-v1' or policy['company'] != expected
                or policy['enabled_by_default'] is not False or policy['max_credits'] != 15
                or policy['max_search_requests'] != 1 or policy['max_detail_requests'] != 1 or policy['realtime'] is not False):
            raise ValueError()
        if any(type(policy[k]) is not int for k in ('max_credits','max_search_requests','max_detail_requests')):
            raise ValueError()
        pricing = policy['pricing']
        reviewed, until = date.fromisoformat(pricing['verified_on']), date.fromisoformat(pricing['valid_until'])
        if not reviewed <= today <= until or (until-reviewed).days > 7 or pricing['source'] != 'https://docs.openregister.de/pricing':
            raise ValueError()
        if set(pricing) != {'verified_on','valid_until','source','company_search','company_details'}:
            raise ValueError()
        for name,(path_value, credits) in OPERATIONS.items():
            item = pricing[name]
            source = 'https://docs.openregister.de/endpoint/' + ('autocomplete-company' if name=='company_search' else 'company')
            if type(item.get('credits')) is not int or item != {'method':'GET','path':path_value,'credits':credits,'source':source}:
                raise ValueError()
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ProfileError('pricing_or_policy_unverified', 'The fixed scope or endpoint credit documentation is missing, expired or inconsistent; requests are blocked.', 503) from None
    return policy


def reduce_identity(raw, *, details=False):
    if not isinstance(raw, dict):
        raise ProfileError('unsupported_response', 'Provider identity response is not a supported object.', 502)
    if raw.get('development') is True or raw.get('synthetic') is True:
        raise ProfileError('fixture_evidence_rejected', 'Synthetic data cannot establish live company identity.')
    name = raw.get('name')
    if isinstance(name, dict):
        name = name.get('name')
    register = raw.get('register') if details else raw
    legacy = raw.get('company_register') if details else None
    if register is None:
        register = legacy or {}
    if not isinstance(register, dict):
        raise ProfileError('unsupported_response', 'Provider registration fields are unsupported.', 502)
    if legacy and raw.get('register'):
        for field in ('register_number','register_type','register_court'):
            if register.get(field) != legacy.get(field):
                raise ProfileError('conflicting_registration', 'Current and legacy register fields conflict.')
    if details and register.get('company_id') is not None and register['company_id'] != raw.get('id'):
        raise ProfileError('conflicting_registration', 'Register and top-level provider identifiers conflict.')
    address = raw.get('address') or {}
    country = raw.get('country') or (address.get('country') if isinstance(address,dict) else None)
    result = {'provider_company_id':raw.get('id') if details else raw.get('company_id'), 'name':name,
              'register_number':register.get('register_number'), 'register_type':register.get('register_type'),
              'register_court':register.get('register_court'),
              'country':country}
    if not valid_provider_id(result['provider_company_id'],'Germany'):
        raise ProfileError('unsupported_response', 'A valid provider company identifier is required.', 502)
    if any(v is not None and not isinstance(v,str) for v in result.values()):
        raise ProfileError('unsupported_response', 'Provider identity fields have unsupported types.', 502)
    return result


def matches_target(identity, policy):
    target = policy['company']
    kind, number = registration(identity.get('register_number'))
    explicit_kind = normalized(identity.get('register_type'))
    if kind and explicit_kind and kind != explicit_kind:
        return False
    actual_kind = explicit_kind or kind
    country = identity.get('country')
    return (normalized(identity.get('name')) in {normalized(n) for n in target['allowed_legal_names']}
            and actual_kind == 'hrb' and number == '100484'
            and court(identity.get('register_court')) == court(target['register_court'])
            and (country is None or normalized(country) in ('de','deu','deutschland','germany')))


class RegisterTransport:
    """Two documented GET routes only; no redirects, retries or SDK fallback."""
    def preflight(self):
        key = os.getenv('OPENREGISTER_API_KEY') or dotenv_values(ROOT/'.env').get('OPENREGISTER_API_KEY')
        if not key:
            raise ProfileError('missing_credentials','OpenRegister credentials are unavailable; no provider request made.',503)
        return key

    def request(self, operation, provider_id=None):
        if operation not in OPERATIONS or operation == 'company_details' and not valid_provider_id(provider_id,'Germany'):
            raise ProfileError('operation_forbidden','Only approved register search and selected company details are supported.',403)
        key = self.preflight()
        path = OPERATIONS[operation][0]
        if provider_id is not None:
            path = path.replace('{company_id}',provider_id)
        params = {'query':'Volkswagen AG'} if operation=='company_search' else {'realtime':'false'}
        try:
            with requests.Session() as session:
                session.trust_env=False
                session.mount('https://',requests.adapters.HTTPAdapter(max_retries=0))
                response=session.get(BASE+path,params=params,headers={'Authorization':'Bearer '+key,'Accept':'application/json'},
                                     timeout=30,allow_redirects=False)
                if response.status_code != 200:
                    codes={401:'provider_authentication_failed',403:'provider_permission_denied',404:'provider_not_found',429:'provider_rate_limited'}
                    raise ProfileError(codes.get(response.status_code,'provider_http_error'),
                                       f'Provider returned HTTP {response.status_code}; no retry made. This does not establish missing filings.',502)
                try:
                    raw=response.json()
                except ValueError:
                    raise ProfileError('unsupported_response','Provider response was not supported JSON; no retry made.',502) from None
        except requests.exceptions.Timeout:
            raise ProfileError('provider_timeout','Request timed out; processing and billing are uncertain. No retry is permitted.',504) from None
        except requests.RequestException:
            raise ProfileError('provider_connection_failed','Provider transport failed; no retry is permitted.',502) from None
        if operation=='company_search':
            if not isinstance(raw,dict) or not isinstance(raw.get('results'),list):
                raise ProfileError('unsupported_response','Provider search shape is unsupported.',502)
            return [reduce_identity(row) for row in raw['results']]
        return reduce_identity(raw,details=True)


class VolkswagenProfile:
    def __init__(self, *, directory=STATE_DIR, config=CONFIG, cache_dir=None, transport=None, clock=time.time):
        self.directory=Path(directory)
        self.config=Path(config)
        self.clock=clock
        self.policy=load_policy(config,clock())
        self.transport=transport or RegisterTransport()
        self.cache_dir=Path(cache_dir) if cache_dir else ROOT/'data/api_cache'
        self.directory.mkdir(parents=True,exist_ok=True,mode=0o700)
        os.chmod(self.directory,0o700)
        self.db=self.directory/'state.sqlite3'
        self.grant_file=self.directory/'approval.local'
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY CHECK(id=1), policy_hash TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS approval (id INTEGER PRIMARY KEY CHECK(id=1), digest TEXT NOT NULL, expires REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS test (id INTEGER PRIMARY KEY CHECK(id=1), status TEXT NOT NULL, result TEXT, started_at TEXT NOT NULL, selected_id TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS operations (name TEXT PRIMARY KEY, credits INTEGER NOT NULL, state TEXT NOT NULL, requested_at TEXT NOT NULL, completed_at TEXT, evidence TEXT, diagnostic TEXT)')
            fingerprint=hashlib.sha256(json.dumps(self.policy,sort_keys=True).encode()).hexdigest()
            old=db.execute('SELECT policy_hash FROM metadata WHERE id=1').fetchone()
            if old and old[0]!=fingerprint:
                raise ProfileError('policy_changed','Persisted test policy differs; manual review is required. No new budget was created.',503)
            db.execute('INSERT OR IGNORE INTO metadata VALUES(1,?)',(fingerprint,))
        os.chmod(self.db,0o600)

    @contextmanager
    def transaction(self):
        with closing(sqlite3.connect(self.db,timeout=5)) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    def approve(self, acknowledgement):
        load_policy(self.config,self.clock())
        if acknowledgement != 'Volkswagen AG | Germany | Amtsgericht Braunschweig | HRB 100484 | 15 credits':
            raise ProfileError('approval_required','The exact fixed-scope acknowledgement is required.',403)
        nonce=secrets.token_urlsafe(32)
        with self.transaction() as db:
            if db.execute('SELECT 1 FROM test').fetchone() or db.execute('SELECT 1 FROM operations').fetchone():
                raise ProfileError('test_already_started','The existing test cannot be reset or reapproved.',409)
            db.execute('INSERT OR REPLACE INTO approval VALUES(1,?,?)',(hashlib.sha256(nonce.encode()).hexdigest(),self.clock()+3600))
            fd=os.open(self.grant_file,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as stream:
                stream.write(nonce)
            os.chmod(self.grant_file,0o600)
        return {'approved':True,'expires_in_seconds':3600,'max_credits':15,'provider_requests_made':0}

    def status(self):
        with self.transaction() as db:
            credits=db.execute('SELECT COALESCE(SUM(credits),0) FROM operations').fetchone()[0]
            test=db.execute('SELECT status FROM test WHERE id=1').fetchone()
            rows=db.execute('SELECT name,credits,state,requested_at,completed_at,diagnostic FROM operations ORDER BY requested_at').fetchall()
        return {'profile_id':self.policy['profile_id'],'state':test[0] if test else 'not_started','estimated_credits_reserved':credits,
                'max_credits':15,'money_cost':'Cost unknown','billing_confirmed':False,
                'operations':[dict(zip(('operation','estimated_credits','state','requested_at','completed_at','diagnostic'),row)) for row in rows],
                'financials_enabled':False,'other_providers_enabled':False,'autonomous_research_enabled':False}

    def result(self):
        with self.transaction() as db:
            row=db.execute('SELECT result FROM test WHERE id=1').fetchone()
        return json.loads(row[0]) if row and row[0] else None

    def preview(self):
        detail, search = self.existing_cache()
        state = self.status()
        return {'profile_id':self.policy['profile_id'], 'company':self.policy['company'],
                'cache_state':'detail_cache' if detail else 'search_cache' if search is not None else 'miss',
                'estimated_new_credits':0 if state['state']=='completed' or detail else 10 if search is not None else 11,
                'max_credits':15, 'pricing_verified_on':self.policy['pricing']['verified_on'],
                'pricing_valid_until':self.policy['pricing']['valid_until'], 'money_cost':'Cost unknown',
                'test_state':state['state'], 'provider_requests_made_by_preview':0,
                'cache_warning':'Legacy/unattested, synthetic, stale or conflicting caches cannot establish live identity.'}

    def existing_cache(self):
        """Read existing tracker files only. Unknown/malformed/future/stale entries are not proof."""
        cache=JsonCache(self.cache_dir,self.clock)
        valid_details=[]
        for path in self.cache_dir.glob('*.json'):
            entry=cache.get(path.stem,86400)
            if not isinstance(entry,dict) or not isinstance(entry.get('payload'),dict):
                continue
            provenance=entry.get('provenance') or {}
            if provenance.get('provider')!='OpenRegister' or provenance.get('mode')!='live' or provenance.get('origin')!='provider_response':
                continue
            try:
                identity=reduce_identity(entry['payload'],details=True)
                expected=UsageTracker.key('OpenRegister','company_details',identity['provider_company_id'])
                retrieved=entry.get('retrieved_at')
                if path.stem!=expected or not matches_target(identity,self.policy) or not isinstance(retrieved,str):
                    continue
                parsed=datetime.fromisoformat(retrieved)
                if parsed.tzinfo is None:
                    continue
                when=parsed.timestamp()
                if not 0<=self.clock()-when<86400:
                    continue
                valid_details.append({'identity':identity,'provenance':{'provider':'OpenRegister','origin':'existing_detail_cache',
                                      'cache_hit':True,'retrieved_at':retrieved,'observed_at':timestamp(self.clock()),
                                      'endpoint':'GET /v1/company/{company_id}','evidence_class':'provider_record_not_independently_certified'}})
            except (ProfileError,ValueError,TypeError):
                continue
        # Conflicting caches never cause automatic selection.
        unique={json.dumps(row['identity'],sort_keys=True):row for row in valid_details}
        if len(unique)>1:
            raise ProfileError('ambiguous_cache','Conflicting Volkswagen detail caches require manual review.')
        if unique:
            return next(iter(unique.values())),None
        search_key=UsageTracker.key('OpenRegister','company_search','Volkswagen AG')
        entry=cache.get(search_key,86400)
        candidates=None
        if isinstance(entry,dict) and isinstance(entry.get('results'),list):
            provenance=entry.get('provenance') or {}
            if provenance.get('provider')=='OpenRegister' and provenance.get('mode')=='live' and provenance.get('origin')=='provider_response':
                try:
                    parsed=datetime.fromisoformat(provenance['retrieved_at'])
                    if parsed.tzinfo is not None and 0<=self.clock()-parsed.timestamp()<86400:
                        candidates={'data':[reduce_identity(row) for row in entry['results']],
                                    'provenance':{'provider':'OpenRegister','origin':'existing_search_cache','cache_hit':True,
                                                  'retrieved_at':provenance['retrieved_at'],'observed_at':timestamp(self.clock()),
                                                  'endpoint':'GET /v1/autocomplete/company'}}
                except (ProfileError,KeyError,ValueError,TypeError):
                    pass
        return None,candidates

    def request_once(self, operation, provider_id=None):
        load_policy(self.config,self.clock())
        if operation not in OPERATIONS:
            raise ProfileError('operation_forbidden','Only OpenRegister search and details are allowed.',403)
        # Credentials are checked without I/O before reserving a potentially paid attempt.
        credits=OPERATIONS[operation][1]
        with self.transaction() as db:
            test=db.execute('SELECT status,selected_id FROM test WHERE id=1').fetchone()
            if not test or test[0]!='running' or operation=='company_details' and (not test[1] or test[1]!=provider_id):
                raise ProfileError('operation_forbidden','A running approved test and the fixed register-selected ID are required.',403)
            if db.execute('SELECT 1 FROM operations WHERE name=?',(operation,)).fetchone():
                raise ProfileError('duplicate_request_blocked','An attempt already exists; no duplicate request is permitted.')
            total=db.execute('SELECT COALESCE(SUM(credits),0) FROM operations').fetchone()[0]
            if total+credits>15:
                raise ProfileError('credit_limit_exceeded','The persistent 15-credit limit blocks this operation.',429)
            self.transport.preflight()
            db.execute('INSERT INTO operations(name,credits,state,requested_at) VALUES(?,?,?,?)',
                       (operation,credits,'pending',timestamp(self.clock())))
        try:
            data=self.transport.request(operation,provider_id)
            evidence={'data':data,'provenance':{'provider':'OpenRegister','origin':'live_provider_response','cache_hit':False,
                      'retrieved_at':timestamp(self.clock()),'endpoint':'GET '+OPERATIONS[operation][0],
                      'evidence_class':'provider_record_not_independently_certified'}}
            with self.transaction() as db:
                db.execute('UPDATE operations SET state=?,completed_at=?,evidence=? WHERE name=?',
                           ('succeeded',timestamp(self.clock()),json.dumps(evidence),operation))
            return evidence
        except BaseException as error:
            diagnostic=error.code if isinstance(error,ProfileError) else 'uncertain_operation_failure'
            with self.transaction() as db:
                db.execute('UPDATE operations SET state=?,completed_at=?,diagnostic=? WHERE name=?',
                           ('failed_or_uncertain',timestamp(self.clock()),diagnostic,operation))
            if isinstance(error,ProfileError):raise
            if not isinstance(error,Exception):raise
            raise ProfileError('uncertain_operation_failure','The operation failed; no retry is permitted.',502) from None

    def verify(self, nonce):
        load_policy(self.config,self.clock())
        with self.transaction() as db:
            approval=db.execute('SELECT digest,expires FROM approval WHERE id=1').fetchone()
            if not approval or not nonce or not hmac.compare_digest(approval[0],hashlib.sha256(nonce.encode()).hexdigest()):
                raise ProfileError('approval_required','Use the local explicit approval command first.',403)
            if self.clock()>approval[1]:
                raise ProfileError('approval_expired','The test approval has expired.',403)
            prior=db.execute('SELECT status,result FROM test WHERE id=1').fetchone()
            if prior:
                if prior[1]:return json.loads(prior[1])
                raise ProfileError('test_pending_or_uncertain','A previous test started but has no final result; manual review is required.')
            db.execute('INSERT INTO test(id,status,result,started_at) VALUES(1,?,NULL,?)',('running',timestamp(self.clock())))
        evidence=[]
        try:
            cached,candidates=self.existing_cache()
            if cached:
                result={'status':'verified','company':cached['identity'],'evidence':[cached['provenance']]}
            else:
                evidence=[]
                if candidates is None:
                    response=self.request_once('company_search')
                    candidates=response['data'];evidence.append(response['provenance'])
                else:
                    evidence.append(candidates['provenance'])
                    candidates=candidates['data']
                matches={c['provider_company_id']:c for c in candidates if matches_target(c,self.policy)}
                if len(matches)!=1:
                    result={'status':'ambiguous' if len(matches)>1 else 'not_found','company':None,'evidence':evidence,
                            'warning':'No unique match to HRB 100484, Braunschweig and the allowed legal names; no detail request made.'}
                else:
                    identifier=next(iter(matches))
                    with self.transaction() as db:
                        db.execute('UPDATE test SET selected_id=? WHERE id=1',(identifier,))
                    response=self.request_once('company_details',identifier)
                    identity=response['data'];evidence.append(response['provenance'])
                    passed=identity['provider_company_id']==identifier and matches_target(identity,self.policy)
                    result={'status':'verified' if passed else 'verification_failed','company':identity,'evidence':evidence}
        except ProfileError as error:
            result={'status':'verification_failed','error':{'code':error.code,'message':error.message},'company':None,'evidence':evidence}
        except Exception:
            result={'status':'verification_failed','error':{'code':'uncertain_test_failure','message':'The test could not complete; no automatic retry is permitted.'},'company':None,'evidence':evidence}
        result.update(profile_id=self.policy['profile_id'],development=False,synthetic=False,
                      verification_scope='fixed_register_identity_only',credit_usage=self.status(),
                      legal_findings_verified=False,financials_executed=False,other_paid_providers_executed=False,
                      risk_assessment='Undetermined',warning=result.get('warning','Provider record consistency does not establish legal clearance. Fixture research and legal reference guidance are not company findings.'))
        result['credit_usage']['state']='completed'
        with self.transaction() as db:
            db.execute('UPDATE test SET status=?,result=? WHERE id=1',('completed',json.dumps(result)))
        return result
