"""Offline checks for the isolated Project 3 n8n workflow export."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from projects.ironhack_project3.build_workflow import build, validate_layout


class Project3WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = build()
        self.nodes = {node["name"]: node for node in self.workflow["nodes"]}

    def test_both_triggers_feed_the_shared_input_and_pipeline(self):
        self.assertEqual(self.workflow["name"], "INCEPT — Company Research Agent")
        edges = self.workflow["connections"]
        self.assertEqual(edges["Webhook Trigger"]["main"][0][0]["node"], "Normalize Input")
        self.assertEqual(edges["Manual Trigger"]["main"][0][0]["node"], "Set Demo Company")
        self.assertEqual(edges["Set Demo Company"]["main"][0][0]["node"], "Normalize Input")
        demo = self.nodes["Set Demo Company"]["parameters"]["assignments"]["assignments"]
        values = {item["name"]: item["value"] for item in demo}
        self.assertEqual(values["company_name"], "SAP SE")
        self.assertEqual(values["register_identifier"], "")

    def test_webhook_uses_last_node_response_and_no_webhook_only_node(self):
        self.assertEqual(self.nodes["Webhook Trigger"]["parameters"]["responseMode"], "lastNode")
        self.assertEqual(self.nodes["Webhook Trigger"]["parameters"]["path"], "ironhack-company-research")
        self.assertFalse(any(node["type"].endswith("respondToWebhook") for node in self.nodes.values()))

    def test_browser_form_is_required_and_joins_the_shared_pipeline(self):
        form = self.nodes["Company Research Form"]
        self.assertEqual(form["type"], "n8n-nodes-base.formTrigger")
        self.assertEqual(form["parameters"]["formTitle"], "CompanyScope")
        self.assertIn("Company research, made simple.", form["parameters"]["formDescription"])
        self.assertEqual(
            form["parameters"]["formDescription"].replace("\\n", "\n"),
            "Company research, made simple.\nResearch German companies using official registry data, public web sources and AI-assisted analysis. Generate structured, source-referenced company reports in one workflow.",
        )
        self.assertEqual(form["parameters"]["options"]["path"], "incept-company-research")
        self.assertEqual(form["parameters"]["options"]["buttonLabel"], "Generate Company Report")
        self.assertTrue(form["parameters"]["options"]["customCss"])
        self.assertEqual(form["parameters"]["responseMode"], "lastNode")
        self.assertEqual(form["parameters"]["authentication"], "n8nUserAuth")
        self.assertTrue(form["parameters"]["requireExecuteAccess"])
        fields = form["parameters"]["formFields"]["values"]
        field = next(field for field in fields if field["fieldName"] == "company_name")
        self.assertEqual(field["fieldLabel"], "Company name")
        self.assertEqual(field["fieldName"], "company_name")
        self.assertTrue(field["requiredField"])
        register_field = next(field for field in fields if field["fieldName"] == "register_identifier")
        self.assertFalse(register_field["requiredField"])
        self.assertEqual(self.workflow["connections"]["Company Research Form"]["main"][0][0]["node"], "Normalize Input")
        self.assertIn("raw.formMode", self.nodes["Normalize Input"]["parameters"]["jsCode"])
        self.assertIn("Normalize Input", self.nodes["OpenRegister Search"]["parameters"]["url"])
        self.assertIn("company_name", self.nodes["OpenRegister Search"]["parameters"]["url"])
        self.assertEqual(self.nodes["Form Result"]["parameters"]["operation"], "completion")
        self.assertEqual(self.nodes["Form Result"]["parameters"]["respondWith"], "showText")
        self.assertIn("$json.form_html", self.nodes["Form Result"]["parameters"]["responseText"])
        self.assertNotIn("customCss", self.nodes["Form Result"]["parameters"]["options"])
        self.assertIn("const companyScopeCss=", self.nodes["Render Form Result"]["parameters"]["jsCode"])
        self.assertIn(".cs-report-shell", self.nodes["Render Form Result"]["parameters"]["jsCode"])
        self.assertIn("CompanyScope", self.nodes["Render Form Result"]["parameters"]["jsCode"])

    def test_premium_theme_is_css_only_responsive_and_uses_existing_form_selectors(self):
        css = self.nodes["Company Research Form"]["parameters"]["options"]["customCss"]
        self.assertIn("--color-background: #070a18", css)
        self.assertIn("radial-gradient", css)
        self.assertIn(".card", css)
        self.assertIn(".form-header h1", css)
        self.assertIn("font-size: clamp(1.5rem, 7vw, 3rem)", css)
        self.assertIn("font-size: clamp(1.5rem, 8vw, 2.4rem)", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("text-align: center", css)
        self.assertIn("overflow-x: hidden", css)
        self.assertIn(".form-input:focus", css)
        self.assertIn("#submit-btn:hover", css)
        self.assertIn("#submitted-form", css)
        self.assertIn("@media only screen and (max-width: 600px)", css)
        self.assertIn("prefers-reduced-motion", css)
        self.assertNotRegex(css, r"(?i)<\s*/?\s*(?:script|style|form|input|button)")
        self.assertNotRegex(css, r"(?i)@import|javascript:|url\s*\(")
        self.assertNotRegex(css, r"(?is)\.test-notice\s*\{[^}]*display\s*:\s*none")
        self.assertIn(".cs-report-shell", css)
        self.assertIn(".cs-report-section", css)
        self.assertIn("@media only screen and (max-width: 600px)", css)
        self.assertEqual(len(self.workflow["nodes"]), 34)

    def test_unknown_company_has_a_clear_failure_branch(self):
        false_branch = self.workflow["connections"]["Entity Match?"]["main"][1][0]["node"]
        self.assertEqual(false_branch, "Error: Entity")
        selection = self.nodes["Select Exact Entity"]["parameters"]["jsCode"]
        error = self.nodes["Error: Entity"]["parameters"]["jsCode"]
        self.assertIn("No exact or plausible OpenRegister company match", selection)
        self.assertIn("entrypoint", error)
        self.assertEqual(self.workflow["connections"]["Error: Entity"]["main"][0][0]["node"], "Form Error?")

    def test_success_path_validates_then_saves_and_returns_report(self):
        edges = self.workflow["connections"]
        self.assertEqual(edges["OpenAI Synthesis"]["main"][0][0]["node"], "Validate & Render Report")
        self.assertEqual(edges["Validation Passed?"]["main"][0][0]["node"], "Convert Report to File")
        self.assertEqual(edges["Convert Report to File"]["main"][0][0]["node"], "Save Markdown Report")
        self.assertEqual(edges["Save Markdown Report"]["main"][0][0]["node"], "Report Output")
        self.assertEqual(edges["Report Output"]["main"][0][0]["node"], "Form Success?")
        self.assertEqual(edges["Form Success?"]["main"][0][0]["node"], "Render Form Result")
        self.assertEqual(edges["Form Error?"]["main"][0][0]["node"], "Render Form Result")
        self.assertEqual(edges["Render Form Result"]["main"][0][0]["node"], "Form Result")

    def test_report_renderer_outputs_safe_html_and_truthful_failure_page(self):
        renderer = Path(__file__).resolve().parents[1] / "projects/ironhack_project3/form_report_renderer.js"
        theme = Path(__file__).resolve().parents[1] / "projects/ironhack_project3/form_theme.css"
        script = "const r=require(" + json.dumps(str(renderer)) + ");const fs=require('fs');const x=JSON.parse(process.argv[1]);const css=fs.readFileSync(" + json.dumps(str(theme)) + ", 'utf8');process.stdout.write(JSON.stringify(r.renderCompanyScopeResult(x,css)));"
        report = {
            "ok": True,
            "company": {"name": "Müller & Söhne GmbH"},
            "report_file": "report.md",
            "validation": {"source_ids_valid": True},
            "report_markdown": "# Bericht\n\n## Zusammenfassung\n\nPrüfung für Müller & Söhne. <script>alert(1)</script> **Wichtig**\n\n## Quellen\n\n- [Gesetz](https://example.de/law)\n- [gefälscht](javascript:alert(1))",
        }
        rendered = json.loads(subprocess.run(["node", "-e", script, json.dumps(report, ensure_ascii=False)], check=True, capture_output=True, text=True).stdout)
        self.assertIn("<h2>Zusammenfassung</h2>", rendered)
        self.assertIn("Müller &amp; Söhne", rendered)
        self.assertIn("<strong>Wichtig</strong>", rendered)
        self.assertIn("<style>", rendered)
        self.assertIn(".cs-report-section", rendered)
        self.assertIn("class=\"cs-report-section\"", rendered)
        self.assertNotIn("<script>", rendered)
        self.assertIn("href=\"https://example.de/law\"", rendered)
        self.assertIn(">Gesetz</a>", rendered)
        self.assertNotIn(">https://example.de/law</a>", rendered)
        self.assertNotIn("href=\"javascript:", rendered)
        self.assertIn("Markdown report saved", rendered)

        failure = {"ok": False, "error_code": "exact_company_match_not_found", "message": "No verified match"}
        error_html = json.loads(subprocess.run(["node", "-e", script, json.dumps(failure)], check=True, capture_output=True, text=True).stdout)
        self.assertIn("Research not completed", error_html)
        self.assertNotIn("Research complete", error_html)

    def test_layout_and_all_connection_references_are_valid(self):
        validate_layout(self.workflow["nodes"], self.workflow["connections"])
        positions = [tuple(node["position"]) for node in self.nodes.values()]
        self.assertEqual(len(positions), len(set(positions)))
        for source, ports in self.workflow["connections"].items():
            self.assertIn(source, self.nodes)
            for output in ports["main"]:
                for edge in output:
                    self.assertIn(edge["node"], self.nodes)

    def test_sanitized_export_matches_deterministic_builder(self):
        exported = json.loads((Path(__file__).resolve().parents[1] / "projects/ironhack_project3/workflow.json").read_text())
        self.assertEqual(exported["nodes"], self.workflow["nodes"])
        self.assertEqual(exported["connections"], self.workflow["connections"])


if __name__ == "__main__":
    unittest.main()
