# API, configuration and cost safeguards

Installation and the single development launch command are in [README](../README.md). Never edit or export real credentials as part of workflow setup. n8n owns OAuth; Python provider adapters read private configuration. Environment/header names beginning LEGALFLOW remain compatible identifiers, not a separate product.

## Active service routes

| Route | Purpose / gate |
|---|---|
| GET /health | Development health |
| POST /v1/onboarding/preview | Synthetic typed request, SQLite idempotency, draft documents |
| POST /v1/onboarding/corporate-intelligence | Zero-network optional corporate helper; max three cached operations |
| POST /v1/onboarding/synthesis | Optional synthetic-only AI assessment; disabled by default; authenticated opt-in, persistent request/token budgets and strict output validation |
| POST /v1/onboarding/research/verify | Check orchestrator-provided official source bytes; helper makes no request |
| POST /v1/company/search | DE/UK adapter search; fixtures by default |
| POST /v1/company/verify | Detail/registration identity matching; name alone insufficient |
| POST /v1/research/search | Bounded exact-identity Tavily Search after verification |
| POST /v1/rag/query | Local jurisdiction-filtered corporate references; development-only |
| POST /v1/research/runs | Create bounded development research run |
| POST /v1/research/runs/{run_id}/plan | Next allowlisted action |
| POST /v1/research/runs/{run_id}/tools | One ordered, idempotent step; maximum two iterations |
| POST /v1/research/runs/{run_id}/report | Structured source-linked result |
| GET /v1/usage | Credential-free estimated usage |

There are no financial/annual-account, approval, issuance or send routes. The retired `financial_disclosures` research topic is explicitly rejected with 422; retained topics are corporate_identity, litigation and regulatory_risks. No retained workflow uses the retired topic. Generic usage accounting rejects retired financial/document-download operations before a mock, cache or network callback. UK adapters restrict paths and reject accounts-only retrieval.

## Budget and cache behavior

`UsageTracker` preserves provider, operation, UTC timestamp, estimated credits/cost, cache hit, outcome and session metadata. It does not log query text, credentials, headers or bodies. Credits are estimates, not confirmed billing. Unknown monetary pricing displays **Cost unknown** and blocks execution under a finite spend cap.

Company search/details and Tavily Search retain JSON caching, expiration, process-level duplicate reservation and failure tracking. No cache miss in the corporate-intake helper can invoke a provider callback. Only provenance-attested provider caches or separately labeled approved demo evidence qualify; unknown provenance remains unavailable. Cached registry records are never represented as fresh verification.

Paid-capable cache misses require server approval and fit configured OpenRegister-credit, Tavily-search and session-spend limits. HTTP request bodies cannot approve spending. Defaults use fixtures and paid access disabled. Exact historical money prices are not hardcoded. Read-only does not necessarily mean free: obtain request-specific authorization and verify allowance/billing before a controlled provider call. Tavily uses bounded Basic Search, never the Research endpoint, with 20-second timeout and no retries/redirects.

Private historical ledgers/caches were not reset or deleted during cleanup because they may establish earlier spending/audit history. They are ignored and are not imported by the retired financial subsystem. `.env` was not changed. Configure secrets outside Git; the live environment mode requires a nonempty service token. Loopback development is not tenant isolation or production access control.

## Approval and evidence

Every action remains pending_lawyer_approval; no external action executor exists. Complete-looking documents are not approved. Representative authority, applicable law, conflicts and fiscal particulars require professional review. Original workflow/execution evidence is immutable during normal code updates. Offline tests block sockets and use mocks/temporary stores; no external credits are consumed.

See [Tavily validation](tavily_integration.md), [document rules](legal_document_generation.md) and [live evidence](live_integration_evidence.json). Run `python -m scripts.submission_audit` after explicitly staging reviewed files; it scans staged content and Git history without printing matches. No signed-URL exceptions are allowlisted.

## Corporate cache and warning contract (audit repair)

Both profile/detail adapters now write the versioned `CorporateCacheRecord` format: provider, jurisdiction, registry identifier, original UTC retrieval timestamp, provenance origin/synthetic flag, unverified provider-report status, and payload. Only the successful transport callback labels a record as provider-reported; fixtures are separately labeled synthetic. This records acquisition provenance, not independent truth or representative authority.

UK profile results remain dict-compatible and German results retain `model_dump`; metadata includes `cache_accessed_at`, `cache_hit`, age and freshness. Accessing a record does not rewrite its retrieval date or stored bytes. Only profile calls gain UK disk caching; existing officer/search/filing operations retain their contracts. Corporate intake still performs zero provider requests, including after restart or failure.

Legacy cache entries are not silently migrated. Missing essential provenance leaves a record unusable for corporate assessment, and direct detail verification rejects untraceable legacy snapshots. No automatic paid refresh is introduced. Do not manufacture attestation flags to reuse an old cache; authorize original-source retrieval separately if necessary.

Corporate `warnings` carry stable IDs, categories, messages and source IDs. Final n8n assessment exposes the same warnings as `review_warnings`; actual missing-information messages also populate `missing_information`, while freshness, identity, provenance, authority and provider-failure warnings retain distinct categories. The final `uncertainty` list includes all warning messages with stable deduplication. Individual intakes receive no spurious corporate warnings. Existing v2 document and lawyer-approval validators are unchanged.

Budget/duplicate safeguards in generic live services remain process-scoped: their JSONL events are not a transactional cross-process reservation ledger. The retired isolated profiles' crash-safe credit ceilings are not claimed here. Cache-only intake needs no paid reservation; successful identity caches and matter idempotency survive restart. A multi-process paid deployment would need durable reservations before enabling automatic live tools. No such deployment or paid request is enabled by these repairs.

Optional AI has separate, default-disabled billing/approval/model/request/token controls; existing paid-provider flags cannot enable it. It does not modify registry/Tavily budgets or permit financial calls. See [AI synthesis](ai_synthesis.md) for the private SQLite reservation semantics and current offline-only verification status.
