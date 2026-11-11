# API, configuration and cost safeguards

Installation and the single development launch command are in [README](../README.md). Never edit or export real credentials as part of workflow setup. n8n owns OAuth; Python provider adapters read private configuration. Environment/header names beginning LEGALFLOW remain compatible identifiers, not a separate product.

## Active service routes

| Route | Purpose / gate |
|---|---|
| GET /health | Development health |
| POST /v1/onboarding/preview | Synthetic typed request, SQLite idempotency, draft documents |
| POST /v1/onboarding/corporate-intelligence | Zero-network optional corporate helper; max three cached operations |
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
