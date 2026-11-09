"""Conservative interpretation of provider error envelopes, without logging bodies.

The public financial endpoint reference currently documents the success schema,
not an exhaustive 404 code taxonomy. These explicit code/message aliases are
compatibility rules, not a claim that OpenRegister guarantees those codes.
Generic 404/Not Found and unfamiliar or conflicting signals remain unknown.
"""
import re

CODE_CAUSES = {
    "company_not_found": "company_not_found",
    "financial_data_not_found": "financial_dataset_not_found",
    "financials_not_found": "financial_dataset_not_found",
    "financial_dataset_not_found": "financial_dataset_not_found",
    "endpoint_not_found": "endpoint_not_found",
    "route_not_found": "endpoint_not_found",
    "invalid_endpoint": "endpoint_not_found",
}
MESSAGE_CAUSES = {
    "company not found": "company_not_found",
    "financial data not found": "financial_dataset_not_found",
    "financials not found": "financial_dataset_not_found",
    "financial dataset not found": "financial_dataset_not_found",
    "no financial data found": "financial_dataset_not_found",
    "endpoint not found": "endpoint_not_found",
    "route not found": "endpoint_not_found",
}


def classify_financial_404(body):
    """Read known envelope locations only; never return arbitrary provider text."""
    signals = []

    def inspect(value, field):
        if not isinstance(value, str):
            return
        if field == "code":
            cause = CODE_CAUSES.get(value.strip().lower())
        else:
            normalized = re.sub(r"\s+", " ", value.strip()).lower().rstrip(".")
            cause = MESSAGE_CAUSES.get(normalized)
        if cause:
            signals.append((cause, field))

    if isinstance(body, dict):
        for container in (body, body.get("error"), body.get("detail")):
            if isinstance(container, dict):
                for field in ("code", "message", "detail", "error"):
                    inspect(container.get(field), "code" if field == "code" else "message")
            else:
                inspect(container, "message")
    # A plain text response is not assumed to be a documented JSON envelope.
    causes = {cause for cause, _ in signals}
    if len(causes) != 1:
        return {"not_found_cause": "unknown", "classification_basis": "conflicting_signals" if causes else "no_specific_provider_signal"}
    return {"not_found_cause": causes.pop(),
            "classification_basis": "recognized_code" if any(field == "code" for _, field in signals) else "recognized_message"}
