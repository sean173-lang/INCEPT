"""Search German companies using the OpenRegister API."""

import os
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from scripts.api_usage import get_tracker, UsageTracker, use_tracker, UsageBlocked

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


if __name__ == "__main__":

    import argparse
    parser = argparse.ArgumentParser(description="Search OpenRegister with usage protection")
    parser.add_argument("query", nargs="+")
    parser.add_argument("--approve-api", action="store_true")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--max-openregister-credits", type=int, default=10)
    args = parser.parse_args()
    query = " ".join(args.query).strip()

    if not query:
        print("Usage: python -m scripts.company_search 'Company Name'")
        sys.exit(1)

    try:
        tracker = UsageTracker(approved=args.approve_api, development=args.dev,
                               max_openregister_credits=args.max_openregister_credits,
                               cache_dir="data/api_cache", ledger_path="data/api_usage.jsonl")
        with use_tracker(tracker):
            try:
                results = search_companies(query)
            finally:
                print("API usage (estimates):", json.dumps(tracker.summary()))

        if not results:
            print("No matching companies found.")
            sys.exit(0)

        print(f"\nFound {len(results)} matching companies:\n")

        for index, company in enumerate(results, start=1):
            print(f"{index}. {company.get('name')}")
            print(f"   ID: {company.get('company_id')}")
            print(f"   Court: {company.get('register_court')}")
            print(f"   Register: {company.get('register_type')} {company.get('register_number')}")
            print(f"   Active: {company.get('active')}")
            print()

    except UsageBlocked as error:
        print(f"Search blocked: {error}")
        sys.exit(1)
    except Exception as error:
        print(f"Search failed: {type(error).__name__}")
        print("HTTP status:", getattr(error, "status_code", None))
        sys.exit(1)
