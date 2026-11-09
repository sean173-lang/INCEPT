"""No authenticated network traffic: SDK and REST paths are mocked."""
import io
import json
import sys
import unittest
from offline_support import OfflineTestCase
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from scripts import german_register as de


class SDKStatusError(Exception):
    def __init__(self, status):
        super().__init__('secret-key https://sensitive.example/?token=secret')
        self.status_code = status


class FinancialDiagnosticTests(OfflineTestCase):
    def setUp(self):
        self.key = patch.object(de, 'API_KEY', 'secret-key')
        self.key.start()
        self.addCleanup(self.key.stop)

    def rest(self, status=200, payload=None, error=None):
        response = MagicMock()
        response.status_code = status
        response.json.return_value = payload
        if error and status == 200:
            response.json.side_effect = error
        output = io.StringIO()
        with patch.dict(sys.modules, {'openregister': None}), patch('requests.get', return_value=response) as request, redirect_stdout(output):
            result = de._get_financials('DE-HRB-F1103-267645', allow_paid=True)
        request.assert_called_once()
        self.assertEqual(request.call_args.kwargs['headers']['Authorization'], 'Bearer secret-key')
        self.assertFalse(request.call_args.kwargs['allow_redirects'])
        self.assertSafe(output.getvalue(), result)
        return result, output.getvalue()

    def assertSafe(self, output, result):
        for value in ('secret-key', 'sensitive.example', 'https://', 'Authorization'):
            self.assertNotIn(value, output)
            self.assertNotIn(value, result.get('reason') or '')

    def test_rest_status_categories_and_terminal_diagnostic(self):
        for status, code in ((401, 'authentication_failed'), (402, 'credits_or_billing_required'),
                             (403, 'permission_denied'), (404, 'not_found'), (429, 'rate_limited'),
                             (405, 'invalid_endpoint'), (410, 'invalid_endpoint'), (501, 'invalid_endpoint'),
                             (500, 'provider_error'), (302, 'unexpected_redirect'), (422, 'http_error')):
            with self.subTest(status=status):
                result, output = self.rest(status, {'message': 'secret-key https://sensitive.example'})
                self.assertEqual(result['error_code'], code)
                self.assertEqual(result['http_status'], status)
                self.assertIn(code, output)
                self.assertEqual(result['plan_access'], 'unconfirmed')
                self.assertIn('availability remains unknown', result['reason'])

    def test_route_404_only_identified_from_machine_code(self):
        result, _ = self.rest(404, {'error': {'code': 'route_not_found'}})
        self.assertEqual(result['error_code'], 'invalid_endpoint')
        result, _ = self.rest(404, '<html>not found</html>')
        self.assertEqual(result['error_code'], 'not_found')

    def test_sdk_http_errors_have_same_categories_without_rest_fallback(self):
        for status, code in ((401, 'authentication_failed'), (403, 'permission_denied'),
                             (404, 'not_found'), (429, 'rate_limited')):
            sdk = MagicMock()
            sdk.company.get_financials_v1.side_effect = SDKStatusError(status)
            output = io.StringIO()
            with patch.dict(sys.modules, {'openregister': SimpleNamespace(Openregister=MagicMock(return_value=sdk))}), patch('requests.get') as rest, redirect_stdout(output):
                result = de._get_financials('id', allow_paid=True)
            self.assertEqual(result['error_code'], code)
            sdk.company.get_financials_v1.assert_called_once_with(company_id='id')
            rest.assert_not_called()
            self.assertSafe(output.getvalue(), result)

    def test_network_errors_not_data_absence(self):
        for error, code in ((requests.exceptions.Timeout('secret-key'), 'network_timeout'),
                             (requests.exceptions.ConnectionError('https://sensitive.example'), 'network_error')):
            output = io.StringIO()
            with patch.dict(sys.modules, {'openregister': None}), patch('requests.get', side_effect=error) as request, redirect_stdout(output):
                result = de._get_financials('id', allow_paid=True)
            self.assertEqual(result['error_code'], code)
            self.assertSafe(output.getvalue(), result)
            request.assert_called_once()

    def test_json_and_schema_failures_are_not_no_data(self):
        for payload in ([], 'HTML', {}, {'error': 'secret-key'}, {'indicators': 'bad'},
                        {'indicators': [1]}, {'reports': {}}, {'reports': [{'report_id': {}}]}):
            with self.subTest(payload=payload):
                result, _ = self.rest(payload=payload)
                self.assertEqual(result['error_code'], 'unsupported_response')
                self.assertEqual(result['http_status'], 200)
        result, _ = self.rest(error=ValueError('secret-key https://sensitive.example'))
        self.assertEqual(result['error_code'], 'unsupported_response')

    def test_success_empty_is_not_request_failure_or_absence_proof(self):
        result, output = self.rest(payload={'reports': [], 'indicators': None})
        self.assertEqual(result['error_code'], 'no_indicators_returned')
        self.assertEqual(result['plan_access'], 'request_succeeded')
        self.assertEqual(result['raw']['indicators'], [])
        self.assertIn('does not prove', output)

    def test_success_figures_and_original_shape(self):
        payload = {'reports': [], 'indicators': [{'report_id': 'r', 'date': '2024-12-31', 'revenue': 0}]}
        result, output = self.rest(payload=payload)
        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['raw'], payload)
        self.assertEqual(result['plan_access'], 'request_succeeded')
        self.assertNotIn('secret-key', output)

    def test_sdk_setup_and_parsing_errors_do_not_make_second_call(self):
        for constructor, expected in ((MagicMock(side_effect=TypeError('secret-key')), 'sdk_incompatible'),
                                      (MagicMock(return_value=SimpleNamespace(company=SimpleNamespace(get_financials_v1=lambda **kwargs: object()))), 'unsupported_response')):
            output = io.StringIO()
            with patch.dict(sys.modules, {'openregister': SimpleNamespace(Openregister=constructor)}), patch('requests.get') as request, redirect_stdout(output):
                result = de._get_financials('id', allow_paid=True)
            self.assertEqual(result['error_code'], expected)
            request.assert_not_called()
            self.assertSafe(output.getvalue(), result)

    def test_missing_key_and_default_guard_make_no_requests(self):
        with patch('requests.get') as request, patch.object(de, 'API_KEY', None), redirect_stdout(io.StringIO()):
            self.assertEqual(de._get_financials('id')['status'], 'not_requested')
            self.assertEqual(de._get_financials('id', allow_paid=True)['error_code'], 'missing_credentials')
        request.assert_not_called()


if __name__ == '__main__':
    unittest.main()
