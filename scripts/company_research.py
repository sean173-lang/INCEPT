import os
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

API_KEY = os.getenv("TAVILY_API_KEY")


def research_company(company_name, country="Germany"):
    if not API_KEY:
        raise ValueError("Missing TAVILY_API_KEY in .env")

    client = TavilyClient(api_key=API_KEY)

    query = (
        f'"{company_name}" {country} '
        'lawsuit OR litigation OR insolvency OR sanctions '
        'OR regulatory investigation'
    )

    response = client.search(
        query=query,
        search_depth="basic",
        max_results=5,
        include_answer=False
    )

    return {
        "company": company_name,
        "country": country,
        "sources": [
            {
                "title": item.get("title"),
                "url": item.get("url"),
                "content": item.get("content"),
                "score": item.get("score")
            }
            for item in response.get("results", [])
        ]
    }


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
