"""Retirement must remove finance paths while preserving current INCEPT capabilities."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock,patch
from fastapi.testclient import TestClient
from offline_support import OfflineTestCase
from scripts.api_usage import UsageTracker,UsageBlocked,use_tracker
from scripts import companies_house,german_register
from scripts.http_service import create_app
from scripts.document_examples import scenarios

class CleanupSafeguards(OfflineTestCase):
    def test_retired_operations_block_before_cache_or_transport_even_with_approval(self):
        for development in (True,False):
            tracker=UsageTracker(approved=True,development=development)
            for op in ('financials','accounts_list','document_metadata','document_download'):
                call=MagicMock()
                with self.assertRaises(UsageBlocked):tracker.execute('OpenRegister',op,'retired',call,mock={})
                call.assert_not_called()
        self.assertFalse(hasattr(german_register,'get_financials'))
        self.assertFalse(hasattr(companies_house,'get_annual_accounts'))

    def test_uk_document_and_accounts_routes_fail_before_transport(self):
        with patch('requests.get') as request:
            for endpoint,params in [('/company/00000000/financials',None),('/document/private',None),('/company/00000000/filing-history',{'category':'accounts'})]:
                with self.assertRaises(ValueError):companies_house.api_request(endpoint,params)
            request.assert_not_called()

    def test_company_search_details_and_officers_still_work_offline(self):
        with use_tracker(UsageTracker(development=True)):
            self.assertTrue(companies_house.search_company('Demo')['items'])
            self.assertEqual(companies_house.get_company_profile('00000000')['company_number'],'00000000')
            self.assertEqual(companies_house.get_company_officers('00000000'),{'items':[]})
            self.assertEqual(german_register.get_company('DEMO').model_dump()['id'],'DEMO')

    def test_retired_financial_topics_and_routes_explicitly_rejected(self):
        with tempfile.TemporaryDirectory() as temp,TestClient(create_app(cache_dir=None,ledger_path=None,onboarding_db=Path(temp)/'demo.sqlite3')) as client:
            paths=client.get('/openapi.json').json()['paths']
            self.assertFalse(any('financial' in p or 'accounts' in p for p in paths))
            self.assertEqual(client.post('/v1/research/runs',json={'verification_id':'a'*32,'topics':['financial_disclosures']}).status_code,422)

    def test_counterparty_lookup_does_not_reclassify_or_mutate_client(self):
        body=scenarios()['individual']
        with tempfile.TemporaryDirectory() as temp,TestClient(create_app(cache_dir=None,ledger_path=None,onboarding_db=Path(temp)/'demo.sqlite3')) as client:
            before=client.post('/v1/onboarding/preview',json=body).json()
            lookup=client.post('/v1/company/verify',json={'company_name':'LEGALFLOW DEMO LTD','jurisdiction':'UK','provider_company_id':'00000000','registration_number':'00000000'})
            self.assertEqual(lookup.status_code,200);self.assertEqual(lookup.json()['status'],'verified')
            after=client.post('/v1/onboarding/preview',json=body).json()
            self.assertEqual(before,after);self.assertEqual(after['client']['client_type'],'individual')
            self.assertNotEqual(after['client']['name'],lookup.json()['company']['name'])

    def test_shared_report_escaping_remains_active(self):
        from scripts.report_renderer import text
        value=text('<script>alert(1)</script> [claim](https://example.invalid)')
        self.assertNotIn('<script>',value);self.assertIn('&lt;script&gt;',value)
        self.assertIn('\\[claim\\]',value)
