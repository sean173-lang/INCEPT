"""All provider responses, document downloads and financial figures are mocked."""
import copy
import json
import sys
import unittest
from offline_support import OfflineTestCase
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from scripts.financial_analysis import analyze_financials, normalize_openregister, number
from scripts.accounts_parser import parse_accounts
from scripts.due_diligence import build_issues, financials_for_company
from scripts import companies_house as uk, german_register as de, legalflow_agent as agent
from scripts.report_renderer import render_report
from test_evidence_validator import company, validate


def period(year=2024, **values):
    figures = {"revenue": 100, "net_income": 10, "total_assets": 200, "equity": 50,
               "liabilities": 150, "current_assets": 30, "current_liabilities": 60, "cash": 15}
    figures.update(values)
    return {"period_start": f"{year}-01-01", "period_end": f"{year}-12-31", "scope": "standalone",
            "source": "mock://signed-accounts", "facts": {k: {"value": v, "currency": "EUR", "scale": 1} for k, v in figures.items()}}


def dataset(*periods):
    return {"provider": "mock fixture", "company_id": "01234567", "status": "available", "periods": list(periods)}


def xbrl(company_id="01234567", value="100", extra=""):
    return f'''<xbrli:xbrl xmlns:xbrli="http://www.xbrl.org/2003/instance"
      xmlns:iso4217="http://www.xbrl.org/2003/iso4217" xmlns:uk="http://xbrl.frc.org.uk/fr/2024-01-01/core">
      <xbrli:context id="duration"><xbrli:entity><xbrli:identifier scheme="https://www.companieshouse.gov.uk/">{company_id}</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:startDate>2024-01-01</xbrli:startDate><xbrli:endDate>2024-12-31</xbrli:endDate></xbrli:period></xbrli:context>
      <xbrli:context id="instant"><xbrli:entity><xbrli:identifier scheme="https://www.companieshouse.gov.uk/">{company_id}</xbrli:identifier></xbrli:entity>
      <xbrli:period><xbrli:instant>2024-12-31</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:unit id="GBP"><xbrli:measure>iso4217:GBP</xbrli:measure></xbrli:unit>
      <uk:Revenue contextRef="duration" unitRef="GBP">{value}</uk:Revenue>
      <uk:Assets contextRef="instant" unitRef="GBP">200</uk:Assets>{extra}</xbrli:xbrl>'''.encode()


class FinancialTests(OfflineTestCase):
    def test_ratios_decimal_and_zero(self):
        data = analyze_financials(dataset(period()))
        ratios = data["periods"][0]["ratios"]
        self.assertEqual(ratios["equity_ratio"]["value"], "0.25")
        self.assertEqual(ratios["net_margin"]["value"], "0.1")
        self.assertEqual(ratios["current_ratio"]["value"], "0.5")
        self.assertIn("Current ratio below 1", data["indicators"][0]["description"])
        zero = analyze_financials(dataset(period(revenue=0, total_assets=0)))
        self.assertIsNone(zero["periods"][0]["ratios"]["net_margin"]["value"])
        self.assertIsNone(zero["periods"][0]["ratios"]["equity_ratio"]["value"])

    def test_missing_units_no_inference(self):
        p = period()
        p["facts"]["equity"]["currency"] = None
        p["facts"]["revenue"]["scale"] = None
        result = analyze_financials(dataset(p))["periods"][0]
        self.assertIsNone(result["ratios"]["equity_ratio"]["value"])
        self.assertIsNone(result["ratios"]["net_margin"]["value"])
        self.assertEqual(result["facts"]["ebitda"]["availability"], "unavailable")

    def test_incompatible_currency_and_negative_denominators(self):
        p = period(revenue=-10)
        p["facts"]["equity"]["currency"] = "GBP"
        result = analyze_financials(dataset(p))["periods"][0]
        self.assertIsNone(result["ratios"]["equity_ratio"]["value"])
        self.assertIsNone(result["ratios"]["net_margin"]["value"])

    def test_trends_and_unit_normalization(self):
        older = period(2023, revenue=1000)
        newer = period(2024, revenue=0.8, net_income=-5, equity=-10)
        newer["facts"]["revenue"]["scale"] = 1000
        result = analyze_financials(dataset(newer, older))
        change = result["comparisons"][0]["changes"]["revenue"]
        self.assertEqual(change["absolute_change"], "-200.0")
        self.assertEqual(number(change["percent_change"]), -20)
        descriptions = [i["description"] for i in result["indicators"]]
        self.assertIn("Negative reported equity", descriptions)
        self.assertIn("Reported net loss", descriptions)
        self.assertTrue(any("revenue declined" in d for d in descriptions))

    def test_unequal_scope_short_year_and_periods(self):
        for key, value in (("scope", "consolidated"), ("scope", "unknown"),
                           ("short_year", True), ("period_start", "2024-07-01")):
            p = period()
            p[key] = value
            result = analyze_financials(dataset(period(2023), p))
            self.assertTrue(result["comparisons"][0]["reason"])
            self.assertIsNone(result["comparisons"][0]["changes"]["revenue"]["absolute_change"])

    def test_nonfinite_values_and_missing_data(self):
        for v in (True, None, "NaN", "Infinity", "invented", "1,000"):
            self.assertIsNone(number(v))
        self.assertEqual(analyze_financials()["periods"], [])
        self.assertEqual(analyze_financials({"raw": {"estimates": {"revenue": 999}}})["periods"], [])

    def test_openregister_documented_shape_excludes_estimates(self):
        raw = {"reports": [{"report_id": "r1", "consolidated": False,
                            "report_start_date": "2024-01-01", "report_end_date": "2024-12-31",
                            "sources": [{"html_url": "https://example.org/actual-returned-report"}]}],
               "indicators": [{"report_id": "r1", "date": "2024-12-31", "balance_sheet_total": 100, "equity": -20}],
               "estimates": {"revenue": {"value": 1000000}}}
        original = copy.deepcopy(raw)
        periods = normalize_openregister(raw, "mock://api")
        self.assertEqual(periods[0]["facts"]["total_assets"]["value"], "100")
        self.assertNotIn("revenue", periods[0]["facts"])
        self.assertIsNone(periods[0]["facts"]["equity"]["currency"])
        self.assertEqual(raw, original)
        result = analyze_financials({"provider": "OpenRegister", "status": "available", "raw": raw})
        self.assertIsNone(result["periods"][0]["ratios"]["equity_ratio"]["value"])

    def test_conflicting_and_future_periods(self):
        for change in ({"period_conflict": True}, {"period_end": "2099-12-31"}, {"period_end": "bad"}):
            p = period()
            p.update(change)
            result = analyze_financials(dataset(p))["periods"][0]
            self.assertFalse(result["valid_period"])
            self.assertIsNone(result["ratios"]["net_margin"]["value"])

    def test_financial_identity_binding(self):
        data = company()
        data["financial_data"] = {**dataset(period()), "company_id": "WRONG"}
        self.assertEqual(financials_for_company(data, validate(data=data))["status"], "excluded")

    def test_not_requested_is_not_identity_exclusion(self):
        data = company()
        data["financial_data"] = {"status": "not_requested"}
        self.assertEqual(financials_for_company(data, validate(data=data))["status"], "not_requested")

    def test_invalid_start_date_and_duplicate_periods(self):
        p = period()
        p["period_start"] = "invalid"
        self.assertFalse(analyze_financials(dataset(p))["periods"][0]["valid_period"])
        result = analyze_financials(dataset(period(2023), period(2023), period(2024)))
        self.assertTrue(all("Multiple reports" in c["reason"] for c in result["comparisons"]))

    def test_issues_and_report_sections(self):
        data = company()
        data["financial_data"] = dataset(period(equity=-1))
        validation = validate(data=data)
        financials = financials_for_company(data, validation)
        issues = build_issues(data, validation, financials)
        for issue in issues:
            for field in ("description", "supporting_evidence", "source", "potential_legal_significance",
                          "recommended_follow_up", "verification_status"):
                self.assertIn(field, issue)
        self.assertTrue(any(i["category"] == "financial_indicator" for i in issues))
        report = render_report(data, validation, "Low risk: invented profit 99999")
        for heading in ("Executive Summary", "Corporate Structure", "Financial Analysis", "Legal and Regulatory Findings",
                        "Due Diligence Issues List", "Document Request List", "Transaction Considerations", "Sources and Limitations"):
            self.assertIn("## " + heading, report)
        self.assertEqual(report.count("**Undetermined**"), 1)
        self.assertNotIn("99999", report)

    @patch.object(agent, "OpenAI")
    def test_financial_analysis_in_model_payload_without_bytes(self, client):
        client.return_value.responses.create.return_value = SimpleNamespace(output_text='{"follow_up_ids":["financials"]}')
        data = company()
        data["financial_data"] = {**dataset(period()), "document_content": b"not model input"}
        report = agent.generate_ai_report(data, {"sources": []})
        payload = json.loads(client.return_value.responses.create.call_args.kwargs["input"])
        self.assertEqual(payload["financial_analysis"]["periods"][0]["ratios"]["equity_ratio"]["value"], "0.25")
        self.assertNotIn("document_content", json.dumps(payload))
        self.assertIn("Financial Analysis", report)


class ParserTests(OfflineTestCase):
    def test_xbrl_exact_company_period_unit(self):
        periods = parse_accounts(xbrl(), "01234567", "mock://account")
        self.assertEqual(len(periods), 1)
        self.assertEqual(periods[0]["period_start"], "2024-01-01")
        self.assertEqual(periods[0]["facts"]["revenue"]["currency"], "GBP")
        self.assertEqual(periods[0]["facts"]["total_assets"]["value"], "200")
        self.assertEqual(parse_accounts(xbrl("99999999"), "01234567", "mock"), [])

    def test_conflicting_duplicate_facts_and_unsupported_input(self):
        content = xbrl(extra='<uk:Revenue contextRef="duration" unitRef="GBP">999</uk:Revenue>')
        self.assertIsNone(parse_accounts(content, "01234567", "mock")[0]["facts"]["revenue"]["value"])
        for raw in (b"%PDF-1.4", b"not XML", b'<!DOCTYPE foo [<!ENTITY a "x">]><foo/>'):
            self.assertEqual(parse_accounts(raw, "01234567", "mock"), [])

    def test_ixbrl_scale_and_sign(self):
        raw = xbrl().decode().replace('<xbrli:xbrl ', '<xbrli:xbrl xmlns:ix="http://www.xbrl.org/2013/inlineXBRL" ')
        raw = raw.replace('<uk:Revenue contextRef="duration" unitRef="GBP">100</uk:Revenue>',
                          '<ix:nonFraction name="uk:Revenue" contextRef="duration" unitRef="GBP" scale="3" sign="-">2</ix:nonFraction>')
        facts = parse_accounts(raw.encode(), "01234567", "mock")[0]["facts"]
        self.assertEqual(facts["revenue"]["value"], "-2")
        self.assertEqual(facts["revenue"]["scale"], "1000")


class RetrievalTests(OfflineTestCase):
    @patch.object(de, "API_KEY", "mock-key")
    @patch("requests.get")
    def test_no_automatic_paid_calls(self, request):
        self.assertEqual(de._get_financials("id")["status"], "not_requested")
        request.assert_not_called()
        self.assertEqual(uk.get_annual_accounts("01234567")["status"], "not_requested")
        request.assert_not_called()

    @patch.object(de, "API_KEY", "mock-key")
    @patch("requests.get")
    def test_openregister_rest_no_sdk(self, request):
        request.return_value.status_code = 200
        request.return_value.json.return_value = {"indicators": [{"date": "2024-12-31", "revenue": 0}]}
        with patch.dict(sys.modules, {"openregister": None}):
            result = de._get_financials("DE-id", allow_paid=True)
        self.assertEqual(result["status"], "available")
        request.assert_called_once()
        self.assertTrue(request.call_args.args[0].endswith("/v1/company/DE-id/financials"))
        self.assertFalse(request.call_args.kwargs["allow_redirects"])

    @patch.object(de, "API_KEY", "mock-key")
    @patch("requests.get")
    def test_sdk_supported_and_no_fallback_on_failure(self, request):
        sdk = MagicMock()
        sdk.company.get_financials_v1.return_value.model_dump.return_value = {"reports": [], "indicators": []}
        factory = MagicMock(return_value=sdk)
        with patch.dict(sys.modules, {"openregister": SimpleNamespace(Openregister=factory)}):
            self.assertEqual(de._get_financials("id", allow_paid=True)["status"], "unavailable")
            sdk.company.get_financials_v1.side_effect = RuntimeError("secret request details")
            result = de._get_financials("id", allow_paid=True)
            self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
        request.assert_not_called()

    @patch.object(de, "API_KEY", "mock-key")
    @patch("requests.get")
    def test_older_sdk_missing_method_uses_rest(self, request):
        request.return_value.status_code = 200
        request.return_value.json.return_value = {"indicators": []}
        factory = MagicMock(return_value=SimpleNamespace(company=SimpleNamespace()))
        with patch.dict(sys.modules, {"openregister": SimpleNamespace(Openregister=factory)}):
            de._get_financials("id", allow_paid=True)
        request.assert_called_once()

    @patch.object(de, "API_KEY", "mock-key")
    @patch("requests.get")
    def test_rest_errors_not_retried(self, request):
        for status in (403, 404, 429, 500):
            request.reset_mock()
            request.return_value.status_code = status
            with patch.dict(sys.modules, {"openregister": None}):
                result = de._get_financials("id", allow_paid=True)
            self.assertEqual(result["status"], "unavailable")
            request.assert_called_once()

    @patch.object(uk, "api_request", return_value={"items": []})
    def test_accounts_specific_bounded_query(self, request):
        result = uk.get_annual_accounts("01234567", enabled=True)
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(request.call_args.kwargs["params"], {"category": "accounts", "items_per_page": 5, "start_index": 0})

    @patch.object(uk, "download_account_document")
    @patch.object(uk, "get_document_metadata")
    @patch.object(uk, "get_account_filings")
    def test_one_document_and_pdf_limitation(self, filings, metadata, download):
        link = uk.DOCUMENT_BASE_URL + "/document/abc"
        filings.return_value = {"items": [{"category": "accounts", "links": {"document_metadata": link}}] * 20}
        metadata.return_value = {"resources": {"application/pdf": {"content_length": 100}}}
        download.return_value = b"%PDF-1.4 mock"
        result = uk.get_annual_accounts("01234567", enabled=True, download=True)
        self.assertEqual(len(result["documents"]), 5)
        self.assertEqual(result["status"], "document_only")
        download.assert_called_once()
        self.assertEqual(result["periods"], [])

    @patch.object(uk, "download_account_document", return_value=xbrl())
    @patch.object(uk, "get_document_metadata", return_value={"resources": {"application/xml": {"content_length": 1000}}})
    @patch.object(uk, "get_account_filings")
    def test_mocked_machine_readable_accounts_end_to_end(self, filings, metadata, download):
        filings.return_value = {"items": [{"category": "accounts", "links": {"document_metadata": uk.DOCUMENT_BASE_URL + "/document/a"}}]}
        result = uk.get_annual_accounts("01234567", enabled=True, download=True)
        self.assertEqual(result["status"], "available")
        self.assertEqual(result["periods"][0]["facts"]["revenue"]["value"], "100")
        self.assertEqual(result["document_content"], xbrl())
        self.assertEqual(analyze_financials(result)["periods"][0]["normalized_values"]["total_assets"]["currency"], "GBP")

    @patch.object(uk, "download_account_document")
    @patch.object(uk, "get_document_metadata")
    @patch.object(uk, "get_account_filings")
    def test_metadata_only_never_downloads(self, filings, metadata, download):
        filings.return_value = {"items": [{"category": "accounts"}]}
        result = uk.get_annual_accounts("01234567", enabled=True)
        self.assertEqual(result["status"], "metadata_only")
        metadata.assert_not_called()
        download.assert_not_called()

    @patch.object(uk, "download_account_document")
    @patch.object(uk, "get_document_metadata", return_value={"resources": {"application/xml": {"content_length": 9_000_000}}})
    @patch.object(uk, "get_account_filings")
    def test_large_file_not_downloaded(self, filings, metadata, download):
        filings.return_value = {"items": [{"category": "accounts", "links": {"document_metadata": uk.DOCUMENT_BASE_URL + "/document/a"}}]}
        result = uk.get_annual_accounts("01234567", enabled=True, download=True)
        self.assertIn("exceeds", result["reason"])
        download.assert_not_called()

    @patch("requests.get")
    def test_untrusted_document_host_rejected(self, request):
        for url in ("https://evil.example/document/a", "https://document-api.company-information.service.gov.uk.evil.example/document/a"):
            with self.assertRaises(ValueError):
                uk.get_document_metadata(url)
        request.assert_not_called()

    @patch("requests.get")
    def test_bounded_stream_and_storage_redirect_no_credentials(self, request):
        initial, storage = MagicMock(), MagicMock()
        initial.status_code = 302
        initial.headers = {"Location": "https://storage.example/actual-signed-location"}
        storage.status_code = 200
        storage.headers = {}
        storage.iter_content.return_value = iter([b"abc", b"def"])
        request.side_effect = [MagicMock(__enter__=MagicMock(return_value=initial)), MagicMock(__enter__=MagicMock(return_value=storage))]
        with self.assertRaises(ValueError):
            uk.download_account_document(uk.DOCUMENT_BASE_URL + "/document/a", "application/xml", max_bytes=5)
        self.assertNotIn("auth", request.call_args.kwargs)
        self.assertFalse(request.call_args.kwargs["allow_redirects"])


if __name__ == "__main__":
    unittest.main()
