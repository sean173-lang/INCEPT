"""Sanitized provider-shape regressions. IDs, amounts and URLs are synthetic."""
from datetime import date
import json
from unittest.mock import patch

from offline_support import OfflineTestCase
from scripts.financial_analysis import analyze_financials
from scripts.report_renderer import financial_section
from scripts.volkswagen_financial_test import validate_raw
import test_volkswagen_financial_test as fixtures


def payload():
    return {'reports':[
        {'report_id':'synthetic-2024','consolidated':True,'report_start_date':'2024-01-01','report_end_date':'2024-12-31',
         'sources':[{'html_url':'https://example.invalid/private?X-Amz-Signature=DO_NOT_RENDER&token=SECRET'}]},
        {'report_id':'synthetic-2025','consolidated':True,'report_start_date':'2025-01-01','report_end_date':'2025-12-31'}],
        'indicators':[{'report_id':'synthetic-2024','date':'2024-12-31','revenue':10000,'net_income':1000,'balance_sheet_total':20000,'equity':4000,'cash':2000},
                      {'report_id':'synthetic-2025','date':'2025-12-31','revenue':12000,'net_income':900,'balance_sheet_total':22000,'equity':5000,'cash':1800}]}


def analyze(raw):
    return analyze_financials({'provider':'OpenRegister','raw':raw,'status':'available'},today=date(2026,11,10))


class CachedFinancialRegressionTests(OfflineTestCase):
    def test_actual_shape_extracts_figures_without_inventing_units(self):
        result=analyze(validate_raw(payload()))
        for period in result['periods']:
            self.assertEqual(period['facts']['total_assets']['source_field'],'indicators.balance_sheet_total')
            self.assertIsNone(period['facts']['revenue']['currency']);self.assertIsNone(period['facts']['revenue']['scale'])
            self.assertIsNone(period['ratios']['net_margin']['value'])
        for metric in ('revenue','net_income','total_assets','equity','cash'):
            change=result['comparisons'][0]['changes'][metric]
            self.assertIsNone(change['absolute_change']);self.assertIn('currency or scale',change['reason'])
        self.assertEqual(result['periods'][0]['facts']['revenue']['value'],'10000')

    def test_explicit_indicator_units_are_preserved_and_calculable(self):
        data=payload()
        for row in data['indicators']:row.update(currency='EUR',scale='0.01')
        result=analyze(validate_raw(data))
        self.assertEqual(result['periods'][0]['ratios']['equity_ratio']['value'],'0.2')
        change=result['comparisons'][0]['changes']['revenue']
        self.assertEqual(change['absolute_change'],'20.00');self.assertEqual(change['percent_change'],'20.0')
        self.assertEqual(change['currency'],'EUR')

    def test_conflicting_units_block_calculations(self):
        data=payload();data.update(currency='EUR',scale=1)
        data['indicators'][0].update(currency='USD',scale=1000)
        result=analyze(data)
        self.assertTrue(result['periods'][0]['unit_conflict'])
        self.assertIsNone(result['comparisons'][0]['changes']['revenue']['absolute_change'])

    def test_prior_indicator_date_conflict_stays_invalid(self):
        data=payload();data['indicators'][0]['date']='2023-12-31'
        result=analyze(data)
        self.assertTrue(result['periods'][0]['period_conflict'])
        self.assertEqual(result['periods'][0]['indicator_date'],'2023-12-31')
        self.assertFalse(result['periods'][0]['valid_period'])
        self.assertEqual(result['comparisons'],[])
        self.assertIn('Date conflict','\n'.join(financial_section(result)))

    def test_no_scope_mixing_and_no_nonconsecutive_yoy(self):
        data=payload();data.update(currency='EUR',scale=1)
        other=dict(data['reports'][0],report_id='standalone',consolidated=False)
        data['reports'].append(other)
        data['indicators'].append(dict(data['indicators'][0],report_id='standalone',revenue=999999))
        result=analyze(data)
        comparable=[c for c in result['comparisons'] if c['changes']['revenue']['absolute_change'] is not None]
        self.assertEqual(len(comparable),1);self.assertEqual(comparable[0]['scope'],'consolidated')
        data=payload();data.update(currency='EUR',scale=1)
        data['reports'][0].update(report_start_date='2022-01-01',report_end_date='2022-12-31')
        data['indicators'][0]['date']='2022-12-31'
        self.assertIn('Non-consecutive',analyze(data)['comparisons'][0]['reason'])

    def test_no_signed_urls_in_rendered_financial_section(self):
        result=analyze(payload());report='\n'.join(financial_section(result))
        self.assertIn('synthetic-2024',report)
        for secret in ('X-Amz','SECRET','DO_NOT_RENDER','example.invalid'):self.assertNotIn(secret,report)
        self.assertIn('X-Amz',json.dumps(result['periods'][0]['document_sources']))


class CachedReportRegenerationTests(OfflineTestCase):
    setUp=fixtures.FinancialProfileTests.setUp
    profile=fixtures.FinancialProfileTests.profile
    approved=fixtures.FinancialProfileTests.approved

    def test_report_reanalysis_only_no_approval_or_pricing_dependency(self):
        p,nonce=self.approved();self.transport.request.return_value=payload();original=p.run(nonce)
        self.transport.request.reset_mock()
        before=p.db.read_bytes();cache=(p.cache_dir/(original['company']['provider_company_id']+'.json')).read_bytes()
        self.now+=86400*30
        report=p.regenerate_report().read_text()
        self.transport.request.assert_not_called()
        self.assertEqual(p.db.read_bytes(),before)
        self.assertEqual((p.cache_dir/(original['company']['provider_company_id']+'.json')).read_bytes(),cache)
        for secret in ('X-Amz','SECRET','DO_NOT_RENDER'):self.assertNotIn(secret,report)
        self.assertIn('synthetic-2024',report)
        self.assertIn('currency or scale',report)
        self.assertEqual(p.status()['estimated_credits_reserved'],10)
