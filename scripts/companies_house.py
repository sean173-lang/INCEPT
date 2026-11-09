import os
import requests
from dotenv import load_dotenv

# ==========================================
# LEGALFLOW — Companies House Integration
# ==========================================

load_dotenv()

API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"


# ==========================================
# API REQUEST HANDLER
# ==========================================

def api_request(endpoint, params=None):

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


if __name__ == "__main__":
    try:
        main()
    except (requests.exceptions.RequestException, ValueError, KeyError) as error:
        print(f"\nLEGALFLOW could not complete the request: {error}")