# Synthetic German document samples — v2

Regenerate with `python -m scripts.document_examples`. Each folder contains input JSON, three deterministic Markdown drafts, structured validation and a lawyer checklist.

- [Individual](individual/vollmacht.md): fictional natural person and out-of-court civil-commercial dispute.
- [Corporate](corporate/vollmacht.md): fictional GmbH and fictional managing director with an explicitly synthetic authority reference.

Authority and fee drafts are complete for lawyer review, not legally approved. Both advance requests remain NOT_READY_FOR_ISSUANCE: genuine tax ID, unique invoice number and issuance date are intentionally missing. Bank credentials are not invented. All actions remain pending lawyer approval.

The 14-day payment wording and minute-by-minute recording method come from the explicit synthetic input policies; they are not defaults for other clients. The VAT calculation is an explicit demo configuration, not a conclusion that 19% applies to every case.

Compared with execution 26's preserved outputs, these documents have separate structured clauses, bounded powers, principal/representative distinction, protected reimbursement notice, conditional VAT and gross figures, line-item advances, issuance blockers and source/template/validation metadata. The original documents and workflow evidence were not rewritten.


| Scenario | Vollmacht | Fee agreement | Advance draft | Validation | Lawyer checklist |
|---|---|---|---|---|---|
| Individual | [Open](individual/vollmacht.md) | [Open](individual/fee_agreement.md) | [Open](individual/advance_invoice.md) | [JSON](individual/validation.json) | [Review](individual/review_checklist.md) |
| Corporate | [Open](corporate/vollmacht.md) | [Open](corporate/fee_agreement.md) | [Open](corporate/advance_invoice.md) | [JSON](corporate/validation.json) | [Review](corporate/review_checklist.md) |
