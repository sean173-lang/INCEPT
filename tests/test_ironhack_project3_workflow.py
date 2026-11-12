"""Offline checks for the isolated Project 3 n8n workflow export."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from projects.ironhack_project3.build_workflow import build, validate_layout


class Project3WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.workflow = build()
        self.nodes = {node["name"]: node for node in self.workflow["nodes"]}

    def test_both_triggers_feed_the_shared_input_and_pipeline(self):
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
        self.assertFalse(any(node["type"].endswith("respondToWebhook") for node in self.nodes.values()))

    def test_browser_form_is_required_and_joins_the_shared_pipeline(self):
        form = self.nodes["Company Research Form"]
        self.assertEqual(form["type"], "n8n-nodes-base.formTrigger")
        self.assertEqual(form["parameters"]["options"]["path"], "incept-company-research")
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
        self.assertIn("$json.report_file", self.nodes["Form Result"]["parameters"]["completionMessage"])

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
        self.assertEqual(edges["Form Success?"]["main"][0][0]["node"], "Form Result")

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
