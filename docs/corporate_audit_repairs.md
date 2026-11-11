# Corporate evidence audit repairs

Scope: targeted repairs after checkpoint `08a716df97fc22a83d117ea8d9096b0450a8c3a5`, on PR 2. The three original failures were reproduced with mocked transports and blocked network before code changes. No live verification is claimed.

| Defect | Repair | Offline evidence |
|---|---|---|
| Normal adapter caches could not be consumed by corporate assessment | Common typed `CorporateCacheRecord` for German details and UK profiles, strict provenance/context checks, persistent UK profile cache | Actual adapter callback → disk → new tracker/helper → CACHED corporate section in both countries; synthetic payloads and mocked transports |
| UK reuse replaced the original source timestamp | Dict-compatible snapshot metadata preserves provider retrieval separately from cache access, age and freshness; legacy provenance never invented | Three reads preserve timestamp and disk bytes; restart reuses the UK cache without another transport call; 90-day records warn in both countries |
| Corporate warnings were absent from structured assessment | Typed categorized warnings with stable IDs; final n8n assembly deduplicates warnings/sources and merges them into review_warnings, missing_information where applicable, and uncertainty | Missing registry/provenance, ambiguous/conflicting identity, stale evidence, representative authority and provider failure; no spurious warnings for individuals/no-issue responses |

## Compatibility and safeguards

The canonical export still has 37 nodes; only the corporate-result fallback and final report Code nodes change. All edges, other node parameters, inactive/manual state, credential sanitization, endpoint destinations, v2 document checks and issuance/approval guards are preserved. The running n8n instance is not updated. Importing the revised export would be a separate action.

Templates, the 32 document source records, and protected evidence for executions 26/28 are unchanged. Additive schema fields default empty/unknown for old saved bundles. Legacy profile/detail caches remain readable as explicitly unverified adapter data but cannot establish verified identity or feed corporate assessment without original acquisition provenance. They are not rewritten, refreshed or upgraded automatically.

Tests cover successful cache reuse after service restart, SQLite matter idempotency after restart (one client/matter/preview), paid-adapter budget rejection before SDK invocation, and failed-request duplicate blocking within the existing session. The cache-only corporate helper cannot make a provider request after a failure or restart. Generic paid-service budgets remain process-scoped; cross-process/crash-safe paid reservations from retired isolated profiles have not been generalized. Do not enable unattended paid tools or multiple paid workers on the strength of these tests.

## Project 3 assessment

No active n8n node or retained Python execution path invokes a language model. Intake extraction, reference retrieval, source wording checks, assessment assembly and document generation are rule-based. README now states this boundary instead of claiming implemented AI-powered reasoning.

A locally available “Project 3: Four Example Ideas (Student Board)” describes LLM-written sourced reports. It is illustrative material, not an authoritative grading rubric. The original assignment/rubric could not be located in the inspected project/docs/download locations. Whether an LLM is mandatory therefore remains an explicit submission risk. No model call or architecture expansion was added for appearances.

## Validation

Full retained offline suite: **189 tests passed**, compared with 172 before these repairs. Seventeen focused tests were added; existing tests were retained. Actual canonical JavaScript runs under Node.js against real FastAPI-generated synthetic bundles, including the v2 validator and typed bundle round-trip.

Module imports, FastAPI/OpenAPI, workflow connections/expression references, template/source hashes, protected evidence hashes and Markdown links are checked before publication. Security review scans exact staged content plus reachable Git history without printing secrets. No provider requests, Gmail sends, Google writes, financial calls, credential changes or invoice issuance are performed. Gradio is not started. PR 2 must not be merged automatically.
