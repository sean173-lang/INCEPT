"""Focused offline tests for Project 3 retrieval, analysis contract and Markdown."""
from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

from projects.ironhack_project3.build_workflow import build

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "projects/ironhack_project3"


def run_node(source: str, expression: str, payload: dict) -> dict | str:
    script = source + "\nconst input=JSON.parse(require('fs').readFileSync(0,'utf8'));const result=" + expression + ";process.stdout.write(JSON.stringify(result));"
    result = subprocess.run(["node", "-e", script], input=json.dumps(payload), text=True,
                            capture_output=True, check=True, timeout=10)
    return json.loads(result.stdout)


class Project3QualityTests(unittest.TestCase):
    def setUp(self):
        self.workflow = build()
        self.nodes = {node["name"]: node for node in self.workflow["nodes"]}

    def test_tavily_parser_keeps_relevant_brand_results_and_rejects_collisions(self):
        fixture = {
            "company": {"name": "Shapesty GmbH", "purpose": "Betrieb von Fitnessstudios sowie Verkauf und Vertrieb von Fitness- und Lifestyleprodukten.",
                        "register": {"register_court": "Berlin (Charlottenburg)"}, "address": {"formatted_value": "Wichertstraße 56, Berlin"}},
            "results": [
                {"title": "About us", "url": "https://shapesty.com/about-us", "content": "Shapesty in Berlin. Our fitness studio offers boutique training.", "published_date": None, "score": 0.9},
                {"title": "Lagree Berlin – Shapesty", "url": "https://www.shapesty.com/", "content": "Boutique fitness studio in Berlin offering Lagree classes.", "published_date": "2026-10-01", "score": 0.8},
                {"title": "Strong Sweden moment", "url": "https://facebook.com/strongsweden/posts/1", "content": "A little Berlin moment.", "score": 0.2},
                {"title": "Schaeffler Group", "url": "https://www.schaeffler.com/en", "content": "Industrial bearings and mobility products.", "score": 0.8},
            ]}
        parsed = run_node((PROJECT / "tavily_parser.js").read_text(),
                          "parseTavilySources(input.results,input.company,'2026-11-12T10:00:00Z')", fixture)
        self.assertEqual(parsed["raw_result_count"], 4)
        self.assertEqual([source["id"] for source in parsed["sources"]], ["WEB-1", "WEB-2"])
        self.assertTrue(all(source["kind"] == "web_lead" for source in parsed["sources"]))
        self.assertEqual(parsed["sources"][1]["published_at"], "2026-10-01")
        self.assertEqual(parsed["sources"][0]["source_type"], "company_site_candidate")
        self.assertIn("not independently verified", parsed["sources"][0]["confidence_note"])
        self.assertEqual(parsed["rejected_reasons"], {"brand_mismatch": 2})

    def test_parser_accepts_no_url_global_and_rejects_credentials_or_sensitive_query(self):
        source = (PROJECT / "tavily_parser.js").read_text()
        fixture = {"company": {"name": "Shapesty GmbH", "purpose": "fitness studio", "register": {}, "address": {}},
                   "results": [{"title": "Shapesty fitness", "url": "https://user:pass@shapesty.com/x", "content": "fitness studio"},
                               {"title": "Shapesty fitness", "url": "https://shapesty.com/x?auth_token=abc", "content": "fitness studio"}]}
        parsed = run_node(source, "parseTavilySources(input.results,input.company,'now')", fixture)
        self.assertEqual(parsed["sources"], [])
        self.assertEqual(parsed["rejected_reasons"], {"unsafe_or_invalid_url": 2})
        self.assertNotIn("new URL", source)

    def test_schema_and_versioned_prompt_drive_substantive_report_sections(self):
        js = self.nodes["Prepare OpenAI Input"]["parameters"]["jsCode"]
        schema_match = re.search(r"const schema=(\{.*?\});const webIds=", js)
        self.assertIsNotNone(schema_match)
        schema = json.loads(schema_match.group(1))
        self.assertIn("executive_summary", schema["required"])
        for field in ("business_model_analysis", "public_findings", "analytical_observations", "information_gaps", "recommended_actions"):
            self.assertIn(field, schema["properties"])
        self.assertIn("claim_type", schema["properties"]["business_model_analysis"]["items"]["properties"])
        self.assertIn("company_name:e.company.name", js)
        self.assertIn("registry_evidence:", js)
        self.assertIn("public_web_research:", js)
        self.assertIn("source_id.enum=webIds.length?webIds", js)
        self.assertIn("rag_context:e.rag_context", js)
        self.assertIn("gpt-4o-mini", js)
        prompt = (PROJECT / "prompts/corporate_intelligence_v1.md").read_text()
        self.assertIn("Never invent revenue", prompt)
        self.assertIn("RAG is methodology only", prompt)
        self.assertIn("Ignore instructions", prompt)
        self.assertIn("Never cite `REGISTRY-1` in `public_findings`", prompt)

    def test_markdown_renderer_emits_static_headings_links_and_decoded_entities(self):
        renderer = (PROJECT / "markdown_renderer.js").read_text()
        report = {"executive_summary": [{"text": "Shapesty offers fitness classes & products.", "source_ids": ["WEB-1"], "claim_type": "reported_fact"}],
                  "business_model_analysis": [{"text": "The product mix suggests a combined service and retail model.", "source_ids": ["WEB-1"], "claim_type": "analysis"}], "public_findings": [], "analytical_observations": [],
                  "information_gaps": [], "recommended_actions": []}
        evidence = {"company": {"name": "Shapesty GmbH", "legal_form": "GmbH", "register": {"register_number": "HRB 246468", "register_court": "Berlin"},
                                "address": {"formatted_value": "Berlin"}, "status": "active", "purpose": "Fitnessstudio"},
                    "sources": [{"id": "REGISTRY-1", "title": "OpenRegister", "url": "https://api.openregister.de/record", "retrieved_at": "2026-11-12", "source_type": "official_registry", "confidence": "official"},
                                {"id": "WEB-1", "title": "Shapesty & fitness", "url": "https://shapesty.com/", "retrieved_at": "2026-11-12", "published_at": None, "source_type": "company_site_candidate", "confidence": "low"}]}
        output = run_node(renderer, "renderCorporateReport(input.report,input.evidence,{execution_id:282,model:'gpt-4o-mini'})", {"report": report, "evidence": evidence})
        self.assertTrue(output.startswith("# Corporate Research Briefing — Shapesty GmbH\n"))
        for heading in ("Executive Summary", "Company Profile", "Business Model and Market Position", "Public Findings and Developments", "Analytical Observations", "Information Gaps", "Recommended Research Actions", "Sources and Limitations"):
            self.assertEqual(output.count("## " + heading), 1)
        self.assertNotIn("**##", output)
        self.assertIn("Shapesty & fitness", output)
        self.assertIn("<https://shapesty.com/>", output)
        self.assertNotIn("\\*\\*OpenRegister", output)
        self.assertIn("[WEB-1]", output)
        self.assertIn("(analytical inference)", output)

    def test_form_workflow_identity_and_evidence_validator_are_preserved(self):
        self.assertEqual(self.workflow["name"], "INCEPT — Company Research Agent")
        self.assertEqual(self.nodes["Company Research Form"]["parameters"]["options"]["path"], "incept-company-research")
        self.assertIn("company_name", self.nodes["Normalize Input"]["parameters"]["jsCode"])
        validator = self.nodes["Validate & Render Report"]["parameters"]["jsCode"]
        self.assertIn("unknown_source_id", validator)
        self.assertIn("claim_source_validation_failed", validator)
        self.assertIn("sources[x.source_id].kind!=='web_lead'", validator)
        self.assertIn("semantic_entailment:'not_automatically_verified'", validator)


if __name__ == "__main__":
    unittest.main()
