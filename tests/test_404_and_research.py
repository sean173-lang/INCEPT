"""Offline error-body interpretation and exact-identity Tavily regression tests."""
import io
import sys
import unittest
from offline_support import OfflineTestCase
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.financial_errors import classify_financial_404
from scripts import german_register as de, company_research as research
from scripts.financial_analysis import analyze_financials
from scripts.report_renderer import financial_section


class NotFoundTests(OfflineTestCase):
    def test_specific_envelopes(self):
        cases = [({'code': 'company_not_found'}, 'company_not_found'),
                 ({'message': 'Company not found.'}, 'company_not_found'),
                 ({'detail': 'Financial data not found'}, 'financial_dataset_not_found'),
                 ({'error': {'message': 'Financial dataset not found'}}, 'financial_dataset_not_found'),
                 ({'error': {'code': 'route_not_found'}}, 'endpoint_not_found'),
                 ({'error': 'Endpoint not found'}, 'endpoint_not_found')]
        for body, expected in cases:
            with self.subTest(body=body):
                self.assertEqual(classify_financial_404(body)['not_found_cause'], expected)

    def test_generic_unfamiliar_and_conflicting_signals_remain_unknown(self):
        cases = [None, '<html>Company not found</html>', {}, {'detail': 'Not Found'},
                 {'message': 'No financial statements published'},
                 {'message': 'Maybe company not found; try a different endpoint'},
                 {'error': {'code': ['company_not_found']}},
                 {'code': 'future_provider_code'},
                 {'code': 'company_not_found', 'message': 'Route not found'}]
        for body in cases:
            with self.subTest(body=body):
                self.assertEqual(classify_financial_404(body)['not_found_cause'], 'unknown')

    def test_matching_code_and_message(self):
        result = classify_financial_404({'error': {'code': 'financial_data_not_found', 'message': 'Financial data not found'}})
        self.assertEqual(result['classification_basis'], 'recognized_code')
        self.assertEqual(result['not_found_cause'], 'financial_dataset_not_found')

    @patch.object(de, 'API_KEY', 'test-secret')
    def test_rest_sdk_parity_and_safe_logs(self):
        for cause, body in [('company_not_found', {'detail': 'Company not found'}),
                            ('financial_dataset_not_found', {'error': {'message': 'Financial data not found'}}),
                            ('endpoint_not_found', {'code': 'route_not_found'}),
                            ('unknown', {'detail': 'Not Found', 'token': 'test-secret'})]:
            response = MagicMock(status_code=404)
            response.json.return_value = body
            error = RuntimeError('test-secret https://sensitive.example')
            error.status_code = 404
            error.body = body
            sdk = MagicMock()
            sdk.company.get_financials_v1.side_effect = error
            outputs = []
            for module in (None, SimpleNamespace(Openregister=MagicMock(return_value=sdk))):
                terminal = io.StringIO()
                with patch.dict(sys.modules, {'openregister': module}), patch('requests.get', return_value=response) as request, redirect_stdout(terminal):
                    result = de._get_financials('id', allow_paid=True)
                self.assertEqual(result['not_found_cause'], cause)
                self.assertEqual(result['request_status'], 'failed')
                self.assertEqual(result['publication_status'], 'unknown')
                self.assertEqual(result['financial_data_status'], 'provider_unavailable' if cause == 'financial_dataset_not_found' else 'unknown')
                self.assertNotIn('test-secret', terminal.getvalue())
                self.assertNotIn('https://', terminal.getvalue())
                self.assertEqual(request.call_count, 1 if module is None else 0)
                outputs.append(result['classification_basis'])
            self.assertEqual(outputs[0], outputs[1])

    @patch.object(de, 'API_KEY', 'test-secret')
    def test_sdk_existing_response_body_is_used_without_rest_request(self):
        error = RuntimeError('untrusted message')
        error.status_code = 404
        error.response = MagicMock()
        error.response.json.return_value = {'detail': 'Financial data not found'}
        sdk = MagicMock()
        sdk.company.get_financials_v1.side_effect = error
        with patch.dict(sys.modules, {'openregister': SimpleNamespace(Openregister=MagicMock(return_value=sdk))}), patch('requests.get') as request, redirect_stdout(io.StringIO()):
            result = de._get_financials('id', allow_paid=True)
        request.assert_not_called()
        self.assertEqual(result['not_found_cause'], 'financial_dataset_not_found')

    def test_availability_dimensions_survive_analysis_and_rendering(self):
        data = {'status': 'unavailable', 'request_status': 'failed', 'financial_data_status': 'provider_unavailable',
                'publication_status': 'unknown', 'not_found_cause': 'financial_dataset_not_found',
                'classification_basis': 'recognized_message', 'http_status': 404}
        analysis = analyze_financials(data)
        for key, value in data.items():
            self.assertEqual(analysis[key], value)
        section = '\n'.join(financial_section(analysis))
        self.assertIn('API request outcome: failed', section)
        self.assertIn('Provider data availability: provider unavailable', section)
        self.assertIn('Independent publication status: unknown', section)
        self.assertNotIn('No financial figures published', section)


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
