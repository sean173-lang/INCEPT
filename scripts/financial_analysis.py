"""Offline financial normalization and Decimal calculations; no inferred figures."""
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation

METRICS = ("revenue", "net_income", "total_assets", "equity", "liabilities", "cash",
           "current_assets", "current_liabilities", "ebitda")
OPENREGISTER_FIELDS = {"total_assets": "balance_sheet_total", **{k: k for k in METRICS if k != "total_assets"}}
RATIOS = {"equity_ratio": ("equity", "total_assets"),
          "liabilities_to_assets": ("liabilities", "total_assets"),
          "current_ratio": ("current_assets", "current_liabilities"),
          "net_margin": ("net_income", "revenue")}


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def valid_date(value):
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def normalize_openregister(raw, source):
    """Join indicators to reports by ID, preserving scope and exact dates.

    Estimates and previous_value columns are not treated as reported periods.
    Currency/scale are accepted only when explicitly supplied, never inferred.
    """
    reports = {r.get("report_id"): r for r in raw.get("reports", []) if r.get("report_id")}
    periods = []
    for indicator in raw.get("indicators", []):
        report = reports.get(indicator.get("report_id"), {})
        end = report.get("report_end_date") or indicator.get("date")
        currency = report.get("currency") or raw.get("currency")
        scale = report.get("scale", raw.get("scale"))
        scope = {True: "consolidated", False: "standalone"}.get(report.get("consolidated"), "unknown")
        facts = {}
        for key, provider_key in OPENREGISTER_FIELDS.items():
            value = number(indicator.get(provider_key))
            if value is not None:
                facts[key] = {"value": str(value), "currency": currency, "scale": scale,
                              "source_field": f"indicators.{provider_key}"}
        periods.append({"period_start": report.get("report_start_date"), "period_end": end,
                        "scope": scope, "short_year": indicator.get("short_year"),
                        "report_id": indicator.get("report_id"), "facts": facts,
                        "source": source, "document_sources": report.get("sources", []),
                        "period_conflict": bool(report.get("report_end_date") and indicator.get("date")
                                                and report["report_end_date"] != indicator["date"])})
    return periods


def analyze_financials(data=None, *, today=None):
    today = today or datetime.now(timezone.utc).date()
    data = data or {"status": "not_requested"}
    periods = data.get("periods", [])
    if data.get("provider") == "OpenRegister" and data.get("raw"):
        periods = normalize_openregister(data["raw"], data.get("source"))
    results, indicators, comparisons = [], [], []
    for period in periods:
        end = valid_date(period.get("period_end"))
        start = valid_date(period.get("period_start"))
        valid = bool(end and end <= today and not period.get("period_conflict")
                     and (not period.get("period_start") or start is not None)
                     and (start is None or start <= end))
        facts, values = {}, {}
        for metric in METRICS:
            fact = period.get("facts", {}).get(metric) or {}
            value, scale = number(fact.get("value")), number(fact.get("scale"))
            currency = fact.get("currency")
            usable = (valid and value is not None and scale is not None and scale > 0
                      and isinstance(currency, str) and len(currency) == 3 and currency.isalpha())
            facts[metric] = {**fact, "value": str(value) if value is not None else None,
                             "availability": "reported" if value is not None else "unavailable",
                             "calculation_eligible": bool(usable)}
            if usable:
                values[metric] = (value * scale, currency.upper())
        ratios = {}
        for name, (numerator, denominator) in RATIOS.items():
            a, b = values.get(numerator), values.get(denominator)
            ok = a is not None and b is not None and a[1] == b[1] and b[0] > 0
            ratios[name] = {"value": str(a[0] / b[0]) if ok else None,
                            "formula": f"{numerator} / {denominator}",
                            "reason": None if ok else "Missing or incompatible units, invalid period, or non-positive denominator."}
        item = {**period, "facts": facts, "ratios": ratios, "valid_period": valid,
                "normalized_values": {k: {"value": str(v[0]), "currency": v[1]} for k, v in values.items()}}
        results.append(item)
        for metric, label in (("equity", "Negative reported equity"), ("net_income", "Reported net loss")):
            value = number(facts[metric]["value"])
            if valid and value is not None and value < 0:
                indicators.append({"description": label, "metric": metric, "period_end": period.get("period_end"),
                                   "evidence": facts[metric], "source": period.get("source"),
                                   "verification_status": "reported_financial_indicator_not_legal_finding"})
        current_ratio = number(ratios["current_ratio"]["value"])
        if current_ratio is not None and current_ratio < 1:
            indicators.append({"description": "Current ratio below 1 (review liquidity context)",
                               "metric": "current_ratio", "period_end": period.get("period_end"),
                               "evidence": ratios["current_ratio"], "source": period.get("source"),
                               "verification_status": "calculated_indicator_not_legal_finding"})
    ordered = sorted((p for p in results if p["valid_period"]), key=lambda p: p["period_end"])
    for previous, current in zip(ordered, ordered[1:]):
        reason = None
        ps, cs = valid_date(previous.get("period_start")), valid_date(current.get("period_start"))
        pe, ce = valid_date(previous["period_end"]), valid_date(current["period_end"])
        if any(sum(p["period_end"] == item["period_end"] and p.get("scope") == item.get("scope")
                   for p in ordered) > 1 for item in (previous, current)):
            reason = "Multiple reports for the same period and scope; resolve restatements before comparison."
        elif previous.get("scope") == "unknown" or previous.get("scope") != current.get("scope"):
            reason = "Unknown or different reporting scope."
        elif not ps or not cs or cs <= pe or abs((ce - cs).days - (pe - ps).days) > 7:
            reason = "Missing, overlapping, or unequal reporting periods."
        elif previous.get("short_year") or current.get("short_year"):
            reason = "Short financial year; annual comparison withheld."
        changes = {}
        for metric in ("revenue", "net_income", "total_assets", "equity", "cash"):
            a = previous["normalized_values"].get(metric)
            b = current["normalized_values"].get(metric)
            ok = not reason and a and b and a["currency"] == b["currency"]
            delta = number(b["value"]) - number(a["value"]) if ok else None
            base = number(a["value"]) if ok else None
            changes[metric] = {"absolute_change": str(delta) if delta is not None else None,
                               "percent_change": str(delta / base * 100) if base is not None and base > 0 else None,
                               "currency": b["currency"] if ok else None}
            if delta is not None and delta < 0:
                indicators.append({"description": f"Reported {metric.replace('_', ' ')} declined between comparable periods",
                                   "metric": metric, "period_end": current["period_end"],
                                   "evidence": {"from": previous["period_end"], "to": current["period_end"], **changes[metric]},
                                   "source": [previous.get("source"), current.get("source")],
                                   "verification_status": "calculated_trend_not_legal_finding"})
        comparisons.append({"from": previous["period_end"], "to": current["period_end"],
                            "reason": reason, "changes": changes})
    return {"status": data.get("status", "unavailable"),
            **{key: data.get(key) for key in ("request_status", "financial_data_status", "publication_status",
                                             "not_found_cause", "classification_basis", "http_status", "error_code")}, "provider": data.get("provider"),
            "source": data.get("source"), "retrieved_at": data.get("retrieved_at"),
            "periods": results, "comparisons": comparisons, "indicators": indicators,
            "documents": data.get("documents", []), "reason": data.get("reason"),
            "coverage": "Reported figures available; original accounts require review." if results else "No usable financial figures available.",
            "limitations": ["Indicators are review triggers, not legal findings or proof of insolvency.",
                            "Missing currency or scale prevents monetary calculations; estimates are excluded.",
                            "Ratios are dimensionless; period changes use base currency units. No currency conversion is performed.",
                            "Restatements, accounting policy differences and audit qualifications require manual review."]}
