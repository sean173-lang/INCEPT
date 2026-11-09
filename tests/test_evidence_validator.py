"""Offline fixtures: no live providers or API credits."""
import copy
import json
import unittest
from offline_support import OfflineTestCase
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

from scripts.evidence_validator import classify_source, validate_evidence
from scripts import legalflow_agent as agent


PROFILE = {"company_name": "Example Limited", "company_number": "01234567",
           "date_of_creation": "2020-01-02", "company_status": "active"}


def company():
    return {"country": "UK", "name": "Example Limited", "company_number": "01234567",
            "incorporated": "2020-01-02", "original_api_data": {"profile": dict(PROFILE)}}


def validate(sources=(), data=None):
    return validate_evidence(data or company(), {"sources": list(sources)}, today=date(2026, 11, 9))


def source(**kwargs):
    return {"title": "Example Limited", "content": "Example Limited pending lawsuit",
            "url": "https://www.gov.uk/example", **kwargs}


class EvidenceTests(OfflineTestCase):
    def test_registry_identity_and_dates(self):
        result = validate()
        self.assertTrue(all(result["registry_checks"].values()))
        changed = company()
        changed.update(name="Other Limited", company_number="99999999", incorporated="2021-01-02")
        self.assertFalse(any(validate(data=changed)["registry_checks"].values()))

    def test_missing_original_evidence(self):
        data = company()
        data.pop("original_api_data")
        self.assertFalse(any(validate(data=data)["registry_checks"].values()))

    def test_identity_exclusion(self):
        for item in (source(company_number="99999999"), source(company_name="Other Limited"),
                     source(content="Example Limited company number: 99999999")):
            result = validate([item])["sources"][0]
            self.assertEqual(result["identity"], "unrelated")
            self.assertFalse(result["usable"])
        result = validate([source(title="Other Limited", content="Unrelated business")])
        self.assertEqual(result["sources"][0]["identity"], "unverified")

    def test_registration_match_is_not_verified_finding(self):
        item = validate([source(company_number="01234567")])["sources"][0]
        self.assertTrue(item["registration_number_match"])
        self.assertFalse(item["verified_legal_finding"])

    def test_host_classification(self):
        self.assertEqual(classify_source("https://www.gov.uk/path"), "official")
        for url in ("https://gov.uk.evil.example", "https://notgov.uk", "https://openregister.de"):
            self.assertEqual(classify_source(url), "third_party")
        for url in ("javascript:alert(1)", "https://gov.uk@evil.example", "https://["):
            self.assertEqual(classify_source(url), "unknown")

    def test_dates(self):
        values = [(None, "unknown"), ("nonsense", "unknown"), ("2020-01-01", "outdated"),
                  ("2026-11-01", "recent"), ("2027-01-01", "invalid_future_date")]
        for value, expected in values:
            with self.subTest(value=value):
                self.assertEqual(validate([source(published_date=value)])["sources"][0]["freshness"], expected)

    def test_legal_status_remains_unverified(self):
        for content, status in [("alleged fraud; case settled", "historical_unverified"),
                                ("pending litigation", "ongoing_unverified"),
                                ("case dismissed; another pending", "conflicting_unverified")]:
            item = validate([source(content="Example Limited " + content)])["sources"][0]
            self.assertEqual(item["litigation_status"], status)
            self.assertFalse(item["verified_legal_finding"])
        self.assertEqual(validate([source(content="Example Limited alleged fraud")])["sources"][0]["legal_evidence"], "unverified_allegation")

    def test_never_infer_low_risk(self):
        for sources in ([], [source(content="Example Limited has no adverse news")]):
            self.assertEqual(validate(sources)["risk_assessment"], "Undetermined")

    def test_officer_and_filing_dates_against_original(self):
        data = company()
        data["officers"] = [{"name": "Director", "role": "director", "appointed_on": "2022-01-01"}]
        data["recent_filings"] = [{"date": "2023-01-01", "type": "AA", "description": "accounts"}]
        data["original_api_data"].update(officers={"items": [{"name": "Director", "officer_role": "director", "appointed_on": "2022-01-01"}]}, filings={"items": copy.deepcopy(data["recent_filings"])})
        self.assertTrue(all(c["verified"] for c in validate(data=data)["date_checks"]))
        data["officers"][0]["appointed_on"] = "2025-01-01"
        data["recent_filings"][0]["date"] = "2025-01-01"
        self.assertEqual([c["verified"] for c in validate(data=data)["date_checks"]], [True, False, False])

    def test_german_provider_id_and_registration(self):
        data = {"country": "Germany", "name": "Example GmbH", "company_number": "provider-id",
                "register_number": "HRB 123", "register_court": "Berlin", "incorporated": "2020-01-02",
                "original_api_data": {"company": {"id": "provider-id", "name": {"name": "Example GmbH"},
                "incorporated_at": "2020-01-02T00:00:00Z", "company_register": {"register_number": "HRB 123", "register_court": "Berlin"}}}}
        self.assertTrue(all(validate(data=data)["registry_checks"].values()))
        data["register_court"] = "Hamburg"
        self.assertFalse(validate(data=data)["registry_checks"]["register_court"])

    @patch.object(agent, "get_filing_history", return_value={"items": []})
    @patch.object(agent, "get_company_officers", return_value={"items": []})
    @patch.object(agent, "get_company_profile", return_value=PROFILE)
    @patch.object(agent, "search_company", return_value={"items": [{"title": "Example Limited", "company_number": "01234567"}]})
    def test_mocked_registry_pipeline(self, *_):
        data = agent.get_uk_company("Example Limited")
        self.assertTrue(all(validate(data=data)["registry_checks"].values()))
        self.assertTrue(data["retrieved_at"].endswith("+00:00"))

    @patch.object(agent, "get_company")
    def test_mocked_german_response_retained(self, get_company):
        raw = {"id": "provider-id", "name": {"name": "Example GmbH"}}
        get_company.return_value.model_dump.return_value = raw
        get_company.return_value.retrieved_at = "2026-11-09T00:00:00+00:00"
        data = agent.get_german_company("provider-id")
        self.assertEqual(data["original_api_data"], {"company": raw})
        self.assertTrue(data["retrieved_at"].endswith("+00:00"))

    @patch.object(agent, "OpenAI")
    def test_validation_precedes_mocked_analysis(self, client):
        client.return_value.responses.create.return_value = SimpleNamespace(output_text="Research report")
        data = company()
        research = {"sources": [source(company_number="99999999"), source()]}
        original = copy.deepcopy(research)
        report = agent.generate_ai_report(data, research)
        payload = json.loads(client.return_value.responses.create.call_args.kwargs["input"])
        self.assertEqual(len(payload["web_research"]), 1)
        self.assertEqual(payload["evidence_verification"]["risk_assessment"], "Undetermined")
        self.assertIn("**Undetermined**", report)
        self.assertEqual(research, original)


if __name__ == "__main__":
    unittest.main()
