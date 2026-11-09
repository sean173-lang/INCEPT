"""Evidence-linked issues and transaction follow-ups, not legal determinations."""


def build_issues(company, validation, financials):
    issues = []

    def add(description, evidence, source, significance, follow_up, status, category):
        issues.append({"description": description, "supporting_evidence": evidence,
                       "source": source, "potential_legal_significance": significance,
                       "recommended_follow_up": follow_up, "verification_status": status,
                       "category": category})

    register_source = {"authority": company.get("register_court") if company.get("country") == "Germany" else "Companies House",
                       "company_number": company.get("company_number"),
                       "retrieved_at": company.get("retrieved_at")}
    for key, passed in validation["registry_checks"].items():
        if not passed:
            add("Register consistency check requires resolution: " + key.replace("_", " "),
                {"field": key, "reported_value": company.get(key), "matched_original_response": False}, register_source,
                "Unresolved entity or date discrepancies can affect the transaction perimeter and authority checks.",
                "Obtain a current register extract and reconcile the discrepancy.", "inconsistent_or_missing_evidence", "missing_information")
    for indicator in financials["indicators"]:
        add(indicator["description"], {"period_end": indicator["period_end"], "figures": indicator["evidence"]},
            indicator["source"], "May warrant review of liquidity, funding, covenants and transaction assumptions; does not establish insolvency.",
            "Reconcile to signed accounts and obtain management explanations and current cash-flow forecasts.",
            indicator["verification_status"], "financial_indicator")
    for item in validation["sources"]:
        if item["usable"] and (item["legal_evidence"] == "unverified_allegation" or item["litigation_status"] != "unknown"):
            add("External legal lead requires original-source review", item["source"].get("content"),
                item["source"].get("url"),
                "Potential disclosure, warranty or indemnity considerations depend on verified case facts and current status.",
                "Obtain original filings, case identifiers and counsel confirmation; distinguish allegations from findings.",
                "unverified_search_excerpt", "legal_lead")
    for key in ("original_legal_documents", "verified_litigation_status", "current_sanctions_and_insolvency_checks"):
        if key in validation["missing_evidence"]:
            descriptions = {"original_legal_documents": "Original legal documents have not been reviewed",
                            "verified_litigation_status": "Litigation coverage remains incomplete",
                            "current_sanctions_and_insolvency_checks": "Current sanctions and insolvency checks remain incomplete"}
            add(descriptions[key], "Required evidence not supplied to this review.", "Evidence verification coverage review",
                "Missing evidence limits transaction diligence coverage; it does not establish wrongdoing.",
                "Obtain authoritative records and appropriate legal confirmations before reliance.", "not_verified", "missing_information")
    if not financials["periods"]:
        add("Financial information is unavailable for analysis", financials.get("reason") or financials["coverage"],
            financials.get("source") or "Financial retrieval coverage review",
            "Financial capacity, distributions and funding assumptions cannot be assessed from missing accounts.",
            "Request signed annual accounts, current management accounts, debt schedules and cash-flow forecasts.",
            "not_verified", "missing_information")
    elif any(not p["valid_period"] or any(not f["calculation_eligible"] for f in p["facts"].values()) for p in financials["periods"]):
        add("Financial calculation coverage is incomplete", "Some figures, reporting dates, currencies or scales are unavailable or inconsistent.",
            financials.get("source"), "Incomplete inputs limit comparability and transaction financial assumptions.",
            "Confirm reporting periods, scope, currency, scale and missing line items against the original statements.",
            "not_verified", "missing_information")
    return issues


DOCUMENT_REQUESTS = [
    "Current register extract, constitutional documents, shareholder register and ownership chart.",
    "Signed annual accounts for the last three reporting periods, with auditor reports and accounting policies.",
    "Current management accounts, cash-flow forecasts and supporting bank reconciliations.",
    "Debt and security schedules, financing agreements, covenant calculations and guarantees.",
    "Litigation and regulatory correspondence, case documents and counsel confirmations of current status.",
    "Current sanctions and insolvency screening records with entity identifiers and screening dates.",
]
TRANSACTION_CONSIDERATIONS = [
    "Confirm the legal entity, ownership perimeter and signatory authority before executing transaction documents.",
    "Reconcile reported accounts to signed statements and assess working capital, net debt and funding needs with financial advisers.",
    "Resolve evidence gaps before reliance; consider targeted disclosures, warranties, indemnities or completion conditions with counsel.",
    "Financial indicators are review triggers. Unverified allegations and missing information are not established legal findings.",
]


def financials_for_company(company, validation):
    from scripts.financial_analysis import analyze_financials
    data = company.get("financial_data") or {}
    if data.get("status") == "not_requested":
        return analyze_financials(data)
    if data and (data.get("company_id") != company.get("company_number")
                 or not validation["registry_checks"].get("company_number")
                 or not validation["registry_checks"].get("name")):
        data = {"status": "excluded", "reason": "Financial evidence could not be linked to a consistent registry identity."}
    return analyze_financials(data)
