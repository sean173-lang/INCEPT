# Project 3 submission checkpoint

This checklist follows the supplied project requirements; an original course brief was not found locally. The tested implementation was published on the feature branch at `5c540b5`; this documentation update prepares review through a pull request. The default branch must change only after manual review and merge.

| Requirement | Status and evidence |
|---|---|
| n8n primary orchestration | VERIFIED: integrated execution 19, review-ready outcome |
| Three real external integrations | VERIFIED: Gmail, Sheets, Calendar in execution 19; independent executions 12–14 |
| Autonomous bounded research → synthesis → report | VERIFIED for the approved German demo: official BGB §286 source retrieved and checked; not general autonomous legal advice |
| RAG / grounding | IMPLEMENTED and offline tested: curated guidance, source attribution and unresolved claims |
| Two distinct generated reports | PRESENT: individual and corporate examples under examples/reports; clearly synthetic offline outputs |
| Error handling and review branches | IMPLEMENTED / regression tested; no uncertain deadlines or approval execution |
| Corporate DE/UK extension | FIXTURE VERIFIED: isolated n8n executions 20–23; no live registry end-to-end verification |
| Primary-stack justification | PRESENT: docs/stack_decision.md |
| 2–3 GTM future sprints | PRESENT: gtm_future_sprints.md |
| Reproducible 5–7 minute demo | DOCUMENTED: docs/demo_script.md; live services/account state still required for a fresh real run |
| Clean GitHub submission | Feature branch pushed and verified at 5c540b5; documentation update, fresh security checks and PR review required before main publication |
| Gradio UI | PLANNED separate milestone, not implemented here |

Before submission: inspect the complete diff and secret exclusions, run the full suite, review sample artifacts, and manually review the feature-to-main pull request. Do not describe the cache-only corporate extension as a live provider test.


## Isolated n8n validation (2026-11-11)

Four separate inactive fixture test copies executed successfully in n8n: individual **20**, German company **21**, UK company **22**, ambiguous **23**. The first three produced review-ready bundles; the ambiguous case stopped at NEEDS_REVIEW. Google ingress/read operations and legislation retrieval were explicitly substituted, while local onboarding, adapters, evidence checks and report assembly ran for real. Company fixtures remain UNVERIFIED; these executions do not establish live registry or new Google connectivity. Original corporate workflow 0zruCCbLGNUZJ8Gt and proven FeRkXfcrj8dceBZh remain unchanged.

Sanitized trace summary: [execution evidence](docs/incept_corporate_n8n_validation.json). Full local artifacts: `reports/incept_corporate_n8n_validation/`. Regression suite: **285 passing tests**. Gradio remains planned.


## German document quality overhaul (2026-11-11)

Implemented: versioned separate German templates, 32 checked official source records, optional typed document inputs, deterministic rendering and validation, explicit missing-information/issuance states and two generated synthetic bundles in examples/documents. Authority/fee samples are complete for lawyer review; advances remain NOT_READY_FOR_ISSUANCE because no genuine fiscal/invoice metadata is fabricated. This is not legal approval, structured e-invoice support or production readiness. Existing saved bundles and live execution evidence are preserved. See docs/legal_document_generation.md and docs/legal_document_quality_audit.md.

Validation after this overhaul: **314 offline tests passed**, including **19 document-specific tests**. Workflow export structures/links and changed-file privacy scans passed; no live workflow execution or legal approval is claimed.


Actual document-engine HTTP checkpoint: both synthetic scenarios passed on the updated port-8003 service; failed-document states cannot approve matters or issue documents. Final suite: **315 tests passed**. See [sanitized HTTP evidence](docs/legal_document_http_validation.json). Template/legal approval and valid issuance data remain unresolved. No new n8n execution or external action was performed.


## Live document v2 checkpoint before Gradio

Actual n8n execution **28** verified real approved-message intake, read-only Google checks, official German legal-source retrieval and FastAPI template v2.0.0 generation. All three drafts remained pending professional approval; representative authority was asserted only, and the advance was NOT_READY_FOR_ISSUANCE. See [sanitized checkpoint](docs/incept_live_documents_v2.md). The reproducible export removes account/credential/spreadsheet bindings and does not include the one-email sender. This checkpoint does not activate workflows, rerun APIs or start Gradio.
