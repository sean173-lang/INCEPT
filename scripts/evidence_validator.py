"""Conservative, offline checks over registry responses and search evidence.

These checks validate provenance and consistency, not the truth of a webpage.
Search excerpts can never establish a legal finding or current case status.
"""

import re
from datetime import date, datetime, timezone
from urllib.parse import urlparse


OFFICIAL_DOMAINS = (
    "gov.uk", "justice.gov.uk", "judiciary.uk", "bundesgerichtshof.de",
    "handelsregister.de", "unternehmensregister.de",
    "insolvenzbekanntmachungen.de", "bundesanzeiger.de", "bafin.de",
    "bundesjustizamt.de", "justiz.de", "europa.eu",
)


def _normal(value):
    return re.sub(r"[^\w]", "", str(value or "").casefold())


def _date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def classify_source(url):
    """Use parsed hostname boundaries; lookalike domains are not official."""
    try:
        parsed = urlparse(url or "")
        host = (parsed.hostname or "").lower()
        if parsed.scheme not in ("https", "http") or not host or parsed.username:
            return "unknown"
        if any(host == domain or host.endswith("." + domain)
               for domain in OFFICIAL_DOMAINS):
            return "official"
        return "third_party"
    except ValueError:
        return "unknown"


def validate_evidence(company, research, *, today=None, max_age_days=365):
    """Return JSON-safe annotations without changing input or making requests.

    ``original_api_data`` must be the response captured by the registry adapter.
    German registration numbers require court context; OpenRegister IDs are
    provider IDs, not legal registration numbers.
    """
    today = today or datetime.now(timezone.utc).date()
    raw = company.get("original_api_data") or {}
    german = company.get("country") == "Germany"
    profile = raw.get("company", {}) if german else raw.get("profile", {})
    raw_name = (profile.get("name") or {}).get("name") if german else profile.get("company_name")
    raw_number = profile.get("id") if german else profile.get("company_number")
    register = profile.get("company_register") or {}
    checks = {
        "name": bool(raw_name and _normal(raw_name) == _normal(company.get("name"))),
        "company_number": bool(raw_number and _normal(raw_number) == _normal(company.get("company_number"))),
    }
    if german:
        for key in ("register_number", "register_court"):
            checks[key] = bool(register.get(key) and _normal(register[key]) == _normal(company.get(key)))
    expected_date = profile.get("incorporated_at" if german else "date_of_creation")
    checks["incorporated"] = bool(
        _date(expected_date) and _date(expected_date) == _date(company.get("incorporated"))
        and _date(expected_date) <= today
    )
    date_checks = [{"field": "incorporated", "verified": checks["incorporated"]}]
    if not german:
        for item in company.get("officers", []):
            valid = any(
                item.get("name") == original.get("name")
                and item.get("role") == original.get("officer_role")
                and _date(item.get("appointed_on")) is not None
                and _date(item["appointed_on"]) <= today
                and item.get("appointed_on") == original.get("appointed_on")
                and not original.get("resigned_on")
                for original in raw.get("officers", {}).get("items", [])
            )
            date_checks.append({"field": "officers.appointed_on", "verified": valid})
        for item in company.get("recent_filings", []):
            valid = any(
                all(item.get(key) == original.get(key) for key in ("date", "type", "description"))
                and _date(item.get("date")) is not None and _date(item["date"]) <= today
                for original in raw.get("filings", {}).get("items", [])
            )
            date_checks.append({"field": "recent_filings.date", "verified": valid})

    missing = ["registry." + key for key, valid in checks.items() if not valid]
    if any(not item["verified"] for item in date_checks):
        missing.append("verified_registry_dates")
    sources = []
    for source in research.get("sources", []):
        text = " ".join(str(source.get(key) or "") for key in ("title", "content"))
        # Prefer explicit structured identity; otherwise require the complete name.
        stated_name = source.get("company_name")
        stated_number = source.get("register_number" if german else "company_number")
        expected_number = company.get("register_number" if german else "company_number")
        numbers = re.findall(r"\b(?:company\s*(?:number|no\.?|registration number)|registration\s*(?:number|no\.?)|HR[AB])\s*[:#]?\s*([A-Z]{0,2}\d[\d ]*)", text, re.I)
        if stated_number:
            numbers.append(stated_number)
        mismatch = any(_normal(n) != _normal(expected_number).removeprefix("hrb").removeprefix("hra")
                       and _normal(n) != _normal(expected_number) for n in numbers)
        name_match = bool(company.get("name") and re.search(
            r"(?<!\w)" + re.escape(company["name"]) + r"(?!\w)", text, re.I))
        if stated_name and _normal(stated_name) != _normal(company.get("name")):
            mismatch = True
        if german and source.get("register_court") and (
            _normal(source["register_court"]) != _normal(company.get("register_court"))
        ):
            mismatch = True
        identity = "unrelated" if mismatch else "possible_match" if name_match else "unverified"
        published = _date(source.get("published_date") or source.get("published_at"))
        freshness = ("unknown" if published is None else "invalid_future_date" if published > today
                     else "outdated" if (today - published).days > max_age_days else "recent")
        allegation = bool(re.search(r"\b(alleg\w*|accus\w*|claim\w*|investigat\w*)\b", text, re.I))
        historical = bool(re.search(r"\b(settled|dismissed|closed|concluded|resolved)\b", text, re.I))
        ongoing = bool(re.search(r"\b(ongoing|pending|currently)\b", text, re.I))
        sources.append({
            "source": dict(source), "source_type": classify_source(source.get("url")),
            "identity": identity, "registration_number_match": bool(numbers) and not mismatch,
            "freshness": freshness, "usable": identity == "possible_match" and bool(source.get("content"))
            and classify_source(source.get("url")) != "unknown" and freshness != "invalid_future_date",
            "legal_evidence": "unverified_allegation" if allegation else "unverified_search_excerpt",
            "litigation_status": "conflicting_unverified" if historical and ongoing else
            "historical_unverified" if historical else "ongoing_unverified" if ongoing else "unknown",
            "verified_legal_finding": False,
        })
        if freshness in ("unknown", "outdated", "invalid_future_date"):
            missing.append(f"source_{len(sources)}.current_dated_evidence")
    if not any(s["usable"] for s in sources):
        missing.append("relevant_external_evidence")
    missing.extend(["original_legal_documents", "verified_litigation_status", "current_sanctions_and_insolvency_checks"])
    return {
        "analysis_date": today.isoformat(), "registry_checks": checks,
        "date_checks": date_checks, "sources": sources, "missing_evidence": missing,
        "risk_assessment": "Undetermined",
        "risk_reason": "Registry records and search excerpts do not establish sufficient legal risk coverage. Absence of adverse results is not evidence of low risk.",
        "limitations": ["Identity matches are candidates, not independently verified identities.",
                        "Publication age does not establish event date or current litigation status.",
                        "OpenRegister is a third-party registry data provider.",
                        "No original webpages or court documents were retrieved; official hosts alone do not verify claims."],
    }
