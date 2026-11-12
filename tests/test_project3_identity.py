"""Offline registry identity regressions from n8n executions #284–286."""
from __future__ import annotations

import json
import subprocess
import unittest

from projects.ironhack_project3.build_workflow import build


def run_selector(company_name: str, rows: list[dict]) -> dict:
    selector = next(n for n in build()["nodes"] if n["name"] == "Select Exact Entity")["parameters"]["jsCode"]
    harness = "const p=JSON.parse(require('fs').readFileSync(0,'utf8'));const f=new Function('$input','$',p.code);const out=f({first:()=>({json:{body:{results:p.rows}}})},(name)=>({first:()=>({json:{company_name:p.name,register_identifier:null}})}));process.stdout.write(JSON.stringify(out[0].json));"
    result = subprocess.run(["node", "-e", harness], input=json.dumps({"code": selector, "name": company_name, "rows": rows}),
                            text=True, capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


class Project3RegistryIdentityTests(unittest.TestCase):
    def test_execution_285_failure_fixture_does_not_pick_a_volkswagen_affiliate(self):
        rows = [
            {"name": "Volkswagen Autoversicherung AG", "company_id": "candidate-1", "register_number": "204252"},
            {"name": "Volkswagen Versicherung Aktiengesellschaft", "company_id": "candidate-2", "register_number": "200232"},
            {"name": "Volkswagen Financial Services AG", "company_id": "candidate-3", "register_number": "210842"},
            {"name": "TRATON SE", "company_id": "candidate-4", "register_number": "246068"},
            {"name": "Volkswagen Financial Services Overseas AG", "company_id": "candidate-5", "register_number": "3790"},
            {"name": "Volkswagen Group Info Services AG", "company_id": "candidate-6", "register_number": "207876"},
            {"name": "CARIAD SE", "company_id": "candidate-7", "register_number": "208203"},
            {"name": "VOLKSWAGEN CAR.SW ORG 73. Bildverarbeitungsentwicklungs SE & Co. KG", "company_id": "candidate-8", "register_number": "202532"},
            {"name": "Sumitomo Electric Bordnetze SE", "company_id": "candidate-9", "register_number": "205587"},
            {"name": "Volkswagen-AG Preussen Elektra AG Offene Handelsgesellschaft", "company_id": "candidate-10", "register_number": "100135"},
        ]
        result = run_selector("Volkswagen AG", rows)
        self.assertFalse(result["valid"])
        self.assertEqual(result["error_code"], "company_candidate_selection_required")
        self.assertEqual(result["failed_step"], "OpenRegister identity resolution")
        self.assertIn("Volkswagen Autoversicherung AG", result["message"])
        self.assertNotIn("registry_match", result)

    def test_ag_alias_matches_only_the_exact_formal_registered_name(self):
        rows = [
            {"name": "Volkswagen Financial Services AG", "company_id": "affiliate-001", "register_number": "210842"},
            {"name": "Volkswagen Aktiengesellschaft", "company_id": "verified-parent-row", "register_number": "100484",
             "register_type": "HRB", "register_court": "Braunschweig", "legal_form": "ag"},
        ]
        result = run_selector("Volkswagen AG", rows)
        self.assertTrue(result["valid"])
        self.assertEqual(result["registry_match"]["register_number"], "100484")
        self.assertEqual(result["registry_match"]["register_court"], "Braunschweig")
        self.assertEqual(result["registry_match"]["company_id"], "verified-parent-row")

    def test_execution_286_someform_exact_match_still_succeeds(self):
        row = {"name": "someform Studio GmbH", "company_id": "DE-HRB-F1103-235811", "register_number": "235811",
               "register_type": "HRB", "register_court": "Berlin (Charlottenburg)", "legal_form": "gmbh"}
        result = run_selector("someform Studio GmbH", [row])
        self.assertTrue(result["valid"])
        self.assertEqual(result["registry_match"]["company_id"], row["company_id"])

    def test_duplicate_canonical_entities_remain_ambiguous(self):
        rows = [{"name": "Volkswagen AG", "company_id": "parent-a"},
                {"name": "Volkswagen Aktiengesellschaft", "company_id": "parent-b"}]
        result = run_selector("Volkswagen AG", rows)
        self.assertFalse(result["valid"])
        self.assertEqual(result["error_code"], "ambiguous_registry_identity")

    def test_search_expands_ag_without_relaxing_the_identity_matcher(self):
        workflow = build()
        nodes = {n["name"]: n for n in workflow["nodes"]}
        url = nodes["OpenRegister Search"]["parameters"]["url"]
        selector = nodes["Select Exact Entity"]["parameters"]["jsCode"]
        self.assertIn(r"replace(/\s+AG$/i,' Aktiengesellschaft')", url)
        self.assertIn("normEntity(r.name)===normEntity(req.company_name)", selector)
        self.assertIn("candidates.length?'ambiguous_registry_identity'", selector)


if __name__ == "__main__":
    unittest.main()
