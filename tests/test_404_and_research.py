"""Identity-focused public search queries; no network."""
from offline_support import OfflineTestCase
from unittest.mock import MagicMock,patch
from types import SimpleNamespace
import sys
from scripts import company_research as research

class ResearchTests(OfflineTestCase):
    def test_german_exact_identity_query(self):
        query = research.build_research_query('Descartes Technologies GmbH', 'Germany',
                                              registration_number='267645', register_court='Berlin (Charlottenburg)')
        for term in ('"Descartes Technologies GmbH"', '"267645"', '"Berlin (Charlottenburg)"', 'Germany'):
            self.assertIn(term, query)
        self.assertNotIn(' OR ', query)
        self.assertNotIn('DE-HRB-', query)

    def test_uk_query_registration_and_jurisdiction(self):
        query = research.build_research_query('Example Limited', 'UK', registration_number='01234567')
        self.assertIn('"Example Limited"', query)
        self.assertIn('"01234567"', query)
        self.assertIn('United Kingdom', query)

    def test_missing_name_rejected_and_quote_boundaries_cleaned(self):
        with self.assertRaises(ValueError):
            research.build_research_query('   ')
        query = research.build_research_query('Example "Limited"\n', registration_number='123"\n')
        self.assertEqual(query.count('"'), 6)
        self.assertNotIn('\n', query)

    @patch.object(research, 'API_KEY', 'test-secret')
    def test_one_mocked_search_no_additional_calls(self):
        client = MagicMock()
        client.search.return_value = {'results': []}
        with patch.dict(sys.modules, {'tavily': SimpleNamespace(TavilyClient=MagicMock(return_value=client))}):
            result = research.research_company('Example Limited', 'UK', registration_number='01234567')
        client.search.assert_called_once()
        call = client.search.call_args.kwargs
        self.assertEqual(call['max_results'], 5)
        self.assertIn('"01234567"', call['query'])
        self.assertEqual(result['query'], call['query'])
        self.assertIn('not a comprehensive', result['coverage_note'])


if __name__ == '__main__':
    unittest.main()
