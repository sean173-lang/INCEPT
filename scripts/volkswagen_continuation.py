"""One separately approved detail continuation; never resets the search ledger."""
import hashlib
import hmac
import json
import os
import secrets

from scripts.volkswagen_profile import VolkswagenProfile, ProfileError, load_policy, matches_target, timestamp

DIRECT_ID = 'DE-HRB-P1103-100484-P2413'
DIRECT_ACK = f'{DIRECT_ID} | Volkswagen AG | Germany | Amtsgericht Braunschweig | HRB 100484 | additional 10 credits | cumulative 15 credits'


class VolkswagenContinuation(VolkswagenProfile):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.direct_grant = self.directory/'direct-approval.local'
        with self.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS continuation (id INTEGER PRIMARY KEY CHECK(id=1), digest TEXT NOT NULL, expires REAL NOT NULL, state TEXT NOT NULL, result TEXT)')

    def eligible(self, db):
        prior = db.execute('SELECT status,result FROM test WHERE id=1').fetchone()
        search = db.execute("SELECT state FROM operations WHERE name='company_search'").fetchone()
        if (not prior or prior[0]!='completed' or not prior[1] or json.loads(prior[1]).get('status')!='not_found'
                or not search or search[0]!='succeeded'):
            raise ProfileError('continuation_ineligible', 'A completed unsuccessful identity search is required; no new search is allowed.')
        if db.execute("SELECT 1 FROM operations WHERE name='company_details'").fetchone():
            raise ProfileError('details_already_attempted', 'A detail attempt already exists; manual review is required.')

    def approve_direct(self, acknowledgement):
        load_policy(self.config,self.clock())
        if acknowledgement != DIRECT_ACK:
            raise ProfileError('approval_required','The exact direct-detail acknowledgement is required.',403)
        nonce=secrets.token_urlsafe(32)
        with self.transaction() as db:
            self.eligible(db)
            row=db.execute('SELECT state FROM continuation WHERE id=1').fetchone()
            if (row and row[0]!='approved') or db.execute("SELECT 1 FROM operations WHERE name='direct_company_details'").fetchone():
                raise ProfileError('duplicate_request_blocked','The continuation has already started and cannot be reapproved.')
            if db.execute('SELECT COALESCE(SUM(credits),0) FROM operations').fetchone()[0]+10>15:
                raise ProfileError('credit_limit_exceeded','The cumulative 15-credit ceiling blocks approval.',429)
            db.execute('INSERT OR REPLACE INTO continuation VALUES(1,?,?,?,NULL)',
                       (hashlib.sha256(nonce.encode()).hexdigest(),self.clock()+3600,'approved'))
            fd=os.open(self.direct_grant,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
            with os.fdopen(fd,'w') as stream:stream.write(nonce)
            os.chmod(self.direct_grant,0o600)
        return {'approved':True,'provider_company_id':DIRECT_ID,'additional_estimated_credits':10,'max_cumulative_credits':15,'expires_in_seconds':3600,'provider_requests_made':0}

    def direct_result(self):
        with self.transaction() as db:
            row=db.execute('SELECT state,result FROM continuation WHERE id=1').fetchone()
        return json.loads(row[1]) if row and row[1] else {'status':row[0] if row else 'not_started'}

    def verify_direct(self, nonce):
        load_policy(self.config,self.clock())
        with self.transaction() as db:
            row=db.execute('SELECT digest,expires,state,result FROM continuation WHERE id=1').fetchone()
            if not row or not isinstance(nonce,str) or not hmac.compare_digest(row[0],hashlib.sha256(nonce.encode()).hexdigest()):
                raise ProfileError('approval_required','A separate direct-detail approval is required.',403)
            if self.clock()>row[1]:raise ProfileError('approval_expired','Direct-detail approval expired.',403)
            if row[3]:return json.loads(row[3])
            if row[2]!='approved':raise ProfileError('duplicate_request_blocked','Continuation pending or uncertain; manual review required.')
            self.eligible(db)
            db.execute("UPDATE continuation SET state='running' WHERE id=1")
        evidence=[]
        try:
            cached,_=self.existing_cache()
            if cached and cached['identity']['provider_company_id']==DIRECT_ID and cached['identity'].get('country'):
                identity=cached['identity'];evidence.append(cached['provenance'])
            else:
                with self.transaction() as db:
                    if db.execute("SELECT 1 FROM operations WHERE name IN ('direct_company_details','company_details')").fetchone():
                        raise ProfileError('duplicate_request_blocked','A detail attempt already exists.')
                    if db.execute('SELECT COALESCE(SUM(credits),0) FROM operations').fetchone()[0]+10>15:
                        raise ProfileError('credit_limit_exceeded','The cumulative 15-credit ceiling blocks execution.',429)
                    self.transport.preflight()
                    db.execute('INSERT INTO operations(name,credits,state,requested_at) VALUES(?,?,?,?)',
                               ('direct_company_details',10,'pending',timestamp(self.clock())))
                # Same documented standard-detail transport, fixed ID, no fallback.
                identity=self.transport.request('company_details',DIRECT_ID)
                provenance={'provider':'OpenRegister','origin':'live_provider_response','cache_hit':False,
                            'retrieved_at':timestamp(self.clock()),'endpoint':'GET /v1/company/'+DIRECT_ID,
                            'evidence_class':'provider_record_not_independently_certified'}
                evidence.append(provenance)
                with self.transaction() as db:
                    db.execute("UPDATE operations SET state='succeeded',completed_at=?,evidence=? WHERE name='direct_company_details'",
                               (timestamp(self.clock()),json.dumps({'data':identity,'provenance':provenance})))
            required=('provider_company_id','name','country','register_court','register_type','register_number')
            verified=(all(identity.get(field) for field in required)
                      and identity.get('provider_company_id')==DIRECT_ID and matches_target(identity,self.policy))
            result={'status':'verified' if verified else 'manual_review','company':identity,'evidence':evidence}
        except BaseException as error:
            code=error.code if isinstance(error,ProfileError) else 'uncertain_operation_failure'
            with self.transaction() as db:
                db.execute("UPDATE operations SET state='failed_or_uncertain',completed_at=?,diagnostic=? WHERE name='direct_company_details' AND state='pending'",
                           (timestamp(self.clock()),code))
            if not isinstance(error,Exception):raise
            result={'status':'manual_review','company':None,'evidence':evidence,
                    'error':{'code':code,'message':'Direct-detail verification could not complete. No retry is permitted; review is required.'}}
        result.update(provider_company_id_requested=DIRECT_ID,verification_scope='fixed_register_identity_only',
                      development=False,synthetic=False,risk_assessment='Undetermined',legal_findings_verified=False,
                      financials_executed=False,other_paid_providers_executed=False,credit_usage=self.status(),
                      warning='The supplied ID was unverified until checked against provider details. Identity verification is not legal clearance. Fixture research is not company evidence.')
        with self.transaction() as db:
            db.execute("UPDATE continuation SET state='completed',result=? WHERE id=1",(json.dumps(result),))
        return result
