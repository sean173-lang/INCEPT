# Isolated Volkswagen register test

This opt-in service is independent of the development service on port 8000 and
the existing 29-node n8n workflow. It does not edit, activate or call that workflow.
No provider requests were executed while implementing this profile.

The only target is Volkswagen AG (also accepting its full legal name Volkswagen
Aktiengesellschaft), Germany, Amtsgericht Braunschweig, HRB 100484. Search
candidates must match the legal name **and** full register identity. A unique
candidate's provider ID is then used for detail verification. Conflicting details,
multiple matches and missing records cannot produce verified identity.

Only these provider operations exist in this service:

| Operation | Request | Estimated credits |
| --- | --- | --- |
| Company search | GET /v1/autocomplete/company?query=Volkswagen%20AG | 1 |
| Standard details | GET /v1/company/{selected_company_id}?realtime=false | 10 |

The [official pricing](https://docs.openregister.de/pricing),
[autocomplete documentation](https://docs.openregister.de/endpoint/autocomplete-company)
and [details documentation](https://docs.openregister.de/endpoint/company) were
reviewed on November 10, 2026. Real-time details cost 20 credits and are excluded.
The checked-in policy expires November 17, 2026 and fails closed if its pricing,
dates or scope are missing or inconsistent. This is a dated documentation check,
not confirmation of account entitlement or billing. Monetary cost: **Cost unknown**.
Re-review public documentation before renewing the policy; an existing ledger
pins its policy hash, so edits require manual review rather than resetting budget.

A cache miss requires at most two requests, estimated at **11 credits**. A trusted
search cache reduces this to 10; trusted details need no provider requests.
The hard persistent ceiling is 15 credits, with at most one search and one details
attempt. Failed or uncertain requests retain their full estimated reservation.
No automatic retry, redirect following, real-time retrieval or SDK fallback occurs.
Financial endpoints, Tavily, OpenAI and autonomous research are not exposed.

## First controlled test

Use the Python environment with the project's existing dependencies installed
(`requirements-service.txt` includes the HTTP service dependencies). From the repo:

```sh
cd ~/Projects/legalflow-ma
python -m scripts.volkswagen_live_test preview
```

Preview scans caches locally without approval or provider I/O. Legacy cache entries
without explicit live-provider provenance, synthetic entries and entries older
than 24 hours cannot establish real evidence. This may mean that existing generic
caches are inspected but rejected. The preview shows the corresponding estimate.

In terminal 1, start the separate service. This command alone makes no provider call:

```sh
python -m scripts.volkswagen_live_test serve --enable-live-test
```

It binds only to **127.0.0.1:8001**, ignores proxy forwarding headers, uses one
worker and disables access logging. Without the flag, verification is blocked.
In terminal 2, explicitly approve the fixed scope and ceiling, then trigger once:

```sh
python -m scripts.volkswagen_live_test approve --acknowledge 'Volkswagen AG | Germany | Amtsgericht Braunschweig | HRB 100484 | 15 credits'
python -m scripts.volkswagen_live_test verify
python -m scripts.volkswagen_live_test status
```

**Only `verify` can initiate provider requests. Do not run it before live approval.**
The approval expires after one hour. Its random nonce stays in a private local
file and travels in a header to the loopback service; it is not printed or passed
in command arguments. Existing provider credentials are read locally, unchanged.
There is no API for selecting another company, endpoint, budget or tool.

Read-only local endpoints are `GET /health`, `/v1/volkswagen/preview`,
`/v1/volkswagen/status` and `/v1/volkswagen/result`. The sole execution endpoint is
`POST /v1/volkswagen/verify`, with an empty JSON object and the local approval
header. The CLI supplies that header without displaying it.

## Persistence and evidence

Private state lives under ignored `data/volkswagen_live_test/`: a SQLite ledger
and `approval.local`. Keep this directory across restarts. Reservations commit
before network I/O; concurrent processes, crashes and uncertain failures block
duplicate paid attempts. Completed results are reused. There is no reset command
or automatic retry/reapproval after the test starts. If interrupted, inspect the
ledger/status and provider billing manually; restarting does not retry.

Results retain reduced corporate identity, source operation, retrieval/request
timestamps, cache status, diagnostic code and estimated reserved credits. They do
not persist raw provider bodies, personal management data or authorization values.
Details support documented `register` and legacy `company_register` fields and
reject conflicts. Cached evidence must carry provider provenance and its original
retrieval timestamp. A provider record is not independently certified evidence.

Verification covers corporate identity only. It establishes no financial,
litigation, sanctions or regulatory clearance. Risk remains Undetermined. Fixture
research and legal-reference guidance are explicitly not real company findings.

The ledger is a local safeguard, not account-wide billing enforcement. Deliberate
state deletion, running another checkout or changing the code can defeat local
accounting; do not delete or relocate it to repeat a test. Account credit charges
and plan permissions require separate confirmation. No blanket account spending
limit or live entitlement check is claimed.

## Offline verification

```sh
python -m unittest discover -s tests -v
```

Tests use mocked responses and blocked external sockets. Coverage includes dual
opt-in, fixed identity, forbidden operations, cache provenance/freshness, expired
pricing and approval, budget reservations, concurrent execution, process death,
restart replay, safe HTTP diagnostics and response schema conflicts.

## Separately approved direct-detail continuation

For the completed autocomplete `not_found` outcome only, a separate continuation
may check the supplied, initially unverified ID `DE-HRB-P1103-100484-P2413`.
This does not rerun autocomplete or reset its original result or reservation.
It uses the same private database, policy fingerprint and cumulative 15-credit
ceiling. A new `continuation` table records separate approval and outcome;
`operations.direct_company_details` records any paid attempt. Schema creation is
additive and happens only when the service or CLI is next invoked.

Stop only the isolated port-8001 process if it is running, then restart it with
the updated code. Leave n8n and the development service on port 8000 alone.
From the repository, terminal 1:

```sh
python -m scripts.volkswagen_live_test serve --enable-live-test
```

Terminal 2, after explicit live execution approval:

```sh
python -m scripts.volkswagen_live_test status
python -m scripts.volkswagen_live_test approve-direct --acknowledge 'DE-HRB-P1103-100484-P2413 | Volkswagen AG | Germany | Amtsgericht Braunschweig | HRB 100484 | additional 10 credits | cumulative 15 credits'
python -m scripts.volkswagen_live_test verify-direct
python -m scripts.volkswagen_live_test direct-result
python -m scripts.volkswagen_live_test status
```

Only `verify-direct` can execute the continuation. The other commands perform
local operations. Its fresh approval expires after one hour and is stored in
private `direct-approval.local`; the original approval cannot authorize it.
No approval or live execution was performed during implementation.

The sole possible provider request is:

```text
GET https://api.openregister.de/v1/company/DE-HRB-P1103-100484-P2413?realtime=false
```

Trustworthy fresh details for that exact ID are checked first. A cache miss
reserves 10 estimated credits before I/O, bringing the existing 1-credit total
to 11. Failed/uncertain attempts keep the reservation, with no retries, alternate
IDs or further searches. If interrupted, do not delete state or attempt to
reapprove: inspect the saved pending outcome manually. Completed continuation
results are reused; repeated calls never initiate another request.

Returned ID, allowed legal name, explicit German country, court, register type
and number must all establish the target identity. Missing or conflicting fields
produce `manual_review`. The supplied ID alone establishes nothing. The existing
search result remains at `GET /v1/volkswagen/result`; continuation outcome is at
`GET /v1/volkswagen/direct-detail/result`. Its execution endpoint is
`POST /v1/volkswagen/direct-detail/verify`, with empty JSON and the separate
approval header, supplied privately by the CLI. The original pricing-expiry and
all provider/financial/research restrictions remain in force.
