"""HTTP integration tests. All provider I/O is synthetic or mocked."""
import concurrent.futures
import contextvars
import threading
from unittest.mock import MagicMock, patch

import requests
from fastapi.testclient import TestClient

from offline_support import OfflineTestCase
from scripts import company_service as operations
from scripts.api_usage import UsageTracker, RegistryRecord, get_tracker, use_tracker
from scripts.http_service import create_app

DE_INPUT = {'company_name': 'Example GmbH', 'jurisdiction': 'Germany'}
DE_SELECTION = {**DE_INPUT, 'provider_company_id': 'DE-HRB-F1103-123'}
DE_CANDIDATE = {'name': 'Example GmbH', 'company_id': 'DE-HRB-F1103-123',
                'register_number': '123', 'register_court': 'Berlin', 'register_type': 'HRB'}
DE_RAW = {'id': 'DE-HRB-F1103-123', 'name': {'name': 'Example GmbH'},
          'company_register': {'register_number': '123', 'register_court': 'Berlin', 'register_type': 'HRB'},
          'incorporated_at': '2020-01-01'}
UK_INPUT = {'company_name': 'Example Limited', 'jurisdiction': 'UK'}
UK_SELECTION = {**UK_INPUT, 'provider_company_id': '01234567'}
UK_RAW = {'company_name': 'Example Limited', 'company_number': '01234567', 'date_of_creation': '2020-01-01'}


def record(raw=None):
    return RegistryRecord(raw or DE_RAW, retrieved_at='2026-11-10T12:00:00+00:00')


class HTTPServiceTests(OfflineTestCase):
    def setUp(self):
        self.app = create_app(ledger_path=None, cache_dir=None)
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)

    def live_app(self, **kwargs):
        return create_app(development=False, service_token='test-service-token', ledger_path=None, cache_dir=None, **kwargs)

    def test_health_and_openapi_contract(self):
        self.assertEqual(self.client.get('/health').json(), {'status': 'ok', 'development': True})
        spec = self.client.get('/openapi.json').json()
        for path in ('/v1/company/search', '/v1/company/verify', '/v1/research/search', '/v1/usage'):
            self.assertIn(path, spec['paths'])
        self.assertEqual(set(spec['components']['schemas']['VerificationResponse']['properties']['status']['enum']),
                         {'verified', 'ambiguous', 'not_found', 'verification_failed'})

    def test_live_mode_requires_token_at_startup(self):
        with self.assertRaises(ValueError):
            create_app(development=False)

    def test_authentication_precedes_provider_calls(self):
        with TestClient(self.live_app()) as client, patch.object(operations.company_search, 'search_companies') as search:
            for headers in ({}, {'X-LEGALFLOW-Service-Key': 'wrong-secret'}):
                response = client.post('/v1/company/search', json=DE_INPUT, headers=headers)
                self.assertEqual(response.status_code, 401)
                self.assertNotIn('wrong-secret', response.text)
            search.assert_not_called()

    def test_request_validation_without_input_echo_or_calls(self):
        cases = [{}, {'company_name': None, 'jurisdiction': 'Germany'},
                 {'company_name': '  ', 'jurisdiction': 'Germany'},
                 {'company_name': 'x\n', 'jurisdiction': 'Germany'},
                 {'company_name': 'x' * 201, 'jurisdiction': 'Germany'},
                 {'company_name': 'x', 'jurisdiction': 'US'},
                 {**DE_INPUT, 'approved': True, 'api_key': 'DO-NOT-ECHO'},
                 {**DE_INPUT, 'provider_company_id': '../secret'},
                 {**UK_INPUT, 'provider_company_id': '123'},
                 {**UK_INPUT, 'register_court': 'Berlin'},
                 {**DE_INPUT, 'provider_company_id': 'GB-12345678'}]
        with patch.object(operations.company_search, 'search_companies') as search, patch.object(operations.german_register, 'get_company') as details:
            for body in cases:
                response = self.client.post('/v1/company/verify', json=body)
                self.assertEqual(response.status_code, 422, body)
                self.assertEqual(response.json()['error']['code'], 'invalid_request')
                self.assertNotIn('DO-NOT-ECHO', response.text)
                self.assertNotIn('input', response.json()['error'])
            search.assert_not_called()
            details.assert_not_called()

    def test_invalid_json_has_safe_structured_error(self):
        response = self.client.post('/v1/company/verify', content='{bad-json-secret', headers={'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 422)
        self.assertNotIn('bad-json-secret', response.text)

    @patch.object(operations.companies_house, 'search_company')
    @patch.object(operations.company_search, 'search_companies', return_value=[DE_CANDIDATE])
    def test_german_search_only_returns_candidates(self, search, uk):
        response = self.client.post('/v1/company/search', json=DE_INPUT)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'candidates_found')
        self.assertNotIn('verification_id', response.json())
        self.assertEqual(response.json()['candidates'][0]['jurisdiction'], 'Germany')
        uk.assert_not_called()
        search.assert_called_once_with('Example GmbH')

    @patch.object(operations.company_search, 'search_companies')
    @patch.object(operations.companies_house, 'search_company', return_value={'items': [{'title': 'Example Limited', 'company_number': '01234567'}]})
    def test_uk_search_routes_to_companies_house(self, search, de):
        response = self.client.post('/v1/company/search', json=UK_INPUT)
        self.assertEqual(response.json()['candidates'][0]['registration_number'], '01234567')
        de.assert_not_called()

    @patch.object(operations.company_search, 'search_companies', return_value=[DE_CANDIDATE])
    @patch.object(operations.german_register, 'get_company', return_value=record())
    def test_name_candidate_is_verified_only_after_detail_checks(self, details, search):
        response = self.client.post('/v1/company/verify', json=DE_INPUT)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'verified')
        self.assertTrue(all(response.json()['checks'].values()))
        self.assertTrue(response.json()['verification_id'])
        self.assertEqual(response.json()['verification_scope'], 'provider_record_identity')
        details.assert_called_once_with('DE-HRB-F1103-123')

    @patch.object(operations.company_search, 'search_companies', return_value=[DE_CANDIDATE, {**DE_CANDIDATE, 'company_id': 'DE-HRB-OTHER-123'}])
    @patch.object(operations.german_register, 'get_company')
    def test_ambiguous_search_stops_before_details(self, details, search):
        response = self.client.post('/v1/company/verify', json=DE_INPUT)
        self.assertEqual(response.json()['status'], 'ambiguous')
        self.assertIsNone(response.json()['verification_id'])
        details.assert_not_called()

    @patch.object(operations.company_search, 'search_companies', return_value=[])
    def test_no_candidates_not_found(self, search):
        self.assertEqual(self.client.post('/v1/company/verify', json=DE_INPUT).json()['status'], 'not_found')

    def test_same_name_cannot_verify_missing_or_conflicting_registration(self):
        cases = [
            {**DE_RAW, 'id': 'DE-WRONG'},
            {**DE_RAW, 'id': 'DEHRBF1103123'},
            {**DE_RAW, 'company_register': {}},
            {**DE_RAW, 'company_register': {'register_number': '123'}},
            {**DE_RAW, 'name': {'name': 'Unrelated GmbH'}},
            {**DE_RAW, 'country': 'GB'},
        ]
        for raw in cases:
            with patch.object(operations.german_register, 'get_company', return_value=record(raw)):
                response = self.client.post('/v1/company/verify', json=DE_SELECTION)
                self.assertEqual(response.json()['status'], 'verification_failed')
                self.assertIsNone(response.json()['verification_id'])

    @patch.object(operations.german_register, 'get_company', return_value=record())
    def test_explicit_registration_court_and_type_constraints(self, details):
        valid = self.client.post('/v1/company/verify', json={**DE_SELECTION, 'registration_number': 'HRB 123', 'register_type': 'HRB', 'register_court': 'Amtsgericht Berlin'})
        self.assertEqual(valid.json()['status'], 'verified')
        for constraints in ({'registration_number': '124'}, {'register_court': 'Hamburg'}, {'register_type': 'HRA'}, {'registration_number': 'HRA 123'}):
            response = self.client.post('/v1/company/verify', json={**DE_SELECTION, **constraints})
            self.assertEqual(response.json()['status'], 'verification_failed')

    @patch.object(operations.companies_house, 'get_company_profile', return_value=UK_RAW)
    @patch.object(operations.german_register, 'get_company')
    def test_uk_selected_company_details_and_number(self, de, details):
        response = self.client.post('/v1/company/verify', json=UK_SELECTION)
        self.assertEqual(response.json()['status'], 'verified')
        self.assertEqual(response.json()['company']['provider'], 'Companies House')
        details.assert_called_once_with('01234567')
        de.assert_not_called()
        mismatch = self.client.post('/v1/company/verify', json={**UK_SELECTION, 'registration_number': '99999999'})
        self.assertEqual(mismatch.json()['status'], 'verification_failed')

    @patch.object(operations.german_register, 'get_company')
    def test_provider_detail_404_is_not_found(self, details):
        error = RuntimeError('sensitive token')
        error.status_code = 404
        details.side_effect = error
        response = self.client.post('/v1/company/verify', json=DE_SELECTION)
        self.assertEqual(response.json()['status'], 'not_found')
        self.assertNotIn('sensitive', response.text)

    @patch.object(operations.german_register, 'get_company')
    def test_network_and_http_failures_are_safe(self, details):
        failures = [(requests.exceptions.Timeout('token-secret'), 504, 'provider_timeout'),
                    (requests.exceptions.ConnectionError('token-secret'), 502, 'provider_connection_failed')]
        for status in (401, 403, 429, 500):
            error = RuntimeError('token-secret https://sensitive.example')
            error.status_code = status
            failures.append((error, 502, 'provider_access_failed' if status in (401, 403) else 'provider_rate_limited' if status == 429 else 'provider_operation_failed'))
        for error, status, code in failures:
            details.side_effect = error
            response = self.client.post('/v1/company/verify', json=DE_SELECTION)
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.json()['status'], 'verification_failed')
            self.assertEqual(response.json()['error']['code'], code)
            self.assertNotIn('token-secret', response.text)
            self.assertNotIn('sensitive.example', response.text)

    def test_default_live_policy_blocks_paid_adapter_before_sdk(self):
        with TestClient(self.live_app()) as client, patch.object(operations.german_register, 'get_client') as factory:
            response = client.post('/v1/company/verify', json=DE_SELECTION, headers={'X-LEGALFLOW-Service-Key': 'test-service-token'})
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()['error']['code'], 'approval_required')
            factory.assert_not_called()

    def test_credit_limit_cannot_be_overridden_by_http_body(self):
        with TestClient(self.live_app(allow_paid=True, max_openregister_credits=0)) as client, patch.object(operations.german_register, 'get_client') as factory:
            response = client.post('/v1/company/verify', json=DE_SELECTION, headers={'X-LEGALFLOW-Service-Key': 'test-service-token'})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.json()['error']['code'], 'budget_exceeded')
            factory.assert_not_called()

    @patch.object(operations.german_register, 'get_company', return_value=record())
    @patch.object(operations.company_research, 'research_company')
    def test_research_uses_verified_server_identity_and_evidence_filter(self, research, details):
        research.return_value = {'sources': [
            {'title': 'Example GmbH', 'url': 'https://example.org/a', 'content': 'Example GmbH pending litigation', 'score': 0.5},
            {'title': 'Other GmbH', 'url': 'https://example.org/b', 'content': 'Unrelated company'},
        ]}
        verification = self.client.post('/v1/company/verify', json=DE_SELECTION).json()
        response = self.client.post('/v1/research/search', json={'verification_id': verification['verification_id']})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body['risk_assessment'], 'Undetermined')
        self.assertTrue(body['sources'][0]['usable'])
        self.assertFalse(body['sources'][1]['usable'])
        self.assertFalse(body['sources'][0]['verified_legal_finding'])
        research.assert_called_once_with('Example GmbH', 'Germany', registration_number='123', register_court='Berlin')
        tampered = self.client.post('/v1/research/search', json={'verification_id': verification['verification_id'], 'company_name': 'Other GmbH'})
        self.assertEqual(tampered.status_code, 422)

    @patch.object(operations.company_research, 'research_company')
    def test_unverified_or_expired_identity_cannot_trigger_research(self, research):
        response = self.client.post('/v1/research/search', json={'verification_id': 'a' * 32})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['error']['code'], 'verification_required')
        with patch.object(operations.german_register, 'get_company', return_value=record()):
            reference = self.client.post('/v1/company/verify', json=DE_SELECTION).json()['verification_id']
        self.app.state.company_service.clock = lambda: float('inf')
        response = self.client.post('/v1/research/search', json={'verification_id': reference})
        self.assertEqual(response.json()['error']['code'], 'verification_expired')
        research.assert_not_called()

    def test_development_end_to_end_no_provider_network_or_credits(self):
        for jurisdiction, name, identifier in [('Germany', 'LEGALFLOW DEMO GmbH', 'DEMO'), ('UK', 'LEGALFLOW DEMO LTD', '00000000')]:
            response = self.client.post('/v1/company/verify', json={'company_name': name, 'jurisdiction': jurisdiction, 'provider_company_id': identifier})
            self.assertEqual(response.json()['status'], 'verified')
            self.assertTrue(response.json()['development'])
            research = self.client.post('/v1/research/search', json={'verification_id': response.json()['verification_id']})
            self.assertEqual(research.status_code, 200)
        usage = self.client.get('/v1/usage').json()
        self.assertEqual(usage['run_openregister_credits_estimated'], 0)
        self.assertEqual(usage['run_tavily_searches'], 0)
        self.assertFalse(usage['billing_confirmed'])

    def test_shared_session_budget_and_duplicate_protection_across_requests(self):
        app = self.live_app(allow_paid=True, max_openregister_credits=10)
        headers = {'X-LEGALFLOW-Service-Key': 'test-service-token'}
        sdk = MagicMock()
        sdk.company.get_details_v1.side_effect = requests.exceptions.Timeout('sensitive')
        with TestClient(app) as client, patch.object(operations.german_register, 'get_client', return_value=sdk):
            first = client.post('/v1/company/verify', json=DE_SELECTION, headers=headers)
            second = client.post('/v1/company/verify', json=DE_SELECTION, headers=headers)
            third = client.post('/v1/company/verify', json={**DE_SELECTION, 'provider_company_id': 'DE-OTHER'}, headers=headers)
            self.assertEqual(first.status_code, 504)
            self.assertEqual(second.status_code, 409)
            self.assertEqual(third.status_code, 429)
            self.assertEqual(client.get('/v1/usage', headers=headers).json()['run_openregister_credits_estimated'], 10)
        sdk.company.get_details_v1.assert_called_once()

    def test_context_bindings_are_isolated_and_nested_context_restored(self):
        outer = UsageTracker(development=True)
        first = UsageTracker()
        second = UsageTracker()
        barrier = threading.Barrier(2)
        def overlapping_current(tracker):
            with use_tracker(tracker):
                barrier.wait(timeout=5)
                actual = get_tracker()
                barrier.wait(timeout=5)
                return actual
        def current(tracker):
            with use_tracker(tracker):
                return get_tracker()
        with use_tracker(outer), concurrent.futures.ThreadPoolExecutor(2) as pool:
            future_a = pool.submit(overlapping_current, first)
            future_b = pool.submit(overlapping_current, second)
            self.assertIs(future_a.result(), first)
            self.assertIs(future_b.result(), second)
            self.assertIs(get_tracker(), outer)
        context_a, context_b = contextvars.Context(), contextvars.Context()
        self.assertIs(context_a.run(current, first), first)
        self.assertIs(context_b.run(current, second), second)

    @patch.object(operations.company_search, 'search_companies', return_value=[{**DE_CANDIDATE, 'company_id': '../unsafe'}])
    def test_invalid_upstream_candidate_cannot_construct_provider_url(self, search):
        with patch.object(operations.german_register, 'get_company') as details:
            response = self.client.post('/v1/company/verify', json=DE_INPUT)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()['error']['code'], 'unsupported_provider_response')
        details.assert_not_called()


if __name__ == '__main__':
    import unittest
    unittest.main()
