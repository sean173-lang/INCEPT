"""Offline new-graph checks; the proven base workflow is immutable."""
import copy
import json
from pathlib import Path
from offline_support import OfflineTestCase
import test_incept_autonomous_workflow as base_tests
from scripts.incept_autonomous_workflow import build_workflow as original
from scripts.incept_corporate_workflow import build_workflow
from scripts.incept_corporate_demo import scenarios,generate
from scripts.corporate_intelligence import CorporateIntelligence,CorporateRequest
import tempfile

ROOT=Path(__file__).resolve().parents[1]


class CorporateWorkflowTests(OfflineTestCase):
    code=base_tests.AutonomousIntakeWorkflowTests.code
    def setUp(self):
        self.workflow=build_workflow();self.nodes={n['name']:n for n in self.workflow['nodes']};self.intake=scenarios()['germany_company']

    def test_base_export_unchanged_and_new_workflow_separate_and_safe(self):
        self.assertEqual(json.loads((ROOT/'workflows/incept_autonomous_intake_dev.json').read_text()),original())
        self.assertEqual(json.loads((ROOT/'workflows/incept_corporate_intake_dev.json').read_text()),self.workflow)
        self.assertFalse(self.workflow['active']);self.assertEqual(len(self.nodes),37)
        self.assertFalse(any(n.get('credentials') for n in self.nodes.values()))
        for n in self.nodes.values():
            if n['type'].endswith('httpRequest'):
                self.assertNotIn('/financial',n['parameters']['url']);self.assertFalse(n.get('retryOnFail'))
                if n['parameters']['method']=='POST':self.assertTrue(n['parameters']['url'].startswith('http://127.0.0.1:8003/v1/onboarding/'))
        false=self.workflow['connections']['Corporate Intelligence Required?']['main'][1][0]['node']
        self.assertEqual(false,'Plan Bounded Primary Research')

    def route(self,body):return self.code('Route Client Type and Law',{}, {'Validate Intake':{'intake':body}})

    def test_individual_and_company_routing_without_suffix_inference(self):
        for name,body in scenarios().items():
            routed=self.route(body)
            self.assertEqual(routed['ready'],name!='ambiguous')
            self.assertEqual(routed['company'],name in ('germany_company','uk_company'))
        legacy=json.loads((ROOT/'examples/onboarding_preview.json').read_text())
        self.assertFalse(self.route(legacy)['ready'])
        self.assertEqual(self.route(legacy)['client_type'],'unknown')

    def test_governing_law_is_separate_from_company_country(self):
        uk=scenarios()['uk_company'];route=self.route(uk)
        self.assertFalse(self.code('Plan Bounded Primary Research',{}, {'Route Client Type and Law':route})['relevant'])
        uk['matter']['governing_law']='Germany';uk['matter']['summary']=scenarios()['germany_company']['matter']['summary'];route=self.route(uk)
        self.assertTrue(self.code('Plan Bounded Primary Research',{}, {'Route Client Type and Law':route})['relevant'])
        de=scenarios()['germany_company'];de['matter'].pop('governing_law');route=self.route(de)
        self.assertEqual(route['intake']['matter']['governing_law'],'unknown')
        self.assertFalse(self.code('Plan Bounded Primary Research',{}, {'Route Client Type and Law':route})['relevant'])

    def test_company_lookup_failure_nonblocking_and_individual_has_no_section(self):
        fallback=self.code('Corporate Intelligence Result',{'statusCode':503})
        self.assertEqual(fallback['status'],'UNAVAILABLE')
        summary={'bundle':{'assessment':{'content_markdown':'# DEMO\n','sources':[]}}}
        route=self.route(scenarios()['individual'])
        result=self.code('Unified Corporate Mandate Report',copy.deepcopy(summary),{'Route Client Type and Law':route})
        self.assertNotIn('Corporate Client Intelligence',result['bundle']['assessment']['content_markdown'])
        route=self.route(scenarios()['germany_company'])
        result=self.code('Unified Corporate Mandate Report',copy.deepcopy(summary),{'Route Client Type and Law':route,'Corporate Intelligence Result':fallback})
        self.assertIn('UNAVAILABLE',result['bundle']['assessment']['content_markdown'])

    def test_four_real_pipeline_offline_scenarios_generate_distinct_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            result=generate(temp)
            self.assertEqual(set(result),{'individual','germany_company','uk_company','ambiguous'})
            self.assertEqual(result['germany_company']['provider'],'OpenRegister')
            self.assertEqual(result['uk_company']['provider'],'Companies House')
            self.assertEqual(result['ambiguous']['business_state'],'NEEDS_REVIEW')
            for case,record in result.items():
                self.assertEqual(record['external_calls'],0);self.assertEqual(record['financial_requests'],0)
                report=Path(record['report']).read_text()
                if case=='individual':self.assertNotIn('Corporate Client Intelligence',report)
                if case in ('germany_company','uk_company'):self.assertIn('Corporate Client Intelligence',report);self.assertIn('UNVERIFIED',report)
                if case=='uk_company':self.assertIn('NOT VERIFIED',report);self.assertNotIn('BGB §286',report)


class IsolatedExecutionConfigTests(OfflineTestCase):
    def test_isolated_copies_have_no_external_nodes_or_credentials(self):
        from scripts.incept_corporate_execution_test import build_test_workflow
        for case in scenarios():
            w=build_test_workflow(case)
            self.assertFalse(w['active']);self.assertEqual(len(w['nodes']),37)
            for n in w['nodes']:
                self.assertNotIn('credentials',n)
                self.assertIn(n['type'].split('.')[-1],('manualTrigger','if','code','httpRequest'))
                if n['type'].endswith('httpRequest'):
                    self.assertTrue(n['parameters']['url'].startswith('http://127.0.0.1:8004/v1/onboarding/'))
                    self.assertNotIn('financial',n['parameters']['url'])
            final=next(n for n in w['nodes'] if n['name']=='Integrated Onboarding Report')
            self.assertIn('approved_live_email_processed:false',final['parameters']['jsCode'])
            self.assertIn('fixture_substitution:true',final['parameters']['jsCode'])
