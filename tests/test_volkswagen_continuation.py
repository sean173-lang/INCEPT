"""Offline direct continuation tests; no provider evidence or requests."""
import concurrent.futures
import copy
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import MagicMock

import test_volkswagen_live_test as fixtures
from test_volkswagen_live_test import NOW, RAW, ACKNOWLEDGEMENT
from offline_support import OfflineTestCase
from scripts.volkswagen_profile import ProfileError, reduce_identity
from scripts.volkswagen_continuation import VolkswagenContinuation, DIRECT_ACK, DIRECT_ID
from scripts.api_usage import JsonCache, UsageTracker
from scripts.volkswagen_live_test import create_app
from fastapi.testclient import TestClient


class ContinuationTests(OfflineTestCase):
    setUp=fixtures.VolkswagenTests.setUp

    def profile(self):
        return VolkswagenContinuation(directory=self.root/'state',cache_dir=self.root/'cache',transport=self.transport,clock=lambda:self.now[0])

    def ready(self):
        p=self.profile();p.approve(ACKNOWLEDGEMENT)
        self.transport.request.return_value=[];self.transport.request.side_effect=lambda *args:[]
        original=p.verify(p.grant_file.read_text())
        self.assertEqual(original['status'],'not_found')
        self.raw=copy.deepcopy(RAW);self.raw['id']=DIRECT_ID;self.raw['register']['company_id']=DIRECT_ID
        self.transport.request.side_effect=lambda *args:reduce_identity(self.raw,details=True)
        self.transport.request.reset_mock()
        return p,original

    def approved(self):
        p,original=self.ready();p.approve_direct(DIRECT_ACK)
        return p,p.direct_grant.read_text(),original

    def test_fresh_approval_scope_and_expiry(self):
        p,_=self.ready()
        for token in (None,'wrong',p.grant_file.read_text()):
            with self.assertRaises(ProfileError):p.verify_direct(token)
        with self.assertRaises(ProfileError):p.approve_direct(ACKNOWLEDGEMENT)
        p.approve_direct(DIRECT_ACK);self.now[0]+=3601
        with self.assertRaises(ProfileError):p.verify_direct(p.direct_grant.read_text())
        self.transport.request.assert_not_called()

    def test_ineligible_without_search(self):
        with self.assertRaises(ProfileError):self.profile().approve_direct(DIRECT_ACK)
        self.transport.request.assert_not_called()

    def test_success_persists_separate_outcomes_and_replay(self):
        p,token,original=self.approved();result=p.verify_direct(token)
        self.assertEqual(result['status'],'verified');self.assertEqual(result['credit_usage']['estimated_credits_reserved'],11)
        self.transport.request.assert_called_once_with('company_details',DIRECT_ID)
        self.assertEqual(p.result(),original)
        self.assertEqual(self.profile().verify_direct(token),result)
        with self.assertRaises(ProfileError):self.profile().approve_direct(DIRECT_ACK)
        with p.transaction() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM operations').fetchone()[0],2)

    def test_concurrent_calls_only_one_detail(self):
        p,token,_=self.approved()
        def run(_):
            try:return self.profile().verify_direct(token)['status']
            except ProfileError as e:return e.code
        with concurrent.futures.ThreadPoolExecutor(4) as pool:results=list(pool.map(run,range(4)))
        self.assertIn('verified',results);self.transport.request.assert_called_once()
        self.assertEqual(p.status()['estimated_credits_reserved'],11)

    def test_cumulative_budget_blocks_at_approval_and_execution(self):
        p,token,_=self.approved()
        with p.transaction() as db:
            db.execute("INSERT INTO operations(name,credits,state,requested_at) VALUES('prior',5,'pending','mock')")
        self.assertEqual(p.verify_direct(token)['status'],'manual_review')
        self.transport.request.assert_not_called()
        self.assertEqual(p.status()['estimated_credits_reserved'],6)

    def test_budget_blocks_fresh_approval(self):
        p,_=self.ready()
        with p.transaction() as db:
            db.execute("INSERT INTO operations(name,credits,state,requested_at) VALUES('prior',5,'pending','mock')")
        with self.assertRaises(ProfileError):p.approve_direct(DIRECT_ACK)
        self.transport.request.assert_not_called()

    def test_cached_detail_requires_provenance_and_exact_identity(self):
        p,token,_=self.approved()
        entry={'payload':self.raw,'retrieved_at':'2026-11-10T00:00:00+00:00',
               'provenance':{'provider':'OpenRegister','mode':'live','origin':'provider_response'}}
        JsonCache(self.root/'cache',lambda:NOW).put(UsageTracker.key('OpenRegister','company_details',DIRECT_ID),entry)
        result=p.verify_direct(token)
        self.assertEqual(result['status'],'verified');self.assertTrue(result['evidence'][0]['cache_hit'])
        self.assertEqual(result['credit_usage']['estimated_credits_reserved'],1);self.transport.request.assert_not_called()

    def test_missing_mismatched_and_conflicting_fields(self):
        for key,value in [('country',None),('country','GB'),('name',None),('name','Volkswagen Financial Services AG'),
                          ('register_court',None),('register_court','Berlin'),('register_number',None),('register_number','1'),
                          ('register_type',None),('register_type','HRA'),('provider_company_id','other')]:
            with self.subTest(key=key,value=value):
                # Independent mock ledgers, never real state.
                self.root=self.root/(key+str(value).replace(' ','_'));self.root.mkdir(parents=True)
                p,token,_=self.approved();identity=reduce_identity(self.raw,details=True);identity[key]=value
                self.transport.request.side_effect=lambda *args:identity
                self.assertEqual(p.verify_direct(token)['status'],'manual_review')

    def test_timeout_keeps_reservation_and_prevents_retry(self):
        p,token,_=self.approved();self.transport.request.side_effect=TimeoutError('secret must not escape')
        result=p.verify_direct(token)
        self.assertEqual(result['status'],'manual_review');self.assertNotIn('secret',json.dumps(result))
        self.assertEqual(self.profile().verify_direct(token),result);self.transport.request.assert_called_once()
        self.assertEqual(p.status()['estimated_credits_reserved'],11)

    def test_crash_keeps_reservation_and_blocks_restart(self):
        p,token,_=self.approved();self.transport.request.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):p.verify_direct(token)
        with self.assertRaises(ProfileError):self.profile().verify_direct(token)
        with self.assertRaises(ProfileError):self.profile().approve_direct(DIRECT_ACK)
        self.assertEqual(p.status()['estimated_credits_reserved'],11)

    def test_hard_exit_keeps_pending_reservation(self):
        p,token,_=self.approved()
        code='''
import os,sys
from pathlib import Path
from scripts.volkswagen_continuation import VolkswagenContinuation
class Crash:
    def preflight(self): pass
    def request(self,*args): os._exit(71)
p=VolkswagenContinuation(directory=Path(sys.argv[1])/'state',cache_dir=Path(sys.argv[1])/'cache',transport=Crash(),clock=lambda:float(sys.argv[2]))
p.verify_direct(p.direct_grant.read_text())
'''
        result=subprocess.run([sys.executable,'-c',code,str(self.root),str(NOW)],capture_output=True)
        self.assertEqual(result.returncode,71)
        with self.assertRaises(ProfileError):self.profile().verify_direct(token)
        with p.transaction() as db:
            self.assertEqual(db.execute("SELECT state FROM operations WHERE name='direct_company_details'").fetchone()[0],'pending')
        self.assertEqual(p.status()['estimated_credits_reserved'],11)
        self.transport.request.assert_not_called()

    def test_untrusted_cache_does_not_skip_provider_verification(self):
        p,token,_=self.approved()
        JsonCache(self.root/'cache',lambda:NOW).put(UsageTracker.key('OpenRegister','company_details',DIRECT_ID),
                                                  {'payload':self.raw,'retrieved_at':'2026-11-10T00:00:00+00:00'})
        self.assertEqual(p.verify_direct(token)['status'],'verified')
        self.transport.request.assert_called_once_with('company_details',DIRECT_ID)

    def test_conflicting_raw_register_fields_are_manual_review(self):
        p,token,_=self.approved();self.raw['company_register']={'register_number':'999','register_type':'HRB','register_court':'Braunschweig'}
        self.assertEqual(p.verify_direct(token)['status'],'manual_review')

    def test_http_requires_enable_and_separate_approval(self):
        p,token,_=self.approved()
        kwargs=dict(directory=self.root/'state',cache_dir=self.root/'cache',transport=self.transport,clock=lambda:NOW)
        for enabled in (False,True):
            with TestClient(create_app(enable_live_test=enabled,**kwargs),client=('127.0.0.1',1234)) as client:
                url='/v1/volkswagen/direct-detail/verify'
                self.assertEqual(client.post(url,json={}).status_code,403)
                self.assertEqual(client.post(url,json={'company_id':'override'},headers={'X-LEGALFLOW-Test-Approval':token}).status_code,422)
                response=client.post(url,json={},headers={'X-LEGALFLOW-Test-Approval':token})
                self.assertEqual(response.status_code,200 if enabled else 403)
        self.transport.request.assert_called_once_with('company_details',DIRECT_ID)
