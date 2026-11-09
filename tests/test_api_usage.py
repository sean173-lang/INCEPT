"""Cost protection tests use temporary caches and provider mocks only."""
import io
import json
import sys
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from offline_support import OfflineTestCase
from scripts.api_usage import UsageTracker, use_tracker, ApprovalRequired, BudgetExceeded, DuplicateRequestBlocked, UsageBlocked
from scripts import german_register as de, company_search, company_research, legalflow_agent as agent


class UsageTests(OfflineTestCase):
    def test_cache_hit_persistent_and_approval_not_needed(self):
        with tempfile.TemporaryDirectory() as directory:
            call = MagicMock(return_value={'company': 'fixture'})
            tracker = UsageTracker(approved=True, cache_dir=directory)
            first = tracker.execute('OpenRegister', 'company_search', 'fixture', call, cache=True)
            second = UsageTracker(cache_dir=directory)
            result = second.execute('OpenRegister', 'company_search', 'fixture', call, cache=True)
            self.assertEqual(result, first)
            call.assert_called_once()
            self.assertTrue(second.events[0]['cache_hit'])
            self.assertEqual(second.run_credits, 0)

    def test_cache_expiration_and_future_entry(self):
        now = [1000.0]
        tracker = UsageTracker(approved=True, cache_ttl=10, clock=lambda: now[0])
        call = MagicMock(return_value={'items': []})
        tracker.execute('OpenRegister', 'company_search', 'fixture', call, cache=True)
        now[0] = 1010
        tracker.new_run()
        tracker.execute('OpenRegister', 'company_search', 'fixture', call, cache=True)
        self.assertEqual(call.call_count, 2)
        now[0] = 500
        self.assertIsNone(tracker.cache.get(tracker.key('OpenRegister', 'company_search', 'fixture'), 10))

    def test_openregister_limit_cannot_be_overridden_by_approval(self):
        tracker = UsageTracker(approved=True, max_openregister_credits=10)
        call = MagicMock(return_value={})
        tracker.execute('OpenRegister', 'company_details', 'one', call)
        with self.assertRaises(BudgetExceeded):
            tracker.execute('OpenRegister', 'financials', 'two', call, approved=True)
        call.assert_called_once()
        self.assertEqual(tracker.run_credits, 10)

    def test_tavily_limit(self):
        tracker = UsageTracker(approved=True, max_tavily_searches=1)
        call = MagicMock(return_value={})
        tracker.execute('Tavily', 'search_basic', 'one', call)
        with self.assertRaises(BudgetExceeded):
            tracker.execute('Tavily', 'search_basic', 'two', call)
        call.assert_called_once()

    def test_session_spending_survives_new_run(self):
        tracker = UsageTracker(approved=True, max_session_spend='0.2', prices={('OpenRegister', 'company_details'): '0.15'})
        call = MagicMock(return_value={})
        tracker.execute('OpenRegister', 'company_details', 'one', call)
        tracker.new_run()
        with self.assertRaises(BudgetExceeded):
            tracker.execute('OpenRegister', 'company_details', 'two', call)
        call.assert_called_once()
        self.assertEqual(str(tracker.spend), '0.15')

    def test_unknown_price_fails_closed_with_cap(self):
        tracker = UsageTracker(approved=True, max_session_spend='100')
        call = MagicMock()
        with self.assertRaisesRegex(BudgetExceeded, 'Cost unknown'):
            tracker.execute('OpenAI', 'legal_analysis', 'one', call)
        call.assert_not_called()
        tracker = UsageTracker(approved=True)
        tracker.execute('Tavily', 'search_basic', 'one', lambda: {})
        reservation = tracker.events[0]
        self.assertEqual(reservation['cost_display'], 'Cost unknown')
        self.assertIsNone(reservation['estimated_cost'])
        self.assertFalse(reservation['billing_confirmed'])
        self.assertIsNone(tracker.summary()['session_spending_estimated'])
        self.assertEqual(tracker.summary()['cost_display'], 'Cost unknown')

    def test_approval_blocked_before_execution(self):
        call = MagicMock()
        with self.assertRaises(ApprovalRequired):
            UsageTracker().execute('OpenRegister', 'company_details', 'id', call)
        call.assert_not_called()

    def test_failure_reserved_once_and_duplicate_blocked(self):
        tracker = UsageTracker(approved=True)
        call = MagicMock(side_effect=RuntimeError('secret token'))
        with self.assertRaises(RuntimeError):
            tracker.execute('OpenRegister', 'financials', 'id', call)
        with self.assertRaises(DuplicateRequestBlocked):
            tracker.execute('OpenRegister', 'financials', 'id', call)
        self.assertEqual(tracker.run_credits, 10)
        call.assert_called_once()
        self.assertNotIn('secret', json.dumps(tracker.events))
        self.assertEqual(tracker.events[1]['outcome'], 'failure')

    def test_returned_failure_not_cached_or_reissued(self):
        tracker = UsageTracker(approved=True)
        call = MagicMock(return_value={'request_status': 'failed'})
        tracker.execute('OpenRegister', 'financials', 'id', call, success=lambda v: False, cache=True)
        with self.assertRaises(DuplicateRequestBlocked):
            tracker.execute('OpenRegister', 'financials', 'id', call, cache=True)
        call.assert_called_once()

    def test_concurrent_duplicate_success_only_one_call(self):
        tracker = UsageTracker(approved=True)
        call = MagicMock(return_value={'ok': True})
        results = []
        def run():
            results.append(tracker.execute('OpenRegister', 'company_details', 'id', call, cache=True))
        threads = [threading.Thread(target=run) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 5)
        call.assert_called_once()

    def test_ledger_contains_only_safe_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'usage.jsonl'
            tracker = UsageTracker(approved=True, ledger_path=path)
            tracker.execute('OpenRegister', 'company_search', {'Authorization': 'secret', 'query': 'sensitive'}, lambda: {'token': 'secret'})
            raw = path.read_text()
            self.assertNotIn('secret', raw)
            self.assertNotIn('sensitive', raw)
            event = json.loads(raw.splitlines()[0])
            for field in ('provider', 'operation', 'timestamp', 'estimated_credits', 'estimated_cost', 'cache_hit', 'outcome', 'session_id'):
                self.assertIn(field, event)
            self.assertEqual(event['estimated_credits'], 1)

    def test_invalid_configuration(self):
        for settings in ({'max_openregister_credits': -1}, {'max_tavily_searches': 1.5}, {'max_session_spend': 'NaN'}, {'cache_ttl': 0}):
            with self.assertRaises(ValueError):
                UsageTracker(**settings)

    def test_expired_cache_does_not_silently_repeat_paid_request_in_run(self):
        now = [0]
        tracker = UsageTracker(approved=True, cache_ttl=1, clock=lambda: now[0])
        call = MagicMock(return_value={})
        tracker.execute('OpenRegister', 'company_search', 'id', call, cache=True)
        now[0] = 2
        with self.assertRaises(DuplicateRequestBlocked):
            tracker.execute('OpenRegister', 'company_search', 'id', call, cache=True)
        call.assert_called_once()

    def test_cache_hit_after_budget_exhausted_costs_nothing(self):
        tracker = UsageTracker(approved=True, max_openregister_credits=1)
        call = MagicMock(return_value={})
        tracker.execute('OpenRegister', 'company_search', 'id', call, cache=True)
        tracker.execute('OpenRegister', 'company_search', 'id', call, cache=True)
        call.assert_called_once()
        self.assertEqual(tracker.run_credits, 1)


class IntegrationUsageTests(OfflineTestCase):
    @patch.object(de, 'get_client')
    def test_company_details_cache_prevents_second_sdk_call(self, factory):
        factory.return_value.company.get_details_v1.return_value.model_dump.return_value = {'id': 'fixture'}
        tracker = UsageTracker(approved=True)
        with use_tracker(tracker):
            self.assertEqual(de.get_company('fixture').model_dump()['id'], 'fixture')
            self.assertEqual(de.get_company('fixture').model_dump()['id'], 'fixture')
        factory.assert_called_once()
        self.assertEqual(tracker.run_credits, 10)

    def test_company_search_cache(self):
        sdk = MagicMock()
        sdk.search.autocomplete_companies_v1.return_value.results = [{'company_id': 'fixture'}]
        with patch.dict(sys.modules, {'openregister': SimpleNamespace(Openregister=MagicMock(return_value=sdk))}), patch.dict('os.environ', {'OPENREGISTER_API_KEY': 'fixture'}):
            self.assertEqual(company_search.search_companies('Demo'), company_search.search_companies('Demo'))
        sdk.search.autocomplete_companies_v1.assert_called_once_with(query='Demo')

    @patch.object(company_research, 'API_KEY', 'fixture')
    def test_tavily_cache(self):
        sdk = MagicMock()
        sdk.search.return_value = {'results': []}
        with patch.dict(sys.modules, {'tavily': SimpleNamespace(TavilyClient=MagicMock(return_value=sdk))}):
            company_research.research_company('Demo', 'Germany', registration_number='123')
            company_research.research_company('Demo', 'Germany', registration_number='123')
        sdk.search.assert_called_once()

    def test_financial_cache_preserved_without_approval_or_credits(self):
        from scripts.financial_cache import save_financials
        save_financials('fixture', {'company_id': 'fixture', 'request_status': 'succeeded', 'raw': {'indicators': []}})
        tracker = UsageTracker(max_openregister_credits=0)
        with use_tracker(tracker), patch.object(de, '_get_financials') as call:
            result = de.get_financials('fixture')
        call.assert_not_called()
        self.assertTrue(result['cache_hit'])
        self.assertEqual(tracker.run_credits, 0)
        self.assertTrue(tracker.events[0]['cache_hit'])

    @patch.object(de, '_get_financials', return_value={'request_status': 'failed'})
    def test_financial_budget_check_precedes_adapter(self, call):
        with use_tracker(UsageTracker(max_openregister_credits=0)):
            with self.assertRaises(BudgetExceeded):
                de.get_financials('uncached', allow_paid=True)
        call.assert_not_called()

    @patch.object(de, 'API_KEY', 'fixture')
    def test_financial_fresh_result_still_uses_existing_cache(self):
        response = MagicMock(status_code=200)
        response.json.return_value = {'indicators': [], 'reports': []}
        tracker = UsageTracker(max_openregister_credits=10)
        with use_tracker(tracker), patch.dict(sys.modules, {'openregister': None}), patch('requests.get', return_value=response) as request, redirect_stdout(io.StringIO()):
            de.get_financials('fixture', allow_paid=True)
            result = de.get_financials('fixture', allow_paid=True)
        request.assert_called_once()
        self.assertTrue(result['cache_hit'])
        self.assertEqual(tracker.run_credits, 10)

    def test_development_all_integrations_do_not_touch_network(self):
        tracker = UsageTracker(development=True, max_openregister_credits=0, max_tavily_searches=0, max_session_spend=0)
        with use_tracker(tracker), patch('requests.sessions.Session.request', side_effect=AssertionError('Network forbidden')), patch.object(de, 'get_client', side_effect=AssertionError('SDK forbidden')), patch.object(agent, 'OpenAI', side_effect=AssertionError('Model forbidden')):
            self.assertTrue(company_search.search_companies('Demo'))
            data = agent.get_german_company('DEMO', financials=True)
            research = company_research.research_company('Demo')
            report = agent.generate_ai_report(data, research)
            self.assertIn('DEVELOPMENT MODE', report)
            self.assertIn('synthetic data', report)
            self.assertEqual(tracker.run_credits, 0)
            self.assertEqual(tracker.run_searches, 0)
            self.assertEqual(tracker.summary()['unknown_cost_reservations'], 0)
            with self.assertRaises(UsageBlocked):
                tracker.execute('Other', 'unknown', 'id', lambda: self.fail('Must not execute'))


if __name__ == '__main__':
    unittest.main()
