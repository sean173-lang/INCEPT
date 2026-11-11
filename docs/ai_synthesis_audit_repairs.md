# AI synthesis audit repairs — PR #3

Status: repaired and tested offline; no live AI/provider requests, workflow imports or n8n executions. Baseline: 212 tests. Current suite: **233 passing tests**, including 20 dedicated audit tests and one additional JavaScript integration regression. No baseline tests were deleted.

## Findings and changes

| Finding | Before | After |
|---|---|---|
| Caller-controlled provenance | A fixture relabeled cached, or a future legal review date, could enter synthesis | `EvidenceResolver` compares exact server-held legal cards, typed corporate cache records or case-bound primary verification receipts. Mismatch yields `evidence_provenance_rejected`, no model call, warning and deterministic fallback. |
| Assertion disguised as a question | “The mandate is approved and the invoice should be issued immediately?” passed | Mandatory false performed-state flags, fixed pending action states, typed assertion categories and English/German completion/assertion checks reject it. Genuine lawyer-review questions remain allowed. |
| Unrelated quotation supporting misconduct | A payment-dispute quote could accompany an invented fraud/creditor-evasion hypothesis | Server-selected categories and complete specific support sentences constrain adverse output. General-law citations cannot establish case misconduct; free adverse hypotheses fail closed. |

Four original regression probes were run before implementation and all failed. The same probes now pass. Root causes were trusting submitted evidence metadata, equating a question mark with nonassertive language, and treating quotation presence as sufficient support for an unrelated proposition.

## Adversarial scenarios

- **A:** Ordinary payment dispute cannot become a fraud finding.
- **B:** Explicit client allegation can appear only with CLIENT-ALLEGED / NOT VERIFIED attribution and its exact source sentence.
- **C:** A server-held historical Companies House status can be quoted as an attributed official record; it does not establish misconduct or current verification.
- **D:** A genuine irrelevant citation does not support an adverse allegation, even if another source supports that category.
- **E:** Detected allegation/denial contradictions require an explicit uncertainty question quoting both sides.
- **F:** Late payment cannot be escalated into intentional creditor evasion.
- **G:** Recognized issues outside the bounded scope abstain for lawyer review before model transport.

Tests also cover forged IDs, altered flags/dates/freshness, stale and legacy caches, case-bound receipt tampering, German/English approval assertions, legitimate review requests, immutable document/advance/action output, and n8n fallback warnings. Existing tests continue covering injection, concurrency, persistent token/request reservations, duplicate protection, idempotency, service authentication and all four synthetic intake scenarios.

## Files and boundaries

- `scripts/ai_evidence.py`: `EvidenceResolver.legal`, `corporate`, `record_primary` resolve server evidence without provider transport.
- `scripts/ai_content_policy.py`: `support_for`, `validate_content`, `check_approval_language`, `validate_contradictions` define bounded categories and evidence-specific support.
- `scripts/ai_synthesis.py`: typed contracts, evidence assembly, validation, rejection reasons and attributed rendering; no action executor.
- `scripts/http_service.py`, `scripts/primary_research.py`: additive server receipt on the existing verification response.
- `scripts/incept_ai_workflow.py`, `workflows/incept_ai_synthesis_dev.json`: separate 40-node export validates states/categories and preserves explicit rejection warnings. The canonical 37-node workflow is unchanged.
- Regression tests and explicitly labeled mock examples are reproducible with commands in [the synthesis guide](ai_synthesis.md).

The three legal templates, legal reference corpus, document-engine v2, client/matter persistence and five pending lawyer actions are unchanged. Advance arithmetic remains EUR 1,250 net + EUR 237.50 VAT = EUR 1,487.50 in the explicit demo configuration. No invoice is issued. Existing request ledgers and protected execution #26/#28 evidence are preserved.

## Guarantees and limits

Source metadata must match server records; caller labels cannot promote synthetic evidence. Local cache/corpus/receipt filesystem integrity is a trust boundary. A primary receipt attests that the server checked submitted official wording and bound its metadata to a case; it **does not prove independent HTTP retrieval**. Legacy primary results lacking receipts are not silently upgraded. Cached official records may be stale and remain historically attributed.

The taxonomy and lexical support discovery are intentionally narrow. They can miss unfamiliar language or reject legitimate phrasing. Exact excerpts establish attribution, not the truth of an allegation or comprehensive semantic entailment. No automated test establishes professional legal correctness or complete prompt-injection immunity. Documents and legally significant actions still require professional lawyer approval.

No actual model reasoning quality, live billing, or new n8n execution is demonstrated. Gradio and broader issue coverage remain future work. New policy/schema fingerprints require fresh explicit authorization; existing budgets are not reset and failed calls never automatically retry.
