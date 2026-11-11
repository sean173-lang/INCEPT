# Repository cleanup verification

The cleanup branch starts at checkpoint `f5f751f5bf46a8fb0182a4edfd6ec0fd39497391`; the original development branch and Git history remain intact.

## Scope and retained behavior

Financial extraction, ratios, paid financial orchestration, standalone financial ledgers/configuration entry points and historical exports are retired. The shared adapters retain German/UK identity, officer and legal-filing metadata research. Financial operations are rejected before cache, fixtures or transport. The financial-disclosures planner topic now returns validation error 422; current legal research topics remain compatible.

One canonical export remains: [incept_live_documents_v2.json](../workflows/incept_live_documents_v2.json). Its bytes and 37-node graph are unchanged from the checkpoint. Four layered Python builders remain because they contain required validators and routing. No running n8n workflow was changed.

The v2 templates and 32 official document-source records are retained. Individual, German corporate and UK corporate examples remain synthetic. Recorded execution 26 demonstrates isolated counterparty research; this does not claim a general separate counterparty branch in the canonical graph. Executions 26/28 evidence is preserved: all 49 protected private files match their pre-cleanup hashes.

## Verification

- Before: 319 passing tests. After: **172 passing offline tests**.
- [Test ledger](repository_cleanup_tests.md): 154 old function names removed, seven new/replacement names added (one is a renamed export assertion). Financial/historical behavior was retired with its tests; active failures were not suppressed.
- Every retained Python module imports; FastAPI startup/routes, synthetic onboarding, identity adapters, Tavily mocks, RAG, template rendering, invoice arithmetic, approval and idempotency are covered by the full suite.
- Canonical JSON connections and node-expression references validate; templates are byte-identical to the checkpoint.
- Security review covers exact staged content and all reachable Git blobs using secret patterns and current configured secret values. This is a heuristic scan, not proof that every unknown secret is absent.
- No live provider requests, Google actions, paid calls, invoice issuance or Gradio work occurred.

## Exclusions and limits

Seven explicitly inspected ignored historical financial reports were removed. Private financial caches/credit ledgers, databases, backups and raw execution evidence remain ignored and untouched because deleting audit history is unnecessary. They are not active application dependencies and are not published.

One requirements file replaces separate service/accounts requirements. Tavily's compatible SDK constraint is retained. Environment examples contain no keys; `.env` is unchanged. Production authentication/tenancy, lawyer approval, signed legal documents and compliant invoicing remain outside this development demo. Automated checks do not provide legal approval.

The cleaned backend is ready for a separate Gradio development task; Gradio is not implemented or started here. The PR must be manually reviewed and merged.

## Checkout metrics

| Measure | Result |
|---|---:|
| Files before | 194 |
| Files after | 128 |
| Original files removed | 71 |
| Original files retained | 123 |
| New audit/evidence/test files | 5 |
| Original files consolidated into current docs/graph (subset of removals) | 49 |
| Bytes before | 1,575,092 |
| Bytes after | 722,286 |
| Size reduction | 54.1% |

Metrics count tracked file content, excluding `.git`, ignored runtime stores and local installed packages. Removed/consolidated files remain recoverable in Git history; no archive directory was created. See the [pre-change inventory](repository_cleanup_inventory.md) for each original file classification.
