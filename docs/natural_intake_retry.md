# Extraction repair and live retry

## Actual outcome

**Not an end-to-end AI success.** The existing fictional email was reused; no email was sent in this task. One newly authorized extraction call and one separately renewed synthesis call used `gpt-4o-mini`, zero SDK retries, and persistent one-attempt ledgers. No credits were purchased and billing settings were not changed. The isolated helper was stopped after testing. All work remains uncommitted.

The exact cause of historical extraction execution **30** is unknowable from the retained evidence: its failure handler discarded provider output and exceptions. Do not assert that a later reproduction proves its exact cause.

Execution **31** established the retry's actual defect: OpenAI returned a completed response, but the model generated a paraphrased `matter_summary` and some non-exact proposals despite the excerpt-only prompt. Strict local validation rejected them. It was not a budget failure or an invalid JSON response. Safe diagnostics and private response evidence now distinguish provider/transport, schema and source-excerpt failures and preserve available token usage.

The retained response was then grounded **without another model call**: unambiguous case/whitespace matches select the original source text, unsupported proposals are excluded, and the unsupported summary is discarded in favor of an already-supported factual excerpt. Identity and role mismatches still fail closed. Exclusions and restorations are explicit lawyer-review warnings; no unsupported paraphrase is promoted to a fact. Unknown sender identity and authority remain unknown. Exact-excerpt validation still applies after mapping.

- **32:** grounded extraction and three v2 drafts passed; corporate request rejected because persisted `ClientRecord` was sent instead of `ClientInput`. Corrected the workflow mapping; strict schema retained.
- **33:** synthetic corporate research passed; legal-source transport failed because text response data was read from the wrong n8n field. The text transport was also lossy. Reused the canonical workflow's binary-source retrieval and existing declared-charset decoder, with original-byte hashes and explicit lossy-decoding rejection.
- **34:** all three official source checks and synthesis were reached. The model returned schema-valid output, but factual prose was not extractive. Existing content validation rejected it. The workflow stopped with an error, preserving the deterministic assessment. No model retry occurred.

## Usage and evidence

| New request | Input tokens | Output tokens | Estimated USD |
|---|---:|---:|---:|
| Extraction, completed provider response | 854 | 308 | 0.0003129 |
| Synthesis, completed response rejected locally | 4,933 | 2,755 | 0.00239295 |
| Total newly authorized calls | 5,787 | 3,063 | 0.00270585 |

Rates: USD 0.15 input and USD 0.60 output per million tokens, [official model documentation](https://developers.openai.com/api/docs/models/gpt-4o-mini). These are estimates, not confirmed billing. Execution 30 usage/cost remains unknown and is excluded. Including it, there have been three cumulative model attempts, with renewed explicit user authorization for synthesis.

Corporate evidence is **SYNTHETIC / UNVERIFIED** for the fictional INCEPT DEMO GmbH. No live registry or financial request was made. The client and fictional Nordlicht Projektservice GmbH remain distinct; the source amount is 18.750 Euro and chronology remains approximate September/October, without an invented year or deadline.

Original official bytes were retrieved and checked for:

- [BGB §611](https://www.gesetze-im-internet.de/bgb/__611.html): payment/performance obligations under a service contract.
- [BGB §320](https://www.gesetze-im-internet.de/bgb/__320.html): potential withholding of counterperformance.
- [BGB §641](https://www.gesetze-im-internet.de/bgb/__641.html): payment maturity on acceptance if work-contract rules apply.

These are reference rules, not confirmed case findings. Contract classification, terms, performance, acceptance, maturity and objections require original evidence. No default or deadline is established. n8n performed the retrieval; the helper checked submitted source bytes/wording, not independent acquisition. Full source URLs, timestamps, hashes and charset are in ignored local evidence.

## Artifacts and safeguards

Ignored `reports/incept_prose_retry/` contains the deterministic `mandate_assessment.md`, three document drafts, reviewed bundle and sanitized execution summary. Raw provider responses, Gmail traces, tokens and request ledgers remain private under ignored `data/`. The unaccepted synthesis is not included as valid analysis in the report.

- Vollmacht: `MISSING_INFORMATION`.
- Fee agreement: `MISSING_INFORMATION`.
- Advance request: `NOT_READY_FOR_ISSUANCE`.
- Explicit demo arithmetic: EUR 1,250 net + EUR 237.50 VAT = EUR 1,487.50. No prior work is billed.
- All five actions remain pending lawyer approval. No mandate acceptance, invoice issuance, external client contact, Calendar/Sheets write or new Gmail send.
- Same matter identity across executions 32–34 confirms local idempotency.
- Canonical 37-node and separate 40-node workflows, legal-document v2 templates/engine, historical workflows and protected execution evidence are preserved. Only new inactive test copies were imported.

## Validation and remaining blocker

The full offline suite passes **255 tests**. Tests exercise mocked SDK wire responses, exact German spans, excluded paraphrases, unsupported identities/amounts, persistent no-retry budgets, safe failure diagnostics and token retention, typed client mapping, lossless source bytes, workflow exports, structured JSON compatibility, document arithmetic and approval controls.

Changed implementation: `scripts/natural_intake.py`, `scripts/incept_prose_workflow.py`, `scripts/payment_research.py`, and additive usage/error diagnostics in `scripts/ai_synthesis.py`; HTTP wiring and server evidence references are preserved from the preceding uncommitted work. No validation was relaxed to accept the rejected synthesis.

Before a successful live AI demonstration, the synthesis output contract needs reliable source-excerpt selection for factual fields while keeping conditional reasoning separate. Test that repair offline against the retained response. Another live synthesis requires fresh approval; the current allowance is spent. Gradio readiness and professional legal approval are not established.
