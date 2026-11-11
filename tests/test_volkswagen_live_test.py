"""All Volkswagen provider data below is mocked, not real retrieved evidence."""
import concurrent.futures
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.api_usage import JsonCache, UsageTracker
from scripts.volkswagen_profile import (CONFIG, VolkswagenProfile, RegisterTransport, ProfileError,
                                         load_policy, reduce_identity, matches_target)
from scripts.volkswagen_live_test import create_app, ACKNOWLEDGEMENT

NOW=datetime(2026,11,10,tzinfo=timezone.utc).timestamp()
IDENTIFIER='MOCK-VW-IDENTITY'
RAW={'id':IDENTIFIER,'name':{'name':'Volkswagen Aktiengesellschaft'},
     'register':{'register_number':'100484','register_type':'HRB','register_court':'Braunschweig','company_id':IDENTIFIER},
     'address':{'country':'DE'},'representation':[{'name':'Private person must not persist'}]}
CANDIDATE={'company_id':IDENTIFIER,'name':'Volkswagen AG','country':'DE','register_number':'100484',
           'register_type':'HRB','register_court':'Amtsgericht Braunschweig'}
IDENTITY=reduce_identity(RAW,details=True)
SEARCH_IDENTITY=reduce_identity(CANDIDATE)


class VolkswagenTests(OfflineTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.now=[NOW]
        self.transport=MagicMock()
        self.transport.request.side_effect=lambda op,provider_id=None: [dict(SEARCH_IDENTITY)] if op=='company_search' else dict(IDENTITY)

    def profile(self,**kwargs):
        return VolkswagenProfile(directory=self.root/'state',cache_dir=self.root/'cache',transport=self.transport,
                                  clock=lambda:self.now[0],**kwargs)

    def approved(self):
        profile=self.profile();profile.approve(ACKNOWLEDGEMENT)
        return profile,profile.grant_file.read_text()

    def test_unapproved_and_wrong_scope_no_requests(self):
        profile=self.profile()
        for token in (None,'wrong'):
            with self.assertRaises(ProfileError):profile.verify(token)
        with self.assertRaises(ProfileError):profile.approve('Any company, any budget')
        self.transport.request.assert_not_called()

    def test_two_calls_11_credits_and_provenance(self):
        profile,nonce=self.approved();result=profile.verify(nonce)
        self.assertEqual(result['status'],'verified')
        self.assertEqual(result['company']['provider_company_id'],IDENTIFIER)
        self.assertFalse(result['development']);self.assertFalse(result['synthetic'])
        self.assertEqual(result['credit_usage']['estimated_credits_reserved'],11)
        self.assertEqual(result['credit_usage']['state'],'completed')
        self.assertEqual(profile.status()['estimated_credits_reserved'],11)
        self.assertEqual([c.args[0] for c in self.transport.request.call_args_list],['company_search','company_details'])
        self.assertTrue(all(e['retrieved_at'] for e in result['evidence']))
        self.assertTrue(all(not e['cache_hit'] for e in result['evidence']))
        self.assertEqual(profile.status()['money_cost'],'Cost unknown')
        with profile.transaction() as db:
            text=' '.join(row[0] or '' for row in db.execute('SELECT evidence FROM operations'))
        self.assertNotIn('Private person',text)

    def test_restart_replay_and_reapproval_do_not_duplicate(self):
        profile,nonce=self.approved();first=profile.verify(nonce)
        second=self.profile();self.assertEqual(second.verify(nonce),first)
        self.assertEqual(self.transport.request.call_count,2)
        self.assertEqual(second.status()['estimated_credits_reserved'],11)
        with self.assertRaises(ProfileError):second.approve(ACKNOWLEDGEMENT)

    def test_concurrent_same_test_only_one_search_and_details(self):
        profile,nonce=self.approved()
        def run(_):
            try:return self.profile().verify(nonce)['status']
            except ProfileError as error:return error.code
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            results=list(pool.map(run,range(4)))
        self.assertIn('verified',results)
        self.assertEqual(self.transport.request.call_count,2)
        self.assertEqual(profile.status()['estimated_credits_reserved'],11)

    def test_hard_process_exit_keeps_pending_reservation(self):
        profile,nonce=self.approved()
        program = """
import os,sys
from pathlib import Path
from scripts.volkswagen_profile import VolkswagenProfile
class OfflineCrashTransport:
 def preflight(self): return True
 def request(self,operation,provider_id=None):
  Path(sys.argv[1]).joinpath('request.marker').write_text(operation)
  os._exit(71)
p=VolkswagenProfile(directory=Path(sys.argv[1])/'state',cache_dir=Path(sys.argv[1])/'cache',transport=OfflineCrashTransport(),clock=lambda:float(sys.argv[2]))
p.verify(p.grant_file.read_text())
"""
        result=subprocess.run([sys.executable,'-c',program,str(self.root),str(NOW)],capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,71)
        with self.assertRaises(ProfileError):self.profile().verify(nonce)
        self.assertEqual(profile.status()['estimated_credits_reserved'],1)
        self.assertEqual(profile.status()['operations'][0]['state'],'pending')
        self.transport.request.assert_not_called()

    def test_timeout_reserved_and_never_retried_after_restart(self):
        profile,nonce=self.approved()
        self.transport.request.side_effect=ProfileError('provider_timeout','safe timeout',504)
        first=profile.verify(nonce)
        self.assertEqual(first['status'],'verification_failed')
        self.assertEqual(self.profile().verify(nonce),first)
        self.transport.request.assert_called_once()
        self.assertEqual(profile.status()['estimated_credits_reserved'],1)
        self.assertEqual(profile.status()['operations'][0]['state'],'failed_or_uncertain')

    def test_crash_between_reservation_and_request_blocks_restart(self):
        profile,nonce=self.approved()
        self.transport.request.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):profile.verify(nonce)
        with self.assertRaises(ProfileError) as context:self.profile().verify(nonce)
        self.assertEqual(context.exception.code,'test_pending_or_uncertain')
        self.transport.request.assert_called_once()
        self.assertEqual(profile.status()['estimated_credits_reserved'],1)

    def test_direct_requests_and_other_operations_forbidden(self):
        profile=self.profile()
        for operation in ('financials','tavily','openai','research','company_search','company_details'):
            with self.assertRaises(ProfileError):profile.request_once(operation,IDENTIFIER)
        self.transport.request.assert_not_called()

    def test_second_details_and_budget_over_15_are_blocked(self):
        profile,nonce=self.approved()
        with profile.transaction() as db:
            db.execute('INSERT INTO test(id,status,started_at,selected_id) VALUES(1,?,?,?)',('running','fixture',IDENTIFIER))
            db.execute('INSERT INTO operations(name,credits,state,requested_at) VALUES(?,?,?,?)',('reserved-fixture',6,'pending','fixture'))
        with self.assertRaises(ProfileError) as context:profile.request_once('company_details',IDENTIFIER)
        self.assertEqual(context.exception.code,'credit_limit_exceeded')
        self.transport.request.assert_not_called()

    def test_selected_id_cannot_be_overridden(self):
        profile,nonce=self.approved()
        with profile.transaction() as db:
            db.execute('INSERT INTO test(id,status,started_at,selected_id) VALUES(1,?,?,?)',('running','fixture',IDENTIFIER))
        with self.assertRaises(ProfileError):profile.request_once('company_details','ANOTHER-COMPANY')
        self.transport.request.assert_not_called()

    def test_expired_approval_does_not_call_provider(self):
        profile,nonce=self.approved();self.now[0]+=3601
        with self.assertRaises(ProfileError) as context:profile.verify(nonce)
        self.assertEqual(context.exception.code,'approval_expired')
        self.transport.request.assert_not_called()

    def test_ambiguous_and_wrong_register_search_stop_without_details(self):
        for rows,expected in (([{**SEARCH_IDENTITY,'provider_company_id':'MOCK-A'}, {**SEARCH_IDENTITY,'provider_company_id':'MOCK-B'}],'ambiguous'),
                              ([{**SEARCH_IDENTITY,'register_court':'Berlin'}],'not_found')):
            with tempfile.TemporaryDirectory() as directory:
                profile=VolkswagenProfile(directory=directory,cache_dir=Path(directory)/'cache',transport=self.transport,clock=lambda:NOW)
                profile.approve(ACKNOWLEDGEMENT);self.transport.request.reset_mock()
                self.transport.request.side_effect=lambda op,provider_id=None:rows
                self.assertEqual(profile.verify(profile.grant_file.read_text())['status'],expected)
                self.transport.request.assert_called_once()

    def test_details_mismatch_fails_closed(self):
        profile,nonce=self.approved()
        self.transport.request.side_effect=lambda op,provider_id=None:[SEARCH_IDENTITY] if op=='company_search' else {**IDENTITY,'register_number':'123'}
        self.assertEqual(profile.verify(nonce)['status'],'verification_failed')
        self.assertEqual(profile.status()['estimated_credits_reserved'],11)

    def test_legacy_and_current_detail_schema(self):
        legacy=copy.deepcopy(RAW);legacy['company_register']=legacy.pop('register')
        self.assertEqual(reduce_identity(legacy,details=True),IDENTITY)
        conflicting=copy.deepcopy(RAW);conflicting['company_register']={**RAW['register'],'register_court':'Berlin'}
        with self.assertRaises(ProfileError):reduce_identity(conflicting,details=True)
        bad=copy.deepcopy(RAW);bad['register']['company_id']='WRONG'
        with self.assertRaises(ProfileError):reduce_identity(bad,details=True)

    def test_full_identity_and_explicit_name_alias_required(self):
        policy=load_policy(now=NOW)
        self.assertTrue(matches_target(IDENTITY,policy))
        for change in ({'name':'Volkswagen Group'}, {'register_court':'Berlin'},{'register_number':'100485'},
                       {'register_type':'HRA'}, {'register_number':'HRA 100484'}, {'country':'GB'}):
            self.assertFalse(matches_target({**IDENTITY,**change},policy))

    def cache_detail(self,**changes):
        profile=self.profile()
        raw=copy.deepcopy(RAW);raw.update(changes.pop('raw',{}))
        payload={'payload':raw,'retrieved_at':datetime.fromtimestamp(self.now[0],timezone.utc).isoformat(),
                 'provenance':{'provider':'OpenRegister','mode':'live','origin':'provider_response'},**changes}
        JsonCache(self.root/'cache',lambda:self.now[0]).put(UsageTracker.key('OpenRegister','company_details',IDENTIFIER),payload)
        return profile

    def test_preview_is_cache_only_and_requires_no_approval(self):
        profile=self.profile()
        self.assertEqual(profile.preview()['estimated_new_credits'],11)
        profile=self.cache_detail()
        self.assertEqual(profile.preview()['estimated_new_credits'],0)
        self.transport.request.assert_not_called()

    def test_attested_detail_cache_zero_requests(self):
        profile=self.cache_detail();profile.approve(ACKNOWLEDGEMENT)
        result=profile.verify(profile.grant_file.read_text())
        self.assertEqual(result['status'],'verified')
        self.assertTrue(result['evidence'][0]['cache_hit'])
        self.assertEqual(result['credit_usage']['estimated_credits_reserved'],0)
        self.transport.request.assert_not_called()

    def test_unattested_synthetic_stale_and_wrong_identity_cache_not_promoted(self):
        cases=[{'provenance':{}},{'provenance':{'provider':'OpenRegister','mode':'development','origin':'fixture'}},
               {'retrieved_at':'2020-01-01T00:00:00+00:00'}, {'raw':{'name':{'name':'Other AG'}}}, {'raw':{'development':True}}]
        for change in cases:
            profile=self.cache_detail(**change)
            detail,search=profile.existing_cache()
            self.assertIsNone(detail)
        self.transport.request.assert_not_called()

    def test_attested_search_cache_uses_only_one_detail_call(self):
        profile=self.profile()
        entry={'results':[CANDIDATE],'provenance':{'provider':'OpenRegister','mode':'live','origin':'provider_response',
                                                'retrieved_at':datetime.fromtimestamp(NOW,timezone.utc).isoformat()}}
        JsonCache(self.root/'cache',lambda:NOW).put(UsageTracker.key('OpenRegister','company_search','Volkswagen AG'),entry)
        profile.approve(ACKNOWLEDGEMENT);result=profile.verify(profile.grant_file.read_text())
        self.assertEqual(result['status'],'verified');self.assertEqual(result['credit_usage']['estimated_credits_reserved'],10)
        self.transport.request.assert_called_once_with('company_details',IDENTIFIER)
        self.assertTrue(result['evidence'][0]['retrieved_at'])

    def test_pricing_missing_expired_inconsistent_and_future_fail_closed(self):
        base=json.loads(CONFIG.read_text())
        cases=[None, [], {'pricing':None}]
        item=copy.deepcopy(base);item['pricing']['company_details']=None;cases.append(item)
        for key,value in (('verified_on','2027-01-01'),('valid_until','2026-11-09')):
            item=copy.deepcopy(base);item['pricing'][key]=value;cases.append(item)
        for value in (None,20,True):
            item=copy.deepcopy(base);item['pricing']['company_details']['credits']=value;cases.append(item)
        item=copy.deepcopy(base);item['max_credits']=100;cases.append(item)
        item=copy.deepcopy(base);item['realtime']=True;cases.append(item)
        for item in cases:
            path=self.root/'policy.json';path.write_text(json.dumps(item))
            with self.assertRaises(ProfileError):load_policy(path,NOW)
        self.transport.request.assert_not_called()

    def test_policy_change_does_not_reset_ledger(self):
        profile,nonce=self.approved();profile.verify(nonce)
        changed=json.loads(CONFIG.read_text());changed['pricing']['valid_until']='2026-11-16'
        path=self.root/'changed.json';path.write_text(json.dumps(changed))
        with self.assertRaises(ProfileError) as context:self.profile(config=path)
        self.assertEqual(context.exception.code,'policy_changed')
        self.assertEqual(profile.status()['estimated_credits_reserved'],11)

    def test_http_opt_in_auth_and_closed_surface(self):
        for enabled in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                app=create_app(enable_live_test=enabled,directory=directory,cache_dir=Path(directory)/'cache',transport=self.transport,clock=lambda:NOW)
                app.state.profile.approve(ACKNOWLEDGEMENT)
                nonce=app.state.profile.grant_file.read_text()
                with TestClient(app,client=('127.0.0.1',50000)) as client:
                    response=client.post('/v1/volkswagen/verify',json={})
                    self.assertEqual(response.status_code,403)
                    response=client.post('/v1/volkswagen/verify',json={},headers={'X-LEGALFLOW-Test-Approval':nonce})
                    self.assertEqual(response.status_code,200 if enabled else 403)
                    for endpoint in ('/v1/financials','/v1/research/runs','/v1/research/search','/v1/company/search'):
                        self.assertEqual(client.post(endpoint,json={}).status_code,404)
                    override=client.post('/v1/volkswagen/verify',json={'company_name':'Other AG','credits':100,'secret':'do-not-echo'})
                    self.assertEqual(override.status_code,422);self.assertNotIn('do-not-echo',override.text)

    def test_nonloopback_client_rejected(self):
        app=create_app(directory=self.root/'state',transport=self.transport,clock=lambda:NOW)
        with TestClient(app,client=('203.0.113.1',50000)) as client:
            self.assertEqual(client.get('/health').status_code,403)
        self.transport.request.assert_not_called()

    @patch.dict(os.environ,{'OPENREGISTER_API_KEY':'mock-secret'})
    @patch('scripts.volkswagen_profile.requests.Session')
    def test_transport_exact_routes_auth_no_redirects_or_retries(self,factory):
        session=factory.return_value.__enter__.return_value
        response=session.get.return_value;response.status_code=200;response.json.return_value={'results':[CANDIDATE]}
        result=RegisterTransport().request('company_search')
        self.assertEqual(result[0]['provider_company_id'],IDENTIFIER)
        self.assertEqual(session.get.call_args.args[0],'https://api.openregister.de/v1/autocomplete/company')
        self.assertEqual(session.get.call_args.kwargs['params'],{'query':'Volkswagen AG'})
        self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        self.assertEqual(session.mount.call_args.args[1].max_retries.total,0)
        response.json.return_value=RAW
        RegisterTransport().request('company_details',IDENTIFIER)
        self.assertEqual(session.get.call_args.kwargs['params'],{'realtime':'false'})
        with self.assertRaises(ProfileError):RegisterTransport().request('financials',IDENTIFIER)

    @patch.dict(os.environ,{'OPENREGISTER_API_KEY':'mock-secret'})
    @patch('scripts.volkswagen_profile.requests.Session')
    def test_transport_errors_do_not_expose_secrets_or_retry(self,factory):
        session=factory.return_value.__enter__.return_value
        for status in (401,403,404,429,500,302):
            session.get.reset_mock();session.get.return_value.status_code=status
            session.get.return_value.json.return_value={'message':'mock-secret sensitive-body'}
            with self.assertRaises(ProfileError) as context:RegisterTransport().request('company_search')
            self.assertNotIn('mock-secret',context.exception.message)
            self.assertNotIn('sensitive-body',context.exception.message)
            session.get.assert_called_once()
