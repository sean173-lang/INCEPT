"""German-intake HTTP contract and authentication regressions; no provider I/O."""
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.http_service import create_app


class HTTPServiceTests(OfflineTestCase):
    def setUp(self):
        self.client=TestClient(create_app())
        self.addCleanup(self.client.close)

    def test_active_api_exposes_only_intake_analysis_and_optional_documents(self):
        self.assertEqual(self.client.get('/health').json(),{'status':'ok','development':True})
        paths=set(self.client.get('/openapi.json').json()['paths'])
        self.assertTrue({'/v1/onboarding/extract','/v1/onboarding/synthesis','/v1/onboarding/assessment','/v1/onboarding/preview'}<=paths)
        self.assertFalse(any(path.startswith(('/v1/company','/v1/research','/v1/usage')) for path in paths))

    def test_live_mode_requires_service_authentication(self):
        with self.assertRaises(ValueError):create_app(development=False)
        app=create_app(development=False,service_token='test-service-token')
        with TestClient(app) as client:
            for headers in ({},{'X-LEGALFLOW-Service-Key':'wrong-secret'}):
                response=client.post('/v1/onboarding/extract',json={},headers=headers)
                self.assertEqual(response.status_code,401)
                self.assertNotIn('wrong-secret',response.text)

    def test_validation_errors_do_not_echo_message_or_secrets(self):
        secret='DO-NOT-ECHO-API-KEY'
        for endpoint,body in [('/v1/onboarding/extract',{'body':secret,'unexpected':secret}),
                              ('/v1/onboarding/synthesis',{'api_key':secret})]:
            response=self.client.post(endpoint,json=body)
            self.assertEqual(response.status_code,422)
            self.assertNotIn(secret,response.text)
            self.assertEqual(response.json()['error']['code'],'invalid_request')

    def test_removed_classification_routes_return_not_found(self):
        for endpoint in ('/v1/company/search','/v1/company/verify','/v1/research/search','/v1/usage'):
            self.assertEqual(self.client.post(endpoint,json={}).status_code,404)
