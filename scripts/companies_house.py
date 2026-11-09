import os
import requests
from dotenv import load_dotenv
from scripts.api_usage import get_tracker

# ==========================================
# LEGALFLOW — Companies House Integration
# ==========================================

load_dotenv()

API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"


# ==========================================
# API REQUEST HANDLER
# ==========================================

def _api_request(endpoint, params=None):

    if not API_KEY:
        raise ValueError(
            "Missing COMPANIES_HOUSE_API_KEY in .env"
        )

    try:
        response = requests.get(
            f"{BASE_URL}{endpoint}",
            auth=(API_KEY, ""),
            params=params,
            timeout=20
        )

        response.raise_for_status()
        return response.json()

    except requests.exceptions.HTTPError as error:
        print(f"Companies House API error: {error}")
        raise

    except requests.exceptions.RequestException as error:
        print(f"Connection error: {error}")
        raise


def api_request(endpoint, params=None):
    from scripts.development_fixtures import uk_response
    return get_tracker().execute("Companies House", "public_data", {"endpoint": endpoint, "params": params},
                                 lambda: _api_request(endpoint, params), mock=lambda: uk_response(endpoint, params))


# ==========================================
# 1. SEARCH COMPANIES
# ==========================================

def search_company(company_name):

    return api_request(
        "/search/companies",
        params={
            "q": company_name,
            "items_per_page": 5
        }
    )


# ==========================================
# 2. COMPANY PROFILE
# ==========================================

def get_company_profile(company_number):

    return api_request(
        f"/company/{company_number}"
    )


# ==========================================
# 3. DIRECTORS AND OFFICERS
# ==========================================

def get_company_officers(company_number):

    return api_request(
        f"/company/{company_number}/officers",
        params={
            "items_per_page": 100
        }
    )


# ==========================================
# 4. FILING HISTORY
# ==========================================

def get_filing_history(company_number):

    return api_request(
        f"/company/{company_number}/filing-history",
        params={
            "items_per_page": 10
        }
    )


# ==========================================
# 5. COMPANY DUE DILIGENCE DATA
# ==========================================

def get_company_due_diligence(company_number):

    print("\nRetrieving company profile...")
    profile = get_company_profile(company_number)

    print("Retrieving directors and officers...")
    officers = get_company_officers(company_number)

    print("Retrieving filing history...")
    filings = get_filing_history(company_number)

    return {
        "company_profile": profile,
        "officers": officers,
        "filing_history": filings
    }


# ==========================================
# 6. DISPLAY RESULTS
# ==========================================

def display_company_report(data):

    profile = data["company_profile"]
    officers = data["officers"]
    filings = data["filing_history"]

    print("\n" + "=" * 55)
    print("LEGALFLOW — COMPANY DUE DILIGENCE REPORT")
    print("=" * 55)

    print("\nCOMPANY INFORMATION")
    print("-" * 55)

    print("Company:", profile.get("company_name"))
    print("Company Number:", profile.get("company_number"))
    print("Status:", profile.get("company_status"))
    print("Company Type:", profile.get("type"))
    print("Incorporated:", profile.get("date_of_creation"))

    address = profile.get("registered_office_address", {})

    print("\nREGISTERED ADDRESS")
    print("-" * 55)

    print(", ".join(
        str(value)
        for value in address.values()
        if value
    ))

    print("\nDIRECTORS AND OFFICERS")
    print("-" * 55)

    officer_items = officers.get("items", [])

    active_officers = [
        officer
        for officer in officer_items
        if not officer.get("resigned_on")
    ]

    for officer in active_officers:

        print(
            f"{officer.get('name')} | "
            f"{officer.get('officer_role')} | "
            f"Appointed: {officer.get('appointed_on')}"
        )

    if not active_officers:
        print("No active officers returned.")

    print("\nRECENT FILINGS")
    print("-" * 55)

    for filing in filings.get("items", []):

        print(
            f"{filing.get('date')} | "
            f"{filing.get('description')} | "
            f"{filing.get('type')}"
        )

    print("\n" + "=" * 55)
    print("END OF REPORT")
    print("=" * 55)


# ==========================================
# 7. MAIN APPLICATION
# ==========================================

def main():

    print("\nWelcome to LEGALFLOW")
    print("AI-Powered Corporate Due Diligence")
    print("----------------------------------")

    company_name = input(
        "\nEnter UK company name: "
    ).strip()

    if not company_name:
        print("Please enter a company name.")
        return

    print("\nSearching Companies House...")

    results = search_company(company_name)

    companies = results.get("items", [])

    if not companies:
        print("No companies found.")
        return

    print("\nSEARCH RESULTS")
    print("-" * 55)

    for index, company in enumerate(companies, start=1):

        print(
            f"{index}. {company.get('title')} "
            f"({company.get('company_number')}) "
            f"- {company.get('company_status')}"
        )

    while True:
        choice = input(
            "\nSelect a company (1-5): "
        ).strip()

        if choice.isdigit() and 1 <= int(choice) <= len(companies):
            break

        print("Please select a valid company number.")

    selected_company = companies[int(choice) - 1]

    company_number = selected_company["company_number"]

    print(
        f"\nSelected company: {selected_company.get('title')}"
    )

    data = get_company_due_diligence(company_number)

    display_company_report(data)



DOCUMENT_BASE_URL = "https://document-api.company-information.service.gov.uk"


def _document_url(url):
    """Validate API-provided metadata links before attaching credentials."""
    from urllib.parse import urlparse
    import re
    parsed = urlparse(url or "")
    if (parsed.scheme != "https" or parsed.netloc != "document-api.company-information.service.gov.uk"
            or not re.fullmatch(r"/document/[A-Za-z0-9_-]+", parsed.path)
            or parsed.query or parsed.fragment):
        raise ValueError("Invalid Companies House document metadata URL")
    return url


def get_account_filings(company_number):
    """A single bounded accounts-only page; not a complete filing search."""
    return api_request(f"/company/{company_number}/filing-history",
                       params={"category": "accounts", "items_per_page": 5, "start_index": 0})


def _get_document_metadata(metadata_url):
    response = requests.get(_document_url(metadata_url), auth=(API_KEY, ""), timeout=20,
                            allow_redirects=False)
    if response.status_code != 200:
        raise ValueError("Document metadata unavailable")
    return response.json()


def _download_account_document(metadata_url, content_type, *, max_bytes=5_000_000):
    """Download one bounded document; redirected storage receives no API key."""
    from urllib.parse import urlparse
    import ipaddress
    url = _document_url(metadata_url) + "/content"
    with requests.get(url, auth=(API_KEY, ""), headers={"Accept": content_type},
                      timeout=20, allow_redirects=False, stream=True) as response:
        if response.status_code == 302:
            location = response.headers.get("Location", "")
        else:
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Unexpected document response")
            return _bounded_content(response, max_bytes)
    target = urlparse(location)
    if target.scheme != "https" or not target.hostname or target.username or target.password or target.port not in (None, 443):
        raise ValueError("Invalid document storage redirect")
    if target.hostname == "localhost" or target.hostname.endswith((".local", ".internal")):
        raise ValueError("Invalid document storage host")
    try:
        address = ipaddress.ip_address(target.hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise ValueError("Invalid document storage address")
    with requests.get(location, headers={"Accept": content_type}, timeout=20,
                      allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise ValueError("Document download unavailable")
        return _bounded_content(response, max_bytes)


def _bounded_content(response, max_bytes):
    if int(response.headers.get("Content-Length", "0")) > max_bytes:
        raise ValueError("Account document exceeds size limit")
    chunks, total = [], 0
    for chunk in response.iter_content(chunk_size=65536):
        total += len(chunk)
        if total > max_bytes:
            raise ValueError("Account document exceeds size limit")
        chunks.append(chunk)
    return b"".join(chunks)


def get_document_metadata(metadata_url):
    _document_url(metadata_url)
    return get_tracker().execute("Companies House", "document_metadata", metadata_url,
                                 lambda: _get_document_metadata(metadata_url), mock={"resources": {}})


def download_account_document(metadata_url, content_type, *, max_bytes=5_000_000):
    _document_url(metadata_url)
    return get_tracker().execute("Companies House", "document_download", [metadata_url, content_type, max_bytes],
                                 lambda: _download_account_document(metadata_url, content_type, max_bytes=max_bytes), mock=b"")


def get_annual_accounts(company_number, *, enabled=False, download=False):
    """Locate five filings; optionally retrieve at most one account, <=5 MB."""
    from datetime import datetime, timezone
    from scripts.accounts_parser import parse_accounts
    result = {"provider": "Companies House", "company_id": company_number,
              "source": f"{BASE_URL}/company/{company_number}/filing-history",
              "status": "not_requested", "documents": [], "periods": [],
              "reason": "Accounts retrieval was not requested."}
    if not enabled:
        return result
    try:
        filings = get_account_filings(company_number)
        documents = [item for item in filings.get("items", []) if item.get("category") == "accounts"][:5]
        result.update(status="metadata_only", documents=documents,
                      retrieved_at=datetime.now(timezone.utc).isoformat(),
                      reason="Bounded accounts filing page only; financial figures not extracted.")
        if not documents:
            return {**result, "status": "unavailable", "reason": "No accounts returned in the bounded filing page."}
        if not download:
            return result
        link = documents[0].get("links", {}).get("document_metadata")
        metadata = get_document_metadata(link)
        result["document_metadata"] = metadata
        resources = metadata.get("resources", {})
        supported = [mime for mime in ("application/xhtml+xml", "application/xml", "text/xml", "text/html", "application/pdf")
                     if mime in resources]
        if not supported:
            return {**result, "reason": "No supported account document format advertised."}
        mime = supported[0]
        if resources[mime].get("content_length", 0) > 5_000_000:
            return {**result, "reason": "Account document exceeds the 5 MB limit; not downloaded."}
        content = download_account_document(link, mime)
        result.update(downloaded_document={"source": link, "content_type": mime, "bytes": len(content)},
                      periods=parse_accounts(content, company_number, link) if mime != "application/pdf" else [])
        result.update(status="available" if result["periods"] else "document_only",
                      reason="Reported machine-readable facts extracted; review original accounts." if result["periods"] else
                      "Document retrieved but no supported unambiguous XBRL figures extracted; manual review required.")
        # Retain one document for explicit caller access, never send bytes to the model.
        result["document_content"] = content
        return result
    except Exception:
        return {**result, "status": "unavailable", "reason": "Accounts retrieval failed; review credentials, document availability and format."}


if __name__ == "__main__":
    try:
        main()
    except (requests.exceptions.RequestException, ValueError, KeyError) as error:
        print(f"\nLEGALFLOW could not complete the request: {error}")
