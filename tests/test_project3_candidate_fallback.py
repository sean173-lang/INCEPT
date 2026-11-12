"""Offline checks for the minimal OpenRegister candidate fallback."""
from __future__ import annotations

import json
import subprocess
import unittest

from projects.ironhack_project3.build_workflow import build


def run_selector(company_name: str, rows: list[dict], register_identifier: str | None = None) -> dict:
    selector = next(n for n in build()["nodes"] if n["name"] == "Select Exact Entity")["parameters"]["jsCode"]
    harness = "const p=JSON.parse(require('fs').readFileSync(0,'utf8'));const f=new Function('$input','$',p.code);const out=f({first:()=>({json:{body:{results:p.rows}}})},()=>({first:()=>({json:{company_name:p.name,register_identifier:p.register}})}));process.stdout.write(JSON.stringify(out[0].json));"
    result = subprocess.run(
        ["node", "-e", harness],
        input=json.dumps({"code": selector, "name": company_name, "register": register_identifier, "rows": rows}),
        text=True, capture_output=True, check=True, timeout=10,
    )
    return json.loads(result.stdout)


class Project3CandidateFallbackTests(unittest.TestCase):
    def test_sanitaetshaus_returns_verified_candidate_without_auto_selecting(self):
        row = {"name": "Sanitätshaus MKC GmbH Mitte Kompetenz Center", "company_id": "DE-HRB-F1103-100653",
               "register_number": "100653", "register_type": "HRB", "register_court": "Berlin (Charlottenburg)"}
        result = run_selector("Sanitätshaus MKC GmbH", [row])
        self.assertFalse(result["valid"])
        self.assertEqual(result["error_code"], "company_candidate_selection_required")
        self.assertEqual(result["candidate_count"], 1)
        self.assertIn("Sanitätshaus MKC GmbH Mitte Kompetenz Center", result["message"])
        self.assertIn("HRB 100653", result["message"])
        self.assertIn("Berlin (Charlottenburg)", result["message"])
        self.assertNotIn("registry_match", result)

    def test_exact_single_match_and_someform_continue_automatically(self):
        row = {"name": "someform Studio GmbH", "company_id": "DE-HRB-F1103-235811", "register_number": "235811",
               "register_type": "HRB", "register_court": "Berlin (Charlottenburg)"}
        result = run_selector("someform Studio GmbH", [row])
        self.assertTrue(result["valid"])
        self.assertEqual(result["registry_match"]["company_id"], row["company_id"])

    def test_volkswagen_affiliates_are_candidates_not_automatic_match(self):
        rows = [
            {"name": "Volkswagen Autoversicherung AG", "company_id": "candidate-1", "register_number": "204252", "register_court": "Braunschweig"},
            {"name": "Volkswagen Financial Services AG", "company_id": "candidate-2", "register_number": "210842", "register_court": "Braunschweig"},
        ]
        result = run_selector("Volkswagen AG", rows)
        self.assertFalse(result["valid"])
        self.assertEqual(result["error_code"], "company_candidate_selection_required")
        self.assertIn("Volkswagen Autoversicherung AG", result["message"])
        self.assertIn("Volkswagen Financial Services AG", result["message"])
        self.assertNotIn("registry_match", result)

    def test_duplicate_exact_matches_are_numbered_and_not_selected(self):
        rows = [
            {"name": "Example GmbH", "company_id": "candidate-a", "register_number": "123", "register_type": "HRB", "register_court": "Berlin"},
            {"name": "Example GmbH", "company_id": "candidate-b", "register_number": "456", "register_type": "HRB", "register_court": "Hamburg"},
        ]
        result = run_selector("Example GmbH", rows)
        self.assertFalse(result["valid"])
        self.assertEqual(result["error_code"], "ambiguous_registry_identity")
        self.assertEqual(result["candidate_count"], 2)
        self.assertIn("1. Example GmbH — HRB 123 — Berlin", result["message"])
        self.assertIn("2. Example GmbH — HRB 456 — Hamburg", result["message"])

    def test_no_candidates_has_clear_not_found_message(self):
        result = run_selector("No Such Company GmbH", [])
        self.assertFalse(result["valid"])
        self.assertEqual(result["error_code"], "exact_company_match_not_found")
        self.assertIn("No exact or plausible OpenRegister company match", result["message"])

    def test_register_number_is_matched_only_against_openregister_rows(self):
        rows = [
            {"name": "Example GmbH", "company_id": "DE-HRB-100", "register_number": "100", "register_type": "HRB"},
            {"name": "Example GmbH", "company_id": "DE-HRB-200", "register_number": "200", "register_type": "HRB"},
        ]
        result = run_selector("Example GmbH", rows, "HRB 200")
        self.assertTrue(result["valid"])
        self.assertEqual(result["registry_match"]["company_id"], "DE-HRB-200")

    def test_existing_workflow_and_form_entrypoint_are_preserved(self):
        workflow = build()
        self.assertEqual(workflow["name"], "INCEPT — Company Research Agent")
        nodes = {n["name"]: n for n in workflow["nodes"]}
        self.assertEqual(nodes["Company Research Form"]["parameters"]["path"], "incept-company-research")
        fields = nodes["Company Research Form"]["parameters"]["formFields"]["values"]
        self.assertTrue(next(f for f in fields if f["fieldName"] == "company_name")["requiredField"])
        self.assertFalse(next(f for f in fields if f["fieldName"] == "register_identifier")["requiredField"])
        self.assertNotIn("formTrigger", [n["type"] for n in workflow["nodes"] if n["name"] != "Company Research Form"])


if __name__ == "__main__":
    unittest.main()
