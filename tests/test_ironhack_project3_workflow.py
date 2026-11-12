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

    def test_success_path_validates_then_saves_and_returns_report(self):
        edges = self.workflow["connections"]
        self.assertEqual(edges["OpenAI Synthesis"]["main"][0][0]["node"], "Validate & Render Report")
        self.assertEqual(edges["Validation Passed?"]["main"][0][0]["node"], "Convert Report to File")
        self.assertEqual(edges["Convert Report to File"]["main"][0][0]["node"], "Save Markdown Report")
        self.assertEqual(edges["Save Markdown Report"]["main"][0][0]["node"], "Report Output")

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
