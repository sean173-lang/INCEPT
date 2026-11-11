# Ordinary German intake — first controlled live test (historical)

The user authorized one fictional self-addressed Gmail inquiry and at most two `gpt-4o-mini` inference requests: one extraction and one synthesis. Billing dashboard access was explicitly waived for the Ironhack key; no account balance or billing settings are claimed verified. No purchases, recharge changes or other paid providers are authorized.

Latest continuation: see [extraction repair and live retry](natural_intake_retry.md). This section records the earlier execution, not the current final state.

## Historical result

**Failed at extraction; not an end-to-end success.** One message was sent in execution **29**, the exact Gmail ID retained in ignored local evidence. The separate inactive 25-node workflow `uUTlIVY4mlkH9Uf5` executed as **30**. Exact-message metadata validation, body retrieval and plain-text decoding passed. The extraction helper made one live transport attempt and returned `extraction_failed_or_invalid_no_retry`. The next validation node stopped execution. Synthesis, corporate research, source retrieval and document generation were not reached.

The original extraction failure handler did not preserve the provider exception/rejected-output diagnostics or token usage. Therefore the precise cause, successful provider completion, actual token consumption and actual charge are **unknown**. Do not equate the HTTP 200 helper response with model success. Safe diagnostic recording and incomplete-response usage preservation were added afterward and tested offline. **No extraction retry was made.** A new extraction attempt requires fresh explicit approval, a new isolated ledger and preservation of the failed record; do not reset it or silently use the reserved synthesis allowance for another extraction.

The two configured token ceilings were input/output 16,000/1,800 for extraction and 60,000/3,500 for synthesis, with 40-second timeouts and zero SDK retries. At the officially published standard rates of USD 0.15 input / USD 0.60 output per million tokens, the conservative ceilings are USD 0.003480 for extraction and USD 0.011100 for synthesis. These are estimates, not confirmed billing. The read-only model metadata endpoint returned HTTP 200 before execution. Model documentation currently marks the model deprecated; no alternative model is selected automatically.

- [Official model specification and prices](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

## Implementation

- `scripts/natural_intake.py`: typed email and strict model-output schemas; exact contiguous, word-boundary excerpt validation; no inferred dates/authority; private persistent one-attempt reservation, duplicate cache and no retry after failed/uncertain attempts. Ordinary email content is untrusted. Excerpt checks establish attribution, not semantic truth or role accuracy.
- `POST /v1/onboarding/extract`: disabled by default. Enabling requires constructor-supplied approval/budgets, exact approved message metadata and service authentication. No HTTP caller may authorize spending. Structured-JSON intake remains supported unchanged.
- `scripts/payment_research.py`, `references/payment_dispute.json`: wording checks for BGB sections 611, 320 and 641, relevant to service payment obligations, disputed performance and possible work-contract acceptance. Contract classification remains unresolved. No automatic default or deadline inference. The helper verifies submitted wording; n8n performs the source request. Its receipt metadata does not independently attest network acquisition.
- `scripts/ai_evidence.py`: accepts exact trusted payment-reference cards alongside existing references; caller metadata is not promoted.
- `scripts/incept_prose_workflow.py`: builds a separate inactive manual-only 25-node workflow; sanitized export `workflows/incept_prose_intake_dev.json`. Default account/message/service values are placeholders, not real credential bindings. It is not a ready-to-run live configuration.

The actual local run used an isolated loopback service on port 8005 with its own private SQLite databases; that service was stopped after failure. Existing services were not restarted or reconfigured. Each stage has one persistent request slot; no fallback model, retries or financial endpoints. A failed extraction stops downstream processing. The corporate identity is the explicitly fictional INCEPT DEMO GmbH, with synthetic catalogue identifiers; no genuine registry verification or live registry call is claimed.

## Reproduce offline

```sh
python -m unittest discover -s tests -q
python -m scripts.incept_prose_workflow
```

Tests cover exact German prose excerpts, unsupported amounts/dates/representatives, missing authority, strict schemas, metadata isolation, injection checks, persistent duplicates/failures, budgets, authentication, safe diagnostics, source changes/unavailability, and the export's executable metadata/decoding nodes. Existing document, approval and synthesis regression tests remain.

Local evidence: ignored `reports/incept_prose_live/execution_summary.json`; raw email/execution traces and request ledgers remain under ignored `data/incept_prose_live/`. Never commit private bindings, the helper token, MIME body or raw traces. All 15 pre-existing live workflows and 49 protected evidence files were hash-checked unchanged. No mandate was accepted or invoice issued. No Gradio readiness or successful live reasoning is claimed.
