import os
import re
import requests
from dotenv import load_dotenv
from scripts.api_usage import get_tracker

# ==========================================
# INCEPT — Companies House corporate identity
# ==========================================

load_dotenv()

API_KEY = os.getenv("COMPANIES_HOUSE_API_KEY")
BASE_URL = "https://api.company-information.service.gov.uk"


# ==========================================
# API REQUEST HANDLER
# ==========================================

def _validate_endpoint(endpoint,params=None):
    if not (endpoint=='/search/companies' or re.fullmatch(r'/company/[A-Za-z0-9]{8}(?:/officers|/filing-history)?',endpoint)) or (params or {}).get('category')=='accounts':
        raise ValueError('Only corporate search, identity, officer and legal-filing metadata operations are supported')


def _api_request(endpoint, params=None):

    _validate_endpoint(endpoint,params)
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
        print(f"Companies House API error: HTTP {getattr(error.response, 'status_code', 'unknown')}")
        raise

    except requests.exceptions.RequestException as error:
        print(f"Companies House connection error: {type(error).__name__}")
        raise


def api_request(endpoint, params=None):
    _validate_endpoint(endpoint,params)
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
