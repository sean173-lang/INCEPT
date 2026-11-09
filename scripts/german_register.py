import os
import json
from dotenv import load_dotenv
from scripts.financial_errors import classify_financial_404
from scripts.api_usage import get_tracker, RegistryRecord, UsageBlocked

# ==========================================
# LEGALFLOW — German Company Register
# ==========================================

load_dotenv()

API_KEY = os.getenv("OPENREGISTER_API_KEY")


def get_client():
    from openregister import Openregister
    if not API_KEY:
        raise ValueError(
            "Missing OPENREGISTER_API_KEY in .env"
        )

    return Openregister(api_key=API_KEY, max_retries=0, timeout=30)


# ==========================================
# 1. GET COMPANY INFORMATION
# ==========================================

def get_company(company_id):
    from datetime import datetime, timezone
    from scripts.development_fixtures import german_company
    def retrieve():
        client = get_client()
        raw = client.company.get_details_v1(company_id=company_id).model_dump(mode="json")
        return {"payload": raw, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    raw = get_tracker().execute("OpenRegister", "company_details", company_id, retrieve,
                                cache=True, mock=lambda: {"payload": german_company(company_id), "retrieved_at": None})
    return RegistryRecord(raw["payload"], retrieved_at=raw["retrieved_at"])


# ==========================================
# 2. DISPLAY COMPANY INFORMATION
# ==========================================

def display_company(company):

    print("\n" + "=" * 55)
    print("LEGALFLOW — GERMAN COMPANY REPORT")
    print("=" * 55)

    print("\nCOMPANY INFORMATION")
    print("-" * 55)

    for field in [
        "name",
        "id",
        "legal_form",
        "status",
        "address",
        "registration",
        "management"
    ]:
        value = getattr(company, field, None)

        if value is not None:
            print(f"{field}: {value}")

    print("\nFULL API RESPONSE")
    print("-" * 55)

    if hasattr(company, "model_dump"):
        data = company.model_dump(mode="json")
    else:
        data = vars(company)

    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    print("\n" + "=" * 55)


# ==========================================
# 3. MAIN APPLICATION
# ==========================================

def main():

    print("\nWelcome to LEGALFLOW")
    print("German Corporate Due Diligence")
    print("----------------------------------")

    company_id = input(
        "\nEnter OpenRegister company ID: "
    ).strip()

    if not company_id:
        print("Please enter a company ID.")
        return

    print("\nRetrieving German company data...")

    company = get_company(company_id)

    display_company(company)




def _financial_failure(result, code, message, *, status_code=None, stage=None):
    """Log allowlisted diagnostics only: never exception text, bodies or headers."""
    reason = message + " No retry performed. Financial-statement availability remains unknown."
    print(f"[OpenRegister financials] {code} (stage: {stage or 'unknown'}): {reason}")
    return {**result, "status": "unavailable", "error_code": code,
            "http_status": status_code, "failure_stage": stage, "reason": reason,
            "plan_access": "unconfirmed", "request_status": "failed",
            "financial_data_status": "unknown", "publication_status": "unknown"}


def _financial_http_failure(result, status, *, stage="request", body=None):
    if status == 404:
        classification = classify_financial_404(body)
        cause = classification["not_found_cause"]
        messages_404 = {
            "company_not_found": "HTTP 404: provider explicitly reports company not found; verify the provider company identifier.",
            "financial_dataset_not_found": "HTTP 404: provider explicitly reports financial dataset not found; data is unavailable through this provider, not necessarily unpublished.",
            "endpoint_not_found": "HTTP 404: provider explicitly reports endpoint or route not found; verify the route and SDK version.",
            "unknown": "HTTP 404: cause unknown; the response does not specifically identify a missing company, financial dataset or route.",
        }
        failure = _financial_failure(result, "invalid_endpoint" if cause == "endpoint_not_found" else cause if cause != "unknown" else "not_found",
                                     messages_404[cause], status_code=status, stage=stage)
        return {**failure, **classification, "financial_data_status": "provider_unavailable" if cause == "financial_dataset_not_found" else "unknown"}

    messages = {
        401: ("authentication_failed", "HTTP 401: authentication failed; verify the configured API key."),
        402: ("credits_or_billing_required", "HTTP 402: payment or credits required; check account billing and quota."),
        403: ("permission_denied", "HTTP 403: insufficient permissions; verify endpoint entitlement and account restrictions. This alone does not identify your plan."),
        404: ("not_found", "HTTP 404: company, financial resource or route not found; this does not prove that no statements exist."),
        429: ("rate_limited", "HTTP 429: rate limiting or request quota reached; check provider usage before a manual retest."),
    }
    if status in (405, 410, 501):
        code, message = "invalid_endpoint", f"HTTP {status}: endpoint or operation unavailable; verify the documented route and SDK version."
    elif status in messages:
        code, message = messages[status]
    elif 300 <= status < 400:
        code, message = "unexpected_redirect", f"HTTP {status}: unexpected redirect refused to protect credentials."
    elif status >= 500:
        code, message = "provider_error", f"HTTP {status}: provider service error."
    else:
        code, message = "http_error", f"HTTP {status}: financial request rejected."
    return _financial_failure(result, code, message, status_code=status, stage=stage)


def _validate_financial_payload(raw):
    """Reject error envelopes and malformed shapes rather than calling them no data."""
    if not isinstance(raw, dict) or not any(k in raw for k in ("reports", "indicators")):
        raise ValueError("Unsupported financial envelope")
    normalized = dict(raw)
    for field in ("reports", "indicators"):
        rows = raw.get(field)
        if rows is None:
            rows = []
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError("Unsupported financial rows")
        for row in rows:
            for key in ("report_id", "date", "report_start_date", "report_end_date"):
                if row.get(key) is not None and not isinstance(row[key], str):
                    raise ValueError("Unsupported financial metadata")
        normalized[field] = rows
    return normalized


def _get_financials(company_id, *, allow_paid=False):
    """One authorized request, documented cost 10 credits. No automatic retries.

    SDK HTTP errors never trigger another potentially chargeable REST request.
    Account entitlement is unknown until confirmed by the provider; a failed
    request is not evidence that the company has no financial statements.
    """
    from datetime import datetime, timezone
    from urllib.parse import quote
    import requests

    result = {"provider": "OpenRegister", "company_id": company_id,
              "source": f"https://api.openregister.de/v1/company/{quote(company_id, safe='')}/financials",
              "status": "not_requested", "reason": "Financial retrieval requires explicit 10-credit authorization.",
              "plan_access": "unconfirmed", "request_status": "not_requested",
              "financial_data_status": "unknown", "publication_status": "unknown"}
    # Reuse previously retrieved financial data without another API request.
    from scripts.financial_cache import load_financials, save_financials

    if not allow_paid:
        return result
    if not API_KEY:
        return _financial_failure(result, "missing_credentials", "OpenRegister credentials are not configured.", stage="configuration")
    if not company_id or not company_id.strip():
        return _financial_failure(result, "invalid_company_id", "A non-empty company identifier is required.", stage="configuration")
    stage = "sdk_initialization"
    http_status = None
    try:
        try:
            from openregister import Openregister
        except ImportError:
            Openregister = None
        client = Openregister(api_key=API_KEY, max_retries=0, timeout=30) if Openregister else None
        method = getattr(client.company, "get_financials_v1", None) if client else None
        result["transport"] = "sdk" if callable(method) else "rest"
        stage = "request"
        if callable(method):
            # Current official SDK accepts company_id as positional or keyword.
            response = method(company_id=company_id)
            http_status = 200
            stage = "response_parsing"
            raw = response if isinstance(response, dict) else response.model_dump(mode="json")
        else:
            response = requests.get(result["source"], headers={"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"},
                                    timeout=30, allow_redirects=False)
            http_status = response.status_code
            if http_status != 200:
                body = None
                if http_status == 404:
                    try:
                        body = response.json()
                    except (ValueError, TypeError):
                        pass
                return _financial_http_failure(result, http_status, body=body)
            stage = "response_parsing"
            raw = response.json()
        raw = _validate_financial_payload(raw)
        has_indicators = bool(raw["indicators"])
        reason = None if has_indicators else "Request succeeded but no reported financial indicators were returned; this does not prove that no statements exist."
        if reason:
            print("[OpenRegister financials] no_indicators_returned: " + reason)
        financial_result = {**result, "status": "available" if has_indicators else "unavailable",
                "error_code": None if has_indicators else "no_indicators_returned", "http_status": http_status,
                "plan_access": "request_succeeded", "request_status": "succeeded",
                "financial_data_status": "figures_returned" if has_indicators else "no_figures_returned",
                "publication_status": "unknown", "reason": reason,
                "retrieved_at": datetime.now(timezone.utc).isoformat(), "raw": raw}

        # Cache only successfully retrieved financial responses.
        try:
            save_financials(company_id, financial_result)
            print("[OpenRegister financials] Response saved to cache.")
        except (OSError, TypeError, ValueError) as cache_error:
            print(f"[OpenRegister financials] Cache write failed: {type(cache_error).__name__}")

        return financial_result

    except Exception as error:
        # SDKs expose status_code on APIStatusError. Do not stringify exceptions.
        status = getattr(error, "status_code", None)
        if isinstance(status, int) and not isinstance(status, bool) and status >= 300:
            body = getattr(error, "body", None)
            if status == 404 and body is None:
                # Reading the existing SDK response body performs no network I/O.
                try:
                    body = error.response.json()
                except (AttributeError, ValueError, TypeError):
                    pass
            return _financial_http_failure(result, status, stage=stage, body=body)
        if status == 200:
            http_status = 200
        names = {cls.__name__ for cls in type(error).__mro__}
        if isinstance(error, requests.exceptions.Timeout) or names & {"APITimeoutError", "TimeoutException", "ReadTimeout", "ConnectTimeout"}:
            return _financial_failure(result, "network_timeout", "Financial request timed out; the provider may have processed it, so verify usage before retrying.", stage=stage)
        if isinstance(error, requests.exceptions.ConnectionError) or names & {"APIConnectionError", "ConnectError", "NetworkError"}:
            return _financial_failure(result, "network_error", "Network connection failed; check connectivity and provider availability.", stage=stage)
        if stage == "response_parsing" or "APIResponseValidationError" in names:
            return _financial_failure(result, "unsupported_response", "Financial response could not be parsed as the supported JSON financial schema.", status_code=http_status, stage=stage)
        if stage == "sdk_initialization" or isinstance(error, (TypeError, AttributeError)):
            return _financial_failure(result, "sdk_incompatible", "SDK initialization or method invocation failed; verify the installed openregister-sdk and its method signature.", stage=stage)
        if isinstance(error, requests.exceptions.RequestException):
            return _financial_failure(result, "network_error", "Financial HTTP transport failed; no response could be validated.", stage=stage)
        return _financial_failure(result, "unexpected_error", "Unexpected financial integration error; consult the failure stage and reproduce with mocked inputs.", stage=stage)


def get_financials(company_id, *, allow_paid=False):
    """Preserve the existing financial cache; reserve budget only on a miss."""
    from scripts.financial_cache import load_financials
    from scripts.development_fixtures import financials
    tracker = get_tracker()
    if not tracker.development and company_id and company_id.strip():
        try:
            cached = load_financials(company_id)
        except (OSError, ValueError, KeyError):
            cached = None
        if cached is not None:
            return tracker.cache_hit("OpenRegister", "financials", {**cached, "cache_hit": True})
    if not allow_paid and not tracker.development:
        return _get_financials(company_id, allow_paid=False)
    return tracker.execute("OpenRegister", "financials", company_id,
                           lambda: _get_financials(company_id, allow_paid=True), approved=allow_paid,
                           mock=lambda: financials(company_id),
                           success=lambda value: value.get("request_status") == "succeeded")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nOpenRegister error: {error}")
