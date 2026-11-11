import os
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import urlsplit
from dotenv import load_dotenv
from scripts.api_usage import get_tracker

load_dotenv()

API_KEY = os.getenv("TAVILY_API_KEY")


def build_research_query(company_name, country="Germany", *, registration_number=None, register_court=None):
    """One narrow identity-anchored legal query; no keyword OR expansion."""
    def clean(value):
        return " ".join(str(value or "").replace('"', ' ').split())

    name = clean(company_name)
    if not name:
        raise ValueError("Company name is required for identity-focused research")
    jurisdiction = {"UK": "United Kingdom", "Germany": "Germany"}.get(country, clean(country))
    parts = [f'"{name}"']
    if registration_number:
        parts.append(f'"{clean(registration_number)}"')
    if register_court:
        parts.append(f'"{clean(register_court)}"')
    parts.extend([jurisdiction, '"legal proceedings"'])
    return " ".join(parts)


def research_company(company_name, country="Germany", *, registration_number=None, register_court=None, max_results=5):
    if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 5:
        raise ValueError("Search result limit must be an integer between one and five")
    query = build_research_query(company_name, country, registration_number=registration_number,
                                 register_court=register_court)

    def retrieve():
        from tavily import TavilyClient
        if not API_KEY:
            raise ValueError("Missing TAVILY_API_KEY in .env")
        # Explicitly disable transport retries and redirects; preserve cost controls.
        with requests.Session() as session:
            session.mount("https://", HTTPAdapter(max_retries=0))
            session.max_redirects = 0
            client = TavilyClient(api_key=API_KEY, session=session)
            response = client.search(
                query=query, search_depth="basic", max_results=max_results,
                include_answer=False, include_raw_content=False, include_images=False,
                auto_parameters=False, include_usage=True, timeout=20
            )
        if not isinstance(response, dict) or not isinstance(response.get("results"), list):
            raise ValueError("Unsupported Tavily response; research was not cached")

        if any(not isinstance(row, dict) for row in response["results"]):
            raise ValueError("Unsupported Tavily result row; research was not cached")
        retrieved_at = datetime.now(timezone.utc).isoformat()
        def source_url(value):
            if not isinstance(value, str):return None
            try:
                url=urlsplit(value)
                if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:return None
                if any(k in url.query.lower() for k in ("token=", "signature=", "credential=", "x-amz-")):return None
                return value
            except ValueError:return None
        return {
            "company": company_name,
            "country": country,
            "query": query,
            "retrieved_at": retrieved_at,
            "usage": response.get("usage"),
            "billing_confirmed": False,
            "coverage_note": "Single exact-identity legal query; not a comprehensive litigation, sanctions or insolvency search.",
            "sources": [
                {
                    "title": item.get("title"),
                    "url": source_url(item.get("url")),
                    "retrieved_at": retrieved_at,
                    "content": item.get("content"),
                    "score": item.get("score"),
                    "published_date": item.get("published_date"),
                }
                for item in response.get("results", [])[:max_results]
            ]
        }

    return get_tracker().execute("Tavily", "search_basic", {"query": query, "max_results": max_results}, retrieve,
                                 cache=True, mock={"company": "LEGALFLOW DEMO", "country": country,
                                                   "query": query, "sources": [], "coverage_note": "Synthetic development fixture."})
