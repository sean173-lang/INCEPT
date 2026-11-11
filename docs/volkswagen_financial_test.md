# Controlled Volkswagen financial test

This standalone CLI allows at most one OpenRegister financial request for verified
company `DE-HRB-P1103-100484-P2413`. It reads the successful direct-detail identity
evidence from the identity SQLite database in read-only mode. It does not run
company searches, details, n8n, OpenAI, Tavily, document downloads or research loops.
The development service and existing n8n workflow remain unchanged.

Before implementation, financial retrieval (`german_register.py`), the financial
cache, Decimal analyzer, report renderer and API usage controls were inspected.
This profile reuses the existing response validator, conservative HTTP error
classification, Decimal analysis, financial section renderer and usage cache keys.
It reads/writes the existing financial-cache envelope format. Its independent
durable ledger replaces process-scoped budgeting for this single controlled test.

## Current preparation result

The saved identity continuation is verified against actual OpenRegister evidence:
VOLKSWAGEN AKTIENGESELLSCHAFT, Germany, Braunschweig, HRB 100484. The local preview
found no reusable financial response in either the financial cache or usage cache.
No live financial request or financial approval has been executed.

The separate ignored directory `data/volkswagen_financial_test/` contains the new
SQLite ledger, a private approval file when approved, and the private financial
report after execution. The existing identity ledger is never reused as financial
state or reset. Financial ledger initialization is additive only in its own path.

## Budget and request

The [official financial endpoint](https://docs.openregister.de/endpoint/company-financials)
and [pricing documentation](https://docs.openregister.de/pricing) were reviewed on
November 10, 2026. Company financials cost **10 estimated credits**. Monetary cost
is **Cost unknown** because account inclusion and entitlement have not been checked.
This estimate is not confirmed billing. Pricing review expires November 17, 2026;
execution fails closed afterwards pending manual documentation review. Policy
changes do not reset existing financial accounting.

The only possible request is:

```text
GET https://api.openregister.de/v1/company/DE-HRB-P1103-100484-P2413/financials
```

The financial budget is independently capped at 10 credits and one request.
Reservations commit before network I/O. SQLite serializes concurrent callers;
pending attempts, process crashes, timeouts and failed responses cannot trigger a
retry after restarting. Redirects, proxies, transport retries and fallback calls
are disabled. Preserve this directory: deliberate deletion or another checkout
can defeat local accounting; this is not an account-wide provider billing limit.

## Exact approval and execution procedure

Use the existing project Python environment. No separate service or n8n changes
are required. First inspect the local preview and state:

```sh
cd ~/Projects/legalflow-ma
python -m scripts.volkswagen_financial_test preview
python -m scripts.volkswagen_financial_test status
```

Only after approving this specific additional test:

```sh
python -m scripts.volkswagen_financial_test approve --acknowledge 'DE-HRB-P1103-100484-P2413 | financials only | one request | separate 10-credit budget'
python -m scripts.volkswagen_financial_test run --enable-live-test
python -m scripts.volkswagen_financial_test status
python -m scripts.volkswagen_financial_test report
```

Approval is local, expires in one hour, and does not call the provider. Its secret
nonce is stored privately and read internally, never printed or passed in argv.
Only `run --enable-live-test` can make the paid request. Identity approval cannot
authorize financial retrieval. Existing `.env` and credentials are only read,
never modified. Terminal output contains safe diagnostics and estimated usage;
financial payloads remain local. `report` regenerates the Markdown report from the
saved outcome without network access. If a request is pending/uncertain, inspect
state and billing manually; no reset or reapproval is provided after starting.

## Validation, analysis and limitations

Fresh cache entries (24 hours) require the exact company ID, endpoint, successful
HTTP status, retrieval timestamp and explicit live-provider provenance. Legacy
untagged caches and fixture data cannot establish genuine financial evidence.
Trusted reusable cache data consumes zero new credits but still requires approval.

The documented reports/indicators schema is validated before analysis. Error
envelopes, conflicting IDs, invalid numbers, duplicate report IDs and malformed
metadata produce manual review. Reported indicator figures retain dates, scope,
report IDs, source fields, currency and scale; missing figures are never zero.
Estimates, merged tables, previous-value columns and ambiguous statement labels
are excluded. Raw statement trees are not mapped to financial metrics.

The existing analyzer calculates equity/assets, liabilities/assets, current ratio
and net margin only with valid periods and compatible explicit units. It compares
compatible reporting periods and flags declines, losses and negative equity as
review triggers. Missing currency/scale blocks calculations rather than assuming
EUR or unit multiples. Period comparisons across gaps require manual review before
describing them as year-over-year trends. Original report dates and references are
preserved, but documents and audit opinions are not fetched or independently
verified. Corporate identity confirmation does not independently certify financials.

No figures returned, provider unavailability and a failed request remain distinct;
none proves that no statements were published. Overall risk remains Undetermined.
The report includes sources, periods, units, missing-data warnings, formulas,
comparisons, estimated credit usage and financial indicators separate from legal
findings. Personal auditor data and unused response fields are omitted from cache.

## Offline checks

```sh
python -m unittest discover -s tests -q
```

Mocked tests cover explicit approval, identity gating, ledger isolation, cache
provenance, missing data and units, malformed responses, deterministic calculations,
concurrency, restart replay, crashes, expiry, transport restrictions and reporting.

## Cache-only reanalysis

`report` now recomputes analysis from the saved response rather than reprinting an
old analysis. It needs no live approval or unexpired price review. The original
request outcome, budget reservation and provider cache remain unchanged. Derived
analysis is stored privately in `data/volkswagen_financial_test/reanalysis.json`.

The first saved Volkswagen financial response contains actual indicator values,
but no explicit currency/scale metadata. These raw numbers must not be labeled as
EUR, cents, thousands or millions by guessing from their magnitude. Earlier code
also dropped indicator-level currency/scale if supplied; that preservation bug is
fixed prospectively, but discarded metadata cannot be reconstructed from this
cache. The cache does preserve report/root-level unit metadata when present.

Comparison output now states why each metric is withheld. Scope ordering is
separate, non-consecutive periods cannot be labeled year-over-year, and mismatched
indicator/report dates remain excluded and are displayed explicitly. Unit
conflicts also block calculation. Sanitized regression fixtures demonstrate
successful calculations only where explicit compatible units are available.

Reports use provider report IDs and source ordinals instead of document URLs.
Original URLs (including expiring signed URLs) remain only in ignored private
cache/ledger/derived-provenance files, not in Markdown reports. No replacement
document URLs are invented or fetched. Previously exported copies of old reports
are not automatically rewritten.
