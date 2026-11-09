"""Render validated evidence; never publish untrusted model conclusions."""
import html
import json
import re

from scripts.due_diligence import build_issues, financials_for_company, DOCUMENT_REQUESTS, TRANSACTION_CONSIDERATIONS


FOLLOW_UPS = {
    "identity": "Confirm company identity and registration details with the register authority.",
    "documents": "Obtain original court and regulatory documents for any relevant legal leads.",
    "litigation": "Verify whether any litigation is historical, concluded, or ongoing.",
    "screening": "Complete current sanctions and insolvency checks using authoritative records.",
    "financials": "Obtain current financial statements and shareholder documentation.",
}


def text(value):
    """Keep source-provided values from creating Markdown headings or links."""
    value = html.escape(str(value if value is not None else "Not available"))
    return re.sub(r"([\\`*{}_\[\]()#!|>])", r"\\\1", " ".join(value.split()))


def readable_gaps(validation):
    labels = {
        "registry.name": "Company name could not be matched to the original register response.",
        "registry.company_number": "Company or provider identifier could not be matched to the original register response.",
        "registry.register_number": "Legal registration number could not be verified against the register response.",
        "registry.register_court": "Register court could not be verified against the register response.",
        "registry.incorporated": "Incorporation date could not be verified against the original register response.",
        "verified_registry_dates": "One or more register dates are missing, inconsistent, or invalid.",
        "relevant_external_evidence": "No usable external evidence linked to this company was available.",
        "original_legal_documents": "Original court and regulatory documents have not been reviewed.",
        "verified_litigation_status": "Historical and ongoing litigation status has not been independently verified.",
        "current_sanctions_and_insolvency_checks": "Current sanctions and insolvency checks remain incomplete.",
    }
    result = []
    for key in validation["missing_evidence"]:
        match = re.fullmatch(r"source_(\d+)\.current_dated_evidence", key)
        if match:
            index = int(match[1])
            source = validation["sources"][index - 1]
            title = source["source"].get("title") or "Untitled source"
            reason = {"unknown": "publication date is missing or invalid",
                      "outdated": "publication date is outside the freshness window",
                      "invalid_future_date": "publication date is in the future"}[source["freshness"]]
            result.append(f"External source {index} ({title}): {reason}; current dated evidence is needed.")
        else:
            result.append(labels.get(key, "Additional evidence requires verification."))
    return result


def register_reference(company):
    """Use recorded retrieval time, never infer retrieval from analysis time."""
    german = company.get("country") == "Germany"
    return {
        "authority": company.get("register_court") if german else "Companies House",
        "registration_number": company.get("register_number") if german else company.get("company_number"),
        "provider": "OpenRegister (third-party register data provider)" if german else "Companies House API",
        "provider_id": company.get("company_number"),
        "retrieved_at": company.get("retrieved_at"),
    }


def recommended_followups(model_output):
    """Only allow known recommendation IDs; malformed output uses defaults."""
    try:
        data = json.loads(model_output)
        values = data.get("follow_up_ids", []) if isinstance(data, dict) else []
        if not isinstance(values, list):
            values = []
    except (ValueError, TypeError):
        values = []
    selected = []
    for value in values:
        if isinstance(value, str) and value in FOLLOW_UPS and value not in selected:
            selected.append(value)
    return selected + [key for key in FOLLOW_UPS if key not in selected]


def render_report(company, validation, model_output):
    reference = register_reference(company)
    financials = financials_for_company(company, validation)
    issues = build_issues(company, validation, financials)
    lines = ["# Preliminary Due Diligence Report", "", "## Executive Summary", "",
             "This preliminary review checks register-response consistency and external search evidence. "
             "Legal findings and current litigation status have not been independently verified.",
             "", "Financial coverage: " + text(financials["coverage"]),
             f"Issues requiring follow-up: {len(issues)}. Financial indicators are separate from legal findings.",
             "", "## Company Identification", ""]
    for key, label in (("name", "Company name"), ("company_number", "Provider identifier"),
                       ("register_number", "Registration number"), ("register_court", "Register authority"),
                       ("incorporated", "Incorporation date")):
        if key in company:
            checked = validation["registry_checks"].get(key, False)
            lines.append(f"- {label}: {text(company[key])} — " +
                         ("matches original API response" if checked else "not verified against original API response"))
    lines.extend(["", "## Corporate Structure", "",
                  "The following values are reported by the register data provider; their substantive accuracy "
                  "has not been independently verified.", ""])
    for key, label in (("status", "Status"), ("legal_form", "Legal form"), ("company_type", "Company type"),
                       ("capital", "Capital"), ("historical_names", "Historical names"),
                       ("management", "Management"), ("officers", "Officers"),
                       ("representation_rule", "Representation rule")):
        if company.get(key) is not None:
            value = company[key]
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, default=str)
            lines.append(f"- {label}: {text(value)}")
    lines.extend(financial_section(financials))
    lines.extend(["", "## Legal and Regulatory Findings", "",
                  "Search excerpts are unverified leads. An official hostname does not establish a legal finding. "
                  "No verified legal findings were established by this review; this does not establish their absence.", ""])
    status_labels = {"historical_unverified": "historical litigation language (unverified)",
                     "ongoing_unverified": "ongoing litigation language (unverified)",
                     "conflicting_unverified": "mixed historical and ongoing language (unverified)",
                     "unknown": "litigation status unknown"}
    for index, item in enumerate(validation["sources"], 1):
        disposition = "unverified candidate" if item["usable"] else "excluded from analysis"
        lines.append(f"- External source {index}: {disposition}; "
                     f"{text(item['source_type'].replace('_', ' '))}; {status_labels[item['litigation_status']]}. "
                     + ("Allegation language detected; no finding verified." if item["legal_evidence"] == "unverified_allegation"
                        else "No legal finding verified."))
    lines.extend(["", "## Missing Information and Verification Needs", ""])
    lines.extend("- " + text(gap) for gap in readable_gaps(validation))
    lines.extend(["", "## Due Diligence Issues List", ""])
    for index, issue in enumerate(issues, 1):
        lines.append(f"### Issue {index}: {text(issue['description'])}")
        lines.append("")
        for key, label in (("category", "Category"), ("supporting_evidence", "Supporting evidence"),
                           ("source", "Source"), ("potential_legal_significance", "Potential legal significance"),
                           ("recommended_follow_up", "Recommended follow-up action"), ("verification_status", "Verification status")):
            value = issue[key]
            if key in ("category", "verification_status"):
                value = value.replace("_", " ")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, ensure_ascii=False, default=str)
            lines.append(f"- {label}: {text(value)}")
        lines.append("")
    lines.extend(["", "## Document Request List", ""])
    lines.extend("- " + value for value in DOCUMENT_REQUESTS)
    lines.extend(["", "## Transaction Considerations", ""])
    lines.extend("- " + value for value in TRANSACTION_CONSIDERATIONS)
    lines.extend(["", "### Prioritized Follow-up Investigations", ""])
    lines.extend(f"{index}. {FOLLOW_UPS[key]}" for index, key in enumerate(recommended_followups(model_output), 1))
    lines.extend(["", "## Sources and Limitations", "", "Register reference (API record; no document URL supplied):", ""])
    for key, label in (("authority", "Register authority"), ("registration_number", "Registration number"),
                       ("provider", "Retrieved via"), ("provider_id", "Provider identifier"),
                       ("retrieved_at", "Retrieval date/time (UTC)")):
        lines.append(f"- {label}: {text(reference[key])}")
    lines.extend(["", "External search references (as supplied by the search provider):", ""])
    for index, item in enumerate(validation["sources"], 1):
        source = item["source"]
        # Plain escaped URL preserves the supplied reference without inventing links.
        lines.append(f"- Source {index}: {text(source.get('title'))}; {text(source.get('url'))} "
                     f"({'included as an unverified lead' if item['usable'] else 'excluded'}).")
    lines.extend(["", "Financial source: " + text(financials.get("source")),
                  "Financial retrieval date/time: " + text(financials.get("retrieved_at")), ""])
    for document in financials.get("documents", []):
        lines.append("- Accounts filing: " + text(document.get("description")) + "; filed "
                     + text(document.get("date")) + "; document reference: "
                     + text(document.get("links", {}).get("document_metadata")))
    lines.extend(["", "### Limitations", ""])
    lines.extend("- " + text(value) for value in financials["limitations"])
    lines.extend("- " + text(value) for value in validation["limitations"])
    lines.extend(["", "## Final Risk Assessment", "",
                  f"Preliminary risk assessment: **{validation['risk_assessment']}**.", "",
                  "Financial indicators: " + (str(len(financials["indicators"])) + " review triggers; not legal findings."),
                  "Legal findings: no findings independently verified by this workflow.",
                  "Missing information: see the evidence gaps and document requests above.",
                  "Overall due diligence coverage: incomplete; requires original records and professional review.", "",
                  validation["risk_reason"], "", "This is a preliminary research report, not a certified legal opinion.", ""])
    return "\n".join(lines)


def financial_section(financials):
    lines = ["", "## Financial Analysis", "", "Retrieval status: " + text(financials["status"].replace("_", " ")) + ".",
             text(financials.get("reason") or financials["coverage"]), ""]
    for key, label in (("request_status", "API request outcome"), ("financial_data_status", "Provider data availability"),
                       ("publication_status", "Independent publication status"), ("not_found_cause", "404 classification")):
        if financials.get(key):
            lines.append("- " + label + ": " + text(financials[key].replace("_", " ")))
    lines.append("")
    if not financials["periods"]:
        lines.append("Financial figures, ratios and reporting-period comparisons: unavailable.")
    for period in financials["periods"]:
        lines.extend(["### Reporting period", "",
                      "- Start: " + text(period.get("period_start")) + "; end: " + text(period.get("period_end")),
                      "- Reporting scope: " + text(period.get("scope")),
                      "- Source: " + text(period.get("source")),
                      "- Period valid for calculations: " + str(period["valid_period"]), "",
                      "| Figure | Reported value | Currency | Scale multiplier |", "| --- | --- | --- | --- |"])
        for metric, fact in period["facts"].items():
            lines.append("| " + " | ".join(text(v) for v in (metric.replace("_", " "),
                         fact["value"] if fact["value"] is not None else "Unavailable",
                         fact.get("currency") or "Not available", fact.get("scale") if fact.get("scale") is not None else "Not available")) + " |")
        lines.extend(["", "Calculated ratios (dimensionless):", ""])
        for name, ratio in period["ratios"].items():
            lines.append("- " + text(name.replace("_", " ")) + ": " + text(ratio["value"] or "Unavailable")
                         + "; formula: " + text(ratio["formula"]) + ("; " + text(ratio["reason"]) if ratio["reason"] else ""))
        for source in period.get("document_sources", []):
            lines.append("- Original statement reference supplied by provider: " + text(source.get("html_url")))
        lines.append("")
    for comparison in financials["comparisons"]:
        lines.append("Comparison: " + text(comparison["from"]) + " to " + text(comparison["to"]) + ".")
        if comparison["reason"]:
            lines.append("- Comparison withheld: " + text(comparison["reason"]))
        for metric, change in comparison["changes"].items():
            lines.append("- " + text(metric.replace("_", " ")) + ": absolute change " + text(change["absolute_change"])
                         + " " + text(change["currency"]) + "; percentage change " + text(change["percent_change"]) + "%.")
    lines.extend(["", "Financial indicators (not legal findings):", ""])
    lines.extend("- " + text(item["description"]) + "; period ending " + text(item["period_end"])
                 for item in financials["indicators"])
    if not financials["indicators"]:
        lines.append("No concerning indicators established from the available inputs; this is not evidence of financial health.")
    return lines
