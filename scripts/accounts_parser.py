"""Conservative XBRL/iXBRL extraction. PDFs and ambiguous facts require review."""
import re
from decimal import Decimal
from xml.etree import ElementTree as ET

from scripts.financial_analysis import number

# Exact, limited UK taxonomy concept allowlist; never map free-form labels.
CONCEPTS = {
    "TurnoverRevenue": "revenue", "TurnoverGrossOperatingRevenue": "revenue", "Revenue": "revenue",
    "ProfitLoss": "net_income", "ProfitLossForPeriod": "net_income",
    "Assets": "total_assets", "TotalAssets": "total_assets", "Equity": "equity",
    "ShareholderFunds": "equity", "Liabilities": "liabilities",
    "CashBankOnHand": "cash", "CashCashEquivalents": "cash", "CurrentAssets": "current_assets",
    "CreditorsDueWithinOneYear": "current_liabilities", "CurrentLiabilities": "current_liabilities",
}
NS = {"http://www.xbrl.org/uk/gaap/core/2009-09-01",
      "http://www.xbrl.org/uk/gaap/core/2009-09-01/", "http://xbrl.frc.org.uk/fr/2023-01-01/core",
      "http://xbrl.frc.org.uk/fr/2024-01-01/core", "http://xbrl.frc.org.uk/fr/2025-01-01/core"}


def local(tag):
    return tag.rsplit("}", 1)[-1]


def parse_accounts(content, company_number, source):
    if len(content) > 5_000_000:
        return []
    if b"\x00" in content or b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        return []
    namespaces = {}
    import io
    try:
        for _, pair in ET.iterparse(io.BytesIO(content), events=("start-ns",)):
            namespaces[pair[0]] = pair[1]
        root = ET.fromstring(content)
    except ET.ParseError:
        return []
    contexts, units = {}, {}
    for element in root.iter():
        if local(element.tag) == "context":
            descendants = list(element.iter())
            identifier = next((e.text for e in descendants if local(e.tag) == "identifier"), None)
            if not identifier or identifier.strip().upper() != company_number.upper():
                continue
            instant = next((e.text for e in descendants if local(e.tag) == "instant"), None)
            start = next((e.text for e in descendants if local(e.tag) == "startDate"), None)
            end = next((e.text for e in descendants if local(e.tag) == "endDate"), instant)
            dimensions = sorted((e.get("dimension", ""), e.text or "") for e in descendants
                                if local(e.tag) in ("explicitMember", "typedMember"))
            # Dimensions can describe segments, consolidation, or restatements. Keep
            # them separate and do not assume an undimensioned context is standalone.
            contexts[element.get("id")] = (start, end, str(dimensions))
        if local(element.tag) == "unit":
            measures = [e.text or "" for e in element.iter() if local(e.tag) == "measure"]
            if len(measures) == 1 and not any(local(e.tag) == "divide" for e in element.iter()):
                prefix, _, currency = measures[0].partition(":")
                if namespaces.get(prefix) == "http://www.xbrl.org/2003/iso4217" and re.fullmatch("[A-Z]{3}", currency):
                    units[element.get("id")] = currency
    groups = {}
    for element in root.iter():
        context = contexts.get(element.get("contextRef"))
        if not context:
            continue
        tag = local(element.tag)
        if tag == "nonFraction":
            prefix, _, concept = element.get("name", "").partition(":")
            namespace = namespaces.get(prefix)
        else:
            concept = tag
            namespace = element.tag[1:].split("}")[0] if element.tag.startswith("{") else None
        if namespace not in NS or concept not in CONCEPTS:
            continue
        if any(local(e.tag) == "exclude" for e in element.iter()):
            continue
        # Only parse plain decimal literals and a known dot-decimal transform.
        fmt = element.get("format", "").split(":")[-1]
        if fmt not in ("", "num-dot-decimal", "numdotdecimal"):
            continue
        value_text = "".join(element.itertext()).strip()
        if fmt:
            value_text = value_text.replace(",", "")
        if not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value_text):
            continue
        value = number(value_text)
        scale = number(element.get("scale", "0"))
        if value is None or scale is None or scale != scale.to_integral_value() or abs(scale) > 12:
            continue
        if element.get("sign") not in (None, "-"):
            continue
        if element.get("sign") == "-":
            value = -value
        start, end, dimensions = context
        # Balance-sheet facts are instant, income facts have a duration.
        metric = CONCEPTS[concept]
        if (metric in ("revenue", "net_income")) != bool(start):
            continue
        group = groups.setdefault((start, end, dimensions), {})
        fact = {"value": str(value), "currency": units.get(element.get("unitRef")),
                "scale": str(Decimal(10) ** int(scale)), "source_field": concept}
        existing = group.get(metric)
        group[metric] = fact if existing is None or existing == fact else {"value": None, "conflict": True}
    periods = []
    for (start, end, dimensions), facts in groups.items():
        if start is None and any(s and e == end and d == dimensions for s, e, d in groups):
            continue
        combined = dict(groups.get((None, end, dimensions), {}))
        combined.update(facts)
        periods.append({"period_start": start, "period_end": end, "scope": "unknown",
                        "context_dimensions": dimensions, "facts": combined, "source": source})
    return periods
