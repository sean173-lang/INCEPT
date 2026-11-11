"""Synthetic financials only; all networking disabled by OfflineTestCase."""
from contextlib import closing
import concurrent.futures
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import MagicMock, patch
from offline_support import OfflineTestCase
from scripts.volkswagen_financial_test import FinancialTest, FinancialTransport, ACK, DIRECT_ID, SOURCE, validate_raw
from scripts.volkswagen_profile import ProfileError
from test_volkswagen_live_test import NOW


def raw():
    return {'currency':'EUR','scale':1,'reports':[{'report_id':str(y),'consolidated':True,'report_start_date':f'{y}-01-01','report_end_date':f'{y}-12-31','sources':[{'html_url':'https://example.org/mock-accounts'}]} for y in (2023,2024)],
            'indicators':[{'report_id':str(y),'date':f'{y}-12-31','revenue':v,'net_income':10,'equity':50,'balance_sheet_total':200} for y,v in ((2023,100),(2024,120))]}


class FinancialProfileTests(OfflineTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.identity=self.root/'identity.sqlite3';self.now=NOW
        self.identity_result={'status':'verified','synthetic':False,'development':False,
            'company':{'provider_company_id':DIRECT_ID,'name':'Volkswagen AG','country':'DE','register_court':'Braunschweig','register_type':'HRB','register_number':'100484'},
            'evidence':[{'provider':'OpenRegister','origin':'live_provider_response','retrieved_at':'2026-11-10T00:00:00+00:00'}]}
        with closing(sqlite3.connect(self.identity)) as db:
            db.execute('CREATE TABLE continuation(id INTEGER,result TEXT)');db.execute('INSERT INTO continuation VALUES(1,?)',(json.dumps(self.identity_result),));db.commit()
        self.original=self.identity.read_bytes();self.transport=MagicMock();self.transport.request.return_value=raw()

    def profile(self):
        return FinancialTest(directory=self.root/'financial-test',identity_db=self.identity,cache_dir=self.root/'cache',usage_cache_dir=self.root/'usage',transport=self.transport,clock=lambda:self.now)

    def approved(self):
        p=self.profile();p.approve(ACK);return p,p.grant.read_text()

    def test_no_approval_or_wrong_approval(self):
        p=self.profile()
        with self.assertRaises(ProfileError):p.run(None)
        with self.assertRaises(ProfileError):p.approve('identity approval')
        self.transport.request.assert_not_called()

    def test_verified_identity_required_read_only(self):
        p=self.profile();self.assertFalse(p.preview()['cache_reusable'])
        self.assertEqual(self.identity.read_bytes(),self.original)
        with closing(sqlite3.connect(self.identity)) as db:db.execute("UPDATE continuation SET result='{}'");db.commit()
        with self.assertRaises(ProfileError):p.approve(ACK)
        self.transport.request.assert_not_called()

    def test_real_figures_ratios_comparisons_and_report(self):
        p,nonce=self.approved();result=p.run(nonce)
        self.assertEqual(result['status'],'completed');self.assertEqual(result['credit_usage']['estimated_credits_reserved'],10)
        self.assertEqual(result['analysis']['periods'][0]['ratios']['equity_ratio']['value'],'0.25')
        self.assertEqual(result['analysis']['comparisons'][0]['changes']['revenue']['percent_change'],'20.0')
        report=(p.directory/'report.md').read_text()
        for value in ('2023','2024','EUR',SOURCE,'Undetermined','Missing currency'):self.assertIn(value,report)
        self.assertEqual(self.profile().run(nonce),result);self.transport.request.assert_called_once_with()
        self.assertEqual(self.identity.read_bytes(),self.original)
        with self.assertRaises(ProfileError):p.approve(ACK)

    def test_cache_reuse_zero_credits(self):
        p,nonce=self.approved();p.run(nonce)
        other=FinancialTest(directory=self.root/'independent-test',identity_db=self.identity,cache_dir=self.root/'cache',usage_cache_dir=self.root/'usage',transport=self.transport,clock=lambda:self.now)
        self.assertTrue(other.preview()['cache_reusable']);other.approve(ACK)
        result=other.run(other.grant.read_text());self.assertTrue(result['financial_data']['cache_hit'])
        self.assertEqual(result['credit_usage']['estimated_credits_reserved'],0);self.transport.request.assert_called_once()

    def test_untrusted_cache_not_reused(self):
        p=self.profile();p.cache_dir.mkdir()
        (p.cache_dir/(DIRECT_ID+'.json')).write_text(json.dumps({'result':{'raw':raw(),'company_id':DIRECT_ID}}))
        self.assertIsNone(p.cache());self.transport.request.assert_not_called()

    def test_missing_figures_and_units_never_invented(self):
        for payload in ({'reports':[],'indicators':[]}, {'reports':[],'indicators':[{'date':'2024-12-31','revenue':100}]}):
            self.root=self.root/'case';self.root.mkdir();self.transport.request.return_value=payload
            # Preserve independent verified read-only identity path.
            p,nonce=self.approved();result=p.run(nonce)
            self.assertEqual(result['status'],'completed')
            for period in result['analysis']['periods']:
                self.assertIsNone(period['ratios']['net_margin']['value'])
                self.assertEqual(period['facts']['equity']['availability'],'unavailable')

    def test_malformed_payloads_fail_closed_and_do_not_retry(self):
        for payload in ([],{'error':'bad'}, {'reports':[None]}, {'indicators':[{'revenue':'invented'}]}, {'reports':[],'company_id':'OTHER'}):
            self.root=self.root/'case';self.root.mkdir();self.transport.request.return_value=payload
            p,nonce=self.approved();result=p.run(nonce)
            self.assertEqual(result['status'],'manual_review');self.assertEqual(result['credit_usage']['estimated_credits_reserved'],10)
            self.assertEqual(p.run(nonce),result)

    def test_expired_approval_and_pricing(self):
        p,nonce=self.approved();self.now+=3601
        with self.assertRaises(ProfileError):p.run(nonce)
        self.now+=86400*20
        with self.assertRaises(ProfileError):p.approve(ACK)
        self.transport.request.assert_not_called()

    def test_concurrency_and_budget_persist_across_restart(self):
        p,nonce=self.approved()
        def run(_):
            try:return self.profile().run(nonce)['status']
            except ProfileError:return 'blocked'
        with concurrent.futures.ThreadPoolExecutor(4) as pool:results=list(pool.map(run,range(4)))
        self.assertIn('completed',results);self.transport.request.assert_called_once()
        self.assertEqual(self.profile().status()['estimated_credits_reserved'],10)

    def test_crash_reservation_blocks_restart(self):
        p,nonce=self.approved();self.transport.request.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):p.run(nonce)
        with self.assertRaises(ProfileError):self.profile().run(nonce)
        with self.assertRaises(ProfileError):self.profile().approve(ACK)
        self.assertEqual(p.status()['estimated_credits_reserved'],10)

    def test_timeout_safe_no_retry(self):
        p,nonce=self.approved();self.transport.request.side_effect=TimeoutError('secret')
        result=p.run(nonce);self.assertEqual(result['status'],'manual_review');self.assertNotIn('secret',json.dumps(result))
        self.assertEqual(p.run(nonce),result);self.transport.request.assert_called_once()

    @patch('scripts.volkswagen_financial_test.requests.Session')
    def test_fixed_transport_no_retries_redirects_or_proxy(self,factory):
        session=factory.return_value.__enter__.return_value;session.get.return_value.status_code=200;session.get.return_value.json.return_value=raw()
        with patch.object(FinancialTransport,'preflight',return_value='private-key'):
            FinancialTransport().request()
        self.assertFalse(session.trust_env);session.get.assert_called_once()
        self.assertEqual(session.get.call_args.args,(SOURCE,));self.assertFalse(session.get.call_args.kwargs['allow_redirects'])
        self.assertEqual(session.mount.call_args.args[1].max_retries.total,0)
