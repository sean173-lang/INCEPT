"""Search German companies using the OpenRegister API."""

import os
from pathlib import Path

from dotenv import load_dotenv
from scripts.api_usage import get_tracker

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def search_companies(query):
    """Find matching companies without guessing register IDs."""

    if not query or not query.strip():
        raise ValueError("Please provide a company name.")

    def retrieve():
        from openregister import Openregister
        api_key = os.getenv("OPENREGISTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENREGISTER_API_KEY is missing.")
        client = Openregister(api_key=api_key, max_retries=0, timeout=30)
        response = client.search.autocomplete_companies_v1(query=query.strip())
        return [company.model_dump(mode="json") if hasattr(company, "model_dump") else company
                for company in response.results]
    return get_tracker().execute("OpenRegister", "company_search", query.strip(), retrieve, cache=True,
                                  mock=[{"name": "LEGALFLOW DEMO GmbH", "company_id": "DEMO", "register_court": "Synthetic court"}])
