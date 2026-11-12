"""Offline source-type regression tests using synthetic, non-research fixtures."""
from __future__ import annotations

import json
import subprocess
import unittest

from projects.ironhack_project3.build_workflow import build


def make_fixture(*, invalid_registry_finding: bool = False, registry_only: bool = False) -> dict:
    sources = [{"id": "REGISTRY-1", "kind": "registry", "source_type": "official_registry",
                "title": "Synthetic registry fixture", "url": "https://example.invalid/registry",
                "retrieved_at": "2026-01-01T00:00:00Z", "published_at": None}]
    if not registry_only:
        sources.extend({"id": f"WEB-{i}", "kind": "web_lead", "source_type": "public_web",
                        "title": f"Synthetic web fixture {i}", "url": f"https://example.invalid/{i}",
                        "retrieved_at": "2026-01-01T00:00:00Z", "published_at": None}
                       for i in range(1, 6))
    report = {"executive_summary": [], "business_model_analysis": [],
              "public_findings": ([] if registry_only else [{
                  "source_id": "REGISTRY-1" if invalid_registry_finding else "WEB-1",
                  "finding": "Synthetic finding.", "significance": "Synthetic significance.",
                  "finding_type": "public_development"}]),
              "analytical_observations": [], "information_gaps": [], "recommended_actions": [],
              "business_activity_source_ids": ["REGISTRY-1"],
              "public_research_source_ids": [] if registry_only else [f"WEB-{i}" for i in range(1, 6)],
              "development_source_ids": [], "uncertainties": [], "follow_ups": []}
    response = {"status": "completed", "model": "fixture-model", "usage": {}, "output": [{
        "content": [{"type": "output_text", "text": json.dumps(report)}]}]}
    return {"execution_id": "offline-fixture", "entrypoint": "form", "response": response,
            "evidence": {"company": {"name": "Fixture GmbH", "legal_form": "gmbh",
                                        "register": {"register_type": "HRB", "register_number": "1",
                                                     "register_court": "Berlin"},
                                        "address": {}, "purpose": "Synthetic test data.", "status": "active"},
                         "sources": sources, "rag_context": [], "tavily_result_count": 0,
                         "tavily_http_status": 200, "tavily_accepted_count": len(sources)-1,
                         "tavily_rejected_reasons": [], "search_query": "synthetic fixture"}}


def run_node(source: str, expression: str, payload: dict) -> dict:
    script = source + "\nconst p=JSON.parse(require('fs').readFileSync(0,'utf8'));const result=" + expression + ";process.stdout.write(JSON.stringify(result));"
    result = subprocess.run(["node", "-e", script], input=json.dumps(payload), text=True,
                            capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


def validation_node() -> str:
    return next(n for n in build()["nodes"] if n["name"] == "Validate & Render Report")["parameters"]["jsCode"]


def openai_report(fixture: dict) -> dict:
    return json.loads(fixture["response"]["output"][0]["content"][0]["text"])


def run_validation(fixture: dict) -> dict:
    payload = {"response": fixture["response"], "evidence": fixture["evidence"],
               "entrypoint": fixture["entrypoint"], "execution_id": fixture["execution_id"],
               "code": validation_node()}
    harness = "const p=JSON.parse(require('fs').readFileSync(0,'utf8'));const data={'Assemble Evidence':p.evidence,'Normalize Input':{entrypoint:p.entrypoint}};const f=new Function('$input','$execution','$',p.code);const out=f({first:()=>({json:p.response})},{id:p.execution_id},(name)=>({first:()=>({json:data[name]||{}})}));process.stdout.write(JSON.stringify(out[0].json));"
    result = subprocess.run(["node", "-e", harness], input=json.dumps(payload), text=True,
                            capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


def run_prepare_schema(evidence: dict) -> list[str]:
    code = next(n for n in build()["nodes"] if n["name"] == "Prepare OpenAI Input")["parameters"]["jsCode"]
    script = "const p=JSON.parse(require('fs').readFileSync(0,'utf8'));const f=new Function('$input',p.code);const out=f({first:()=>({json:p.evidence})});process.stdout.write(JSON.stringify(out[0].json.openai_request.text.format.schema.properties.public_findings.items.properties.source_id.enum));"
    result = subprocess.run(["node", "-e", script], input=json.dumps({"code": code, "evidence": evidence}),
                            text=True, capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


class Project3SourceValidationTests(unittest.TestCase):
    def test_registry_source_in_public_finding_is_rejected_precisely(self):
        fixture = make_fixture(invalid_registry_finding=True)
        report = openai_report(fixture)
        self.assertEqual(report["public_findings"][0]["source_id"], "REGISTRY-1")
        self.assertEqual({s["id"] for s in fixture["evidence"]["sources"] if s["kind"] == "web_lead"},
                         {"WEB-1", "WEB-2", "WEB-3", "WEB-4", "WEB-5"})
        result = run_validation(fixture)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "public_finding_source_invalid")
        self.assertEqual(result["failed_field"], "public_findings[0].source_id")

    def test_valid_public_source_response_passes(self):
        result = run_validation(make_fixture())
        self.assertTrue(result["ok"], result)
        self.assertTrue(result["validation"]["source_ids_valid"])

    def test_registry_only_report_passes_with_empty_public_findings(self):
        fixture = make_fixture(registry_only=True)
        report = openai_report(fixture)
        result = run_validation(fixture)
        self.assertTrue(result["ok"], result)

    def test_unknown_source_id_is_rejected(self):
        fixture = make_fixture()
        report = openai_report(fixture)
        report["public_research_source_ids"] = ["WEB-404"]
        fixture["response"]["output"][0]["content"][0]["text"] = json.dumps(report)
        result = run_validation(fixture)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "unknown_source_id")
        self.assertEqual(result["failed_field"], "public_research_source_ids")

    def test_wrong_source_type_in_research_source_array_is_rejected(self):
        fixture = make_fixture()
        report = openai_report(fixture)
        report["public_research_source_ids"] = ["REGISTRY-1"]
        fixture["response"]["output"][0]["content"][0]["text"] = json.dumps(report)
        result = run_validation(fixture)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], "source_type_mismatch")
        self.assertEqual(result["failed_field"], "public_research_source_ids")

    def test_duplicate_valid_source_references_remain_valid(self):
        fixture = make_fixture()
        report = openai_report(fixture)
        report["public_research_source_ids"] = ["WEB-1", "WEB-1"]
        fixture["response"]["output"][0]["content"][0]["text"] = json.dumps(report)
        result = run_validation(fixture)
        self.assertTrue(result["ok"], result)

    def test_openai_schema_constrains_public_findings_to_available_web_ids(self):
        fixture = make_fixture()
        result = run_prepare_schema(fixture["evidence"])
        self.assertEqual(result, ["WEB-1", "WEB-2", "WEB-3", "WEB-4", "WEB-5"])

    def test_registry_only_schema_uses_non_source_sentinel_and_model_must_leave_findings_empty(self):
        fixture = make_fixture()
        evidence = dict(fixture["evidence"])
        evidence["sources"] = [s for s in evidence["sources"] if s["kind"] == "registry"]
        result = run_prepare_schema(evidence)
        self.assertEqual(result, ["NO_PUBLIC_WEB_SOURCE"])
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        self.assertIn("return an empty `public_findings` array", (root / "projects/ironhack_project3/prompts/corporate_intelligence_v1.md").read_text())


if __name__ == "__main__":
    unittest.main()
