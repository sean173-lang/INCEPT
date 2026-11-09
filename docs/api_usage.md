# API usage monitoring and cost protection

LEGALFLOW routes its provider operations through `scripts/api_usage.py`.
The CLI prints a usage summary even if a request fails or a budget blocks it.
A credential-free event ledger is written to `data/api_usage.jsonl` (gitignored).
Events contain provider, operation, UTC timestamp, session/run IDs, estimated
credits and cost, cache-hit status, outcome, execution mode and a
`billing_confirmed: false` marker. Query text, company IDs, request URLs,
headers, bodies and credentials are not written to the usage ledger.

## Run modes

```sh
# Safe synthetic workflow: no provider clients or network requests:
python -m scripts.legalflow_agent --dev --financials

# Explicit authorization of potentially paid calls, within hard limits:
python -m scripts.legalflow_agent --approve-api \
  --max-openregister-credits 20 --max-tavily-searches 1

# Financials remain separately opt-in (10 estimated OpenRegister credits):
python -m scripts.legalflow_agent --approve-api --financials \
  --max-openregister-credits 20 --max-tavily-searches 1

# A finite money cap blocks all unknown-cost calls:
python -m scripts.legalflow_agent --approve-api \
  --max-session-spend 1 --usage-config usage-config.json

# Standalone company search supports approval and development flags too:
python -m scripts.company_search --dev 'Demo company'
python -m scripts.company_search --approve-api 'Company name'
```

A development report is prominently marked synthetic. Development bypasses real
caches and returns fixtures before initializing SDKs or checking credentials.
Unmocked operations fail closed. Development calls record zero consumption and
cannot populate live caches. Development fixtures do not establish any facts
about the company entered by the user.

Without approval, paid cache misses raise `ApprovalRequired`. Cache hits are
permitted without approval. `--financials`/`allow_paid=True` explicitly approves
that financial operation, but never overrides budget limits. Free Companies
House operations do not require paid-call approval. Earlier usage examples in
the README predate these additional approval controls.

## Budgets and prices

Defaults are 50 estimated OpenRegister credits and 5 Tavily searches per run.
There is no default monetary cap, because the account's applicable rates and
allowances are not known. Non-free monetary costs display **Cost unknown** until
reliable upper bounds are configured; unknowns are never reported as zero total
spending. A finite spending cap blocks unknown costs, even with approval.

The CLI config file supports:

```json
{
  "currency": "EUR",
  "cache_ttl_seconds": 86400,
  "prices": []
}
```

Each optional price entry requires `provider`, `operation`, `upper_bound`, and
`source`. `upper_bound` must be a non-negative finite decimal amount **per
operation in the configured session currency**. `source` should identify a
verified account tariff or a documented, conservative calculation. No actual
account price is shipped in configuration. The operator must establish a
reliable bound rather than inventing a price. There is no automatic exchange
rate conversion. For dynamic OpenAI requests, the bound must cover both input
and maximum output usage; otherwise leave that price unknown.

Recognized provider/operation pairs:

| Provider | Operation | Estimated credits per call |
| --- | --- | --- |
| OpenRegister | `company_search` | 1 |
| OpenRegister | `company_details` | 10 |
| OpenRegister | `financials` | 10 |
| Tavily | `search_basic` | 1 |
| OpenAI | `legal_analysis` | Not applicable/unknown |
| Companies House | `public_data`, `document_metadata`, `document_download` | 0; public data is free |

Credit estimates were checked against official documentation on 2026-11-09:
[OpenRegister](https://docs.openregister.de/pricing),
[Tavily](https://docs.tavily.com/documentation/api-credits), and
[Companies House](https://www.gov.uk/guidance/searching-the-companies-house-register).
These estimates are not confirmed billing or proof of account entitlement.
Published overage rates are not assumed to apply to this account.

Consumption is reserved **before** execution. Failures retain the estimate,
because timeout/error responses do not reliably establish whether billing
occurred. A `reserved` ledger event owns the consumption estimate; completion
events (`success`/`failure`) do not add it again. Blocked and cache-hit events
consume no credits. A failed operation returned as a structured result counts
as a failure too. Never sum a reservation and completion as two requests.

A tracker instance defines a session; CLI invocation creates one session/run.
`tracker.new_run()` resets credit/search limits while retaining session spending
and the ledger. Session budgets are not restored from previous processes. This
is local protection, not an account-wide cap or a substitute for provider limits.

## Caches and duplicate protection

Searches, company details and Tavily research have a shared JSON cache under
`data/api_cache/`, default TTL 24 hours. TTL is configurable. Keys hash the
provider, operation and complete operation identity/parameters. Original company
retrieval timestamps survive detail-cache hits. Files are replaced atomically;
malformed, expired or future-dated entries are treated as misses. Successful
empty search results are cacheable; exceptions and malformed research responses
are not. Cached values are copied before use.

Existing `data/financials/` files and `financial_cache.py` are preserved. Financial
cache reads precede budget reservations and do not require another paid approval.
Its existing no-expiration policy is unchanged; old financial data still requires
freshness review. Corrupt financial cache entries are treated as misses. A paid
miss still requires approval and budget capacity.

Within a process, a shared lock prevents concurrent duplicate paid execution.
Successful repeated operations reuse results. Failed/uncertain repeats are
blocked for the current run, rather than automatically retried. Expiration does
not implicitly authorize another call to the same operation within a run: start
an explicit new run to refresh it. SDK retries are disabled for OpenRegister and
OpenAI. No financial REST fallback is attempted after an SDK request failure.

Standalone library callers can use:

```python
from scripts.api_usage import UsageTracker, use_tracker
from scripts.company_search import search_companies

tracker = UsageTracker(development=True, max_openregister_credits=0)
with use_tracker(tracker):
    companies = search_companies("Demo")  # synthetic fixture, no requests
print(tracker.summary())
```

Remaining limitations: limits and duplicate locks do not coordinate separate
processes, accounts or external tools. Monetary upper bounds are operator-supplied
and cannot establish actual billing. The preserved financial cache has no TTL.
Document download is monitored as one logical operation, which can include an
anonymous storage redirect. There is no account-balance query, automatic retry,
provider invoice reconciliation, or automatic permission to exceed a limit.
