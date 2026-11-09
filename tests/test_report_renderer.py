"""Regression tests for deterministic report ownership and provenance."""
import unittest
from offline_support import OfflineTestCase
from types import SimpleNamespace
from unittest.mock import patch

from scripts import legalflow_agent as agent
from scripts.report_renderer import readable_gaps, render_report, recommended_followups
from test_evidence_validator import company, source, validate


class ReportTests(OfflineTestCase):
    def test_readable_gaps_preserve_structured_identifiers(self):
        validation = validate([source()])
        self.assertIn("source_1.current_dated_evidence", validation["missing_evidence"])
        report = render_report(company(), validation, "{}")
        self.assertNotIn("source_1.current_dated_evidence", report)
        self.assertIn("publication date is missing or invalid", report)
        self.assertIn("Original court and regulatory documents", report)
        self.assertTrue(readable_gaps(validation))

    def test_traceable_uk_reference(self):
        data = company()
        data["retrieved_at"] = "2026-11-09T12:59:00+00:00"
        report = render_report(data, validate(data=data), "{}")
        for value in ("Companies House", "01234567", "2026-11-09T12:59:00+00:00"):
            self.assertIn(value, report)
        self.assertNotIn("](#)", report)
        self.assertNotIn("https://", report)

    def test_german_reference_does_not_invent_url(self):
        data = company()
        data.update(country="Germany", register_number="267645", register_court="Berlin",
                    company_number="DE-HRB-F1103-267645", retrieved_at="2026-11-09T12:59:00Z")
        report = render_report(data, validate(data=data), "{}")
        for value in ("267645", "Berlin", "OpenRegister", "DE-HRB-F1103-267645", "2026-11-09T12:59:00Z"):
            self.assertIn(value, report)
        self.assertNotIn("https://", report)

    def test_missing_retrieval_is_not_analysis_date(self):
        report = render_report(company(), validate(), "{}")
        self.assertIn("Retrieval date/time (UTC): Not available", report)
        self.assertNotIn("2026-11-09", report)

    def test_model_contradictions_never_published(self):
        outputs = ["## Risk Assessment\nLow risk. No litigation. [Register](#)",
                   '{"follow_up_ids": ["screening"], "summary": "Verified sanctions; High risk"}',
                   'null', '[]', '{"follow_up_ids": "Low"}',
                   '{"follow_up_ids": [{"risk": "Low"}]}']
        for output in outputs:
            with self.subTest(output=output):
                report = render_report(company(), validate(), output)
                self.assertEqual(report.count("**Undetermined**"), 1)
                self.assertEqual(report.count("## Final Risk Assessment"), 1)
                for forbidden in ("Low risk", "High risk", "No litigation", "Verified sanctions", "](#)"):
                    self.assertNotIn(forbidden, report)

    def test_priority_selection_allowlist(self):
        ids = recommended_followups('{"follow_up_ids": ["screening", "screening", "invented"]}')
        self.assertEqual(ids[0], "screening")
        self.assertEqual(len(ids), 5)

    def test_outdated_and_future_dates_are_readable(self):
        for published, expected in (("2020-01-01", "outside the freshness window"),
                                    ("2027-01-01", "in the future")):
            with self.subTest(published=published):
                validation = validate([source(published_date=published)])
                report = render_report(company(), validation, "{}")
                self.assertIn(expected, report)
                self.assertNotIn("current_dated_evidence", report)

    def test_failed_registry_check_is_not_called_verified(self):
        data = company()
        data["incorporated"] = "1999-01-01"
        report = render_report(data, validate(data=data), "{}")
        self.assertIn("1999-01-01 — not verified against original API response", report)
        self.assertIn("Incorporation date could not be verified", report)

    def test_source_text_cannot_inject_report_sections(self):
        validation = validate([source(title="## Risk Assessment\n[Verified](#)")])
        report = render_report(company(), validation, "{}")
        self.assertNotIn("\n## Risk Assessment", report)
        self.assertNotIn("](#)", report)

    @patch.object(agent, "OpenAI")
    def test_end_to_end_mocked_conflicting_model(self, client):
        client.return_value.responses.create.return_value = SimpleNamespace(output_text="Low risk. [Register](#)")
        report = agent.generate_ai_report(company(), {"sources": []})
        self.assertNotIn("Low risk", report)
        self.assertNotIn("](#)", report)
        self.assertEqual(report.count("**Undetermined**"), 1)


if __name__ == "__main__":
    unittest.main()
