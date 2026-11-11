"""Tavily SDK, parsing and provenance regressions; never contact providers."""
from datetime import datetime
from unittest.mock import MagicMock,patch
from offline_support import OfflineTestCase
from scripts import company_research
from scripts.api_usage import UsageTracker,use_tracker,DuplicateRequestBlocked,BudgetExceeded

class TavilyAdapterTests(OfflineTestCase):
    def invoke(self,response):
        client=MagicMock();client.search.return_value=response
        tracker=UsageTracker(approved=True,max_tavily_searches=1,cache_dir=None,ledger_path=None)
        with use_tracker(tracker),patch.object(company_research,'API_KEY','synthetic-test-key'),patch('tavily.TavilyClient',return_value=client) as factory:
            result=company_research.research_company('TESCO PLC','UK',registration_number='00445790',max_results=3)
        return result,client,factory

    def test_bounded_search_timeout_no_retry_and_source_dates(self):
        rows=[{'title':'TESCO PLC public information','url':'https://example.invalid/tesco','content':'TESCO PLC company 00445790 public record','published_date':'2026-10-01'}]*4
        result,client,factory=self.invoke({'results':rows,'usage':{'credits':1}})
        args=client.search.call_args.kwargs
        self.assertEqual(args['max_results'],3);self.assertEqual(args['search_depth'],'basic');self.assertEqual(args['timeout'],20)
        self.assertFalse(args['auto_parameters']);self.assertFalse(args['include_answer'])
        self.assertEqual(len(result['sources']),3);self.assertEqual(result['sources'][0]['published_date'],'2026-10-01')
        self.assertEqual(result['sources'][0]['retrieved_at'],result['retrieved_at']);self.assertIsNotNone(datetime.fromisoformat(result['retrieved_at']).tzinfo)
        session=factory.call_args.kwargs['session'];self.assertEqual(session.max_redirects,0);self.assertEqual(session.get_adapter('https://').max_retries.total,0)
        self.assertFalse(result['billing_confirmed']);self.assertEqual(result['usage'],{'credits':1})

    def test_unsafe_urls_are_not_published(self):
        for url in ['https://user:password@example.invalid/','javascript:alert(1)','https://example.invalid/?token=placeholder']:
            result,_,_=self.invoke({'results':[{'url':url}]});self.assertIsNone(result['sources'][0]['url'])

    def test_malformed_response_rejected(self):
        for response in [{}, {'results':{}},{'results':['not an object']}]:
            with self.assertRaises(ValueError):self.invoke(response)

    def test_invalid_limits_never_initialize_sdk(self):
        with patch('tavily.TavilyClient') as sdk:
            for limit in (0,6,True,3.5):
                with self.assertRaises(ValueError):company_research.research_company('TESCO PLC',max_results=limit)
            sdk.assert_not_called()

    def test_network_failure_no_retry_or_duplicate_paid_call(self):
        tracker=UsageTracker(approved=True,max_tavily_searches=1)
        sdk=MagicMock();sdk.search.side_effect=TimeoutError('sensitive exception text')
        with use_tracker(tracker),patch.object(company_research,'API_KEY','synthetic-test-key'),patch('tavily.TavilyClient',return_value=sdk):
            with self.assertRaises(TimeoutError):company_research.research_company('TESCO PLC',max_results=3)
            with self.assertRaises(DuplicateRequestBlocked):company_research.research_company('TESCO PLC',max_results=3)
        sdk.search.assert_called_once();self.assertNotIn('sensitive',str(tracker.events))

    def test_unknown_price_with_zero_spend_cap_blocks_sdk(self):
        with use_tracker(UsageTracker(approved=True,max_tavily_searches=1,max_session_spend=0)),patch('tavily.TavilyClient') as sdk:
            with self.assertRaises(BudgetExceeded):company_research.research_company('TESCO PLC',max_results=3)
            sdk.assert_not_called()
