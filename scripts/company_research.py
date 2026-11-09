import os
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


def research_company(company_name, country="Germany", *, registration_number=None, register_court=None):
    query = build_research_query(company_name, country, registration_number=registration_number,
                                 register_court=register_court)

    def retrieve():
        from tavily import TavilyClient
        if not API_KEY:
            raise ValueError("Missing TAVILY_API_KEY in .env")
        client = TavilyClient(api_key=API_KEY)
        response = client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_answer=False
        )
        if not isinstance(response, dict) or not isinstance(response.get("results"), list):
            raise ValueError("Unsupported Tavily response; research was not cached")

        return {
            "company": company_name,
            "country": country,
            "query": query,
            "coverage_note": "Single exact-identity legal query; not a comprehensive litigation, sanctions or insolvency search.",
            "sources": [
                {
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content"),
                    "score": item.get("score"),
                    "published_date": item.get("published_date"),
                }
                for item in response.get("results", [])
            ]
        }

    return get_tracker().execute("Tavily", "search_basic", {"query": query, "max_results": 5}, retrieve,
                                 cache=True, mock={"company": "LEGALFLOW DEMO", "country": country,
                                                   "query": query, "sources": [], "coverage_note": "Synthetic development fixture."})


if __name__ == "__main__":
    company = input("Company name: ").strip()
    country = input("Country (Germany/UK): ").strip() or "Germany"

    print("\nLEGALFLOW — EXTERNAL COMPANY RESEARCH")
    print("-" * 50)

    report = research_company(company, country)

    if not report["sources"]:
        print("No relevant search results found.")

    for source in report["sources"]:
        print("\nTitle:", source["title"])
        print("URL:", source["url"])
        print("Summary:", source["content"])
