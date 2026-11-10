# Phase 1: local HTTP research services for n8n

This service exposes individual company operations. n8n remains the primary
orchestrator: it owns intake, jurisdiction selection, candidate review, endpoint
sequencing, approval decisions and delivery. No workflow was imported, executed,
modified or activated during this implementation. This phase adds no financial
HTTP endpoint, RAG, planner, autonomous loop or report-generation endpoint.
Existing CLI operations and financial cache files remain intact.

## Install and start safely

From the existing repository, in your chosen virtual environment:

```sh
python -m pip install -r requirements-service.txt
python -m uvicorn scripts.http_service:app --host 127.0.0.1 --port 8000 --workers 1
```

The default mode is **development**. It uses labeled synthetic fixtures before
initializing provider SDKs, needs no paid-provider credentials and does not read
or populate live provider caches. It does not contact OpenAI or n8n. Dependency
installation is not a provider API request. No dependency installation or live
server launch was needed to run the in-process HTTP tests in this environment.

Open `http://127.0.0.1:8000/docs` for typed schemas and
`http://127.0.0.1:8000/openapi.json` for the machine-readable specification.
`GET /health` returns mode/status without contacting any provider.

A synthetic Germany example:

```sh
curl -sS http://127.0.0.1:8000/v1/company/verify \
  -H 'Content-Type: application/json' \
  -d '{"company_name":"LEGALFLOW DEMO GmbH","jurisdiction":"Germany","provider_company_id":"DEMO"}'
```

Use `LEGALFLOW DEMO LTD`, jurisdiction `UK`, and provider ID `00000000` for the UK
fixture. A synthetic `verified` result always includes `development: true`; it
is not evidence about a real company. No API credentials belong in request JSON.

## Endpoints and contracts

| Method/path | Request | Result |
| --- | --- | --- |
| `GET /health` | None | Service status and development flag |
| `POST /v1/company/search` | `company_name`, `jurisdiction` | `candidates_found` or `not_found`, with candidate records |
| `POST /v1/company/verify` | Name/jurisdiction; optional selected `provider_company_id`, `registration_number`, `register_court`, `register_type` | `verified`, `ambiguous`, `not_found` or `verification_failed` |
| `POST /v1/research/search` | Server-issued `verification_id` only | Evidence-annotated research for the verified identity |
| `GET /v1/usage` | None | Shared process-session estimated consumption |

Jurisdiction is exactly `Germany` or `UK`. Extra request fields are forbidden:
callers cannot send keys, arbitrary provider URLs, budget overrides or approval
booleans. Names and registration fields have length/type/control-character
checks. Provider IDs cannot contain URL/path syntax; UK company IDs require
eight letters/digits, preserving leading zeroes. German court/type fields are
rejected on UK requests. Registration type, if supplied, is `HRB` or `HRA`.

Search candidates never establish verified identity. A single normalized name
match can select a candidate for subsequent details retrieval; duplicate legal
names with distinct provider IDs return `ambiguous`. Fuzzy-only matches also
require explicit selection. No candidate returns `not_found`. Ambiguity stops
before company-detail retrieval. n8n should collect a candidate choice, then
call verify again with its provider ID and known registration constraints.

Verification compares provider details with the requested name and selected ID.
Registration number must be present; Germany additionally requires register
court. Supplied constraints and available search-candidate registration details
must agree with the detail record. Conflicting jurisdiction metadata is rejected.
The legal registration number is distinct from an OpenRegister provider ID;
IDs are never guessed from registration numbers. Missing identifiers or
registration information cannot be compensated for by matching names.

`verified` means **consistent identity in the selected provider record**, not
independent identity certification, beneficial-ownership verification, signatory
authority verification or legal clearance. The response identifies this scope as
`provider_record_identity`, includes boolean checks and source retrieval time
when available, and returns an opaque `verification_id` valid for 15 minutes.

Research accepts that handle rather than a client-supplied identity. It uses the
stored legal name, jurisdiction, registration number and court with the existing
Tavily integration, then applies the deterministic evidence validator. Unrelated
or unusable results are returned with explicit `usable: false` annotations, not
promoted as evidence. Search snippets remain unverified leads. The response
preserves missing-evidence identifiers and `risk_assessment: Undetermined`.
A missing or expired handle stops before research. There is one existing narrow
legal query per operation, not a new multi-topic or autonomous search loop.

## Authentication, approval and budgets

Live mode fails to start unless a service token is configured. Keep it in an
inherited process environment or secret manager; do not paste it into commands,
workflow JSON or report files. No edits to `.env` are required.

Recognized process settings:

| Setting | Default | Effect |
| --- | --- | --- |
| `LEGALFLOW_SERVICE_MODE` | `development` | `development` or `live` |
| `LEGALFLOW_SERVICE_TOKEN` | Unset | Incoming service authentication; required in live mode |
| `LEGALFLOW_SERVICE_ALLOW_PAID` | `0` | Only exact `1` enables paid cache misses |
| `LEGALFLOW_SERVICE_MAX_OR_CREDITS` | `50` | Shared process-session estimated OpenRegister credit cap |
| `LEGALFLOW_SERVICE_MAX_TAVILY_SEARCHES` | `5` | Shared process-session Tavily search cap |
| `LEGALFLOW_SERVICE_MAX_SPEND` | Unset | Finite monetary cap; unknown costs block paid calls |

For live operation, start the same Uvicorn command only after the operator has
explicitly approved the provider scope and configured these settings. All
protected endpoints require the service token in the
`X-LEGALFLOW-Service-Key` header. Development can also require a token if one is
configured. The service token must be separate from paid-provider and n8n keys.
It is not returned in errors, responses or usage summaries.

Authentication does not authorize spending by itself. With live mode and paid
approval off, warm caches remain usable, while paid cache misses return a
structured approval error before SDK initialization. Companies House public
requests are free, but still require live-service authentication and are tracked.
Use development mode to guarantee no external requests of any kind.

No account-specific money rates are assumed. Unknown monetary costs display
`Cost unknown`. A finite cap blocks unknown-cost paid operations; ordinary
request bodies cannot bypass this. Programmatic `create_app(prices=...,
currency=...)` supports existing tracker upper-bound rates if the operator can
establish their reliability. Without configured rates, a finite cap intentionally
blocks paid operations. Never substitute an unverified price just to unblock it.

The tracker is shared by all requests to an app instance. It reserves usage
before provider execution, preserves failed/uncertain reservations, and blocks
repeated failed operations. Successful repeated searches/details/research use
existing caches or in-session results. SDK automatic retries remain disabled
where already supported. `ContextVar` binding prevents concurrently executing
requests/apps from selecting another request's tracker.

## Errors and n8n branching

Errors use the same safe envelope:

```json
{
  "status": "verification_failed",
  "error": {
    "code": "approval_required",
    "message": "Paid cache misses require server-side approval; request bodies cannot authorize spending.",
    "retryable": false,
    "fields": []
  }
}
```

| HTTP status | Meaning |
| --- | --- |
| 200 | Business result; inspect status, including ambiguous/not_found/verification_failed |
| 401 | Missing/invalid incoming service authentication |
| 403 | Paid approval missing or operation policy blocked |
| 409 | Verification required/expired or duplicate failed request blocked |
| 422 | Typed input validation failed; submitted values are not echoed |
| 429 | Local budget blocked the request, including unknown price under a finite cap |
| 502 | Provider authentication, permissions, rate limit, connection or format error |
| 504 | Provider timeout; processing/billing may be uncertain |

A company-detail 404 returns business `not_found`; it is not a statement about
financial publications or legal standing. Other provider failures return
`verification_failed` with a safe error code. Raw SDK exceptions, authorization
headers, response bodies and sensitive URLs are not returned. Provider failures
must not be converted to no-company/no-litigation conclusions.

## Calling from n8n (configuration instructions only)

1. Retain the existing form, then use a Switch node for Germany/UK intake if desired.
   Both branches can call this service with the appropriate `jurisdiction`.
2. Configure a new HTTP Request node: POST to `/v1/company/search`, JSON body
   `company_name` and `jurisdiction` from the mapped form values.
3. Configure Generic Header Auth with `X-LEGALFLOW-Service-Key` and the service
   token stored in n8n's credential manager. Keep paid-provider secrets in Python.
4. Send the selected candidate ID and known registration constraints to
   `/v1/company/verify`. Switch on the response `status`: continue only on
   `verified`; request selection on `ambiguous`; stop/review `not_found` or
   `verification_failed`.
5. Send the resulting `verification_id` to `/v1/research/search`. n8n owns when
   this occurs and how the returned evidence is merged or delivered.
6. Configure the HTTP node to expose non-2xx status/body for explicit error
   branching. Disable automatic retries of paid operations and retain returned
   safe diagnostics. Never retry a timeout simply to obtain a successful node.
7. Query `/v1/usage` to show estimated usage; this does not trigger provider calls.

If n8n runs on the host, use `http://127.0.0.1:8000`. If n8n runs in Docker,
localhost inside the container is not the host service. Use verified host/container
networking, for example a restricted shared Docker network and service DNS;
`host.docker.internal` may be appropriate on supported installations but still
requires a service bind/interface reachable from Docker. Do not expose this
local prototype publicly. The existing live workflow remains unchanged.

## Tests and current limits

Run `python -m unittest discover -s tests -v`. HTTP tests use FastAPI TestClient
in-process, fake provider responses, temporary storage and the existing socket
block. No provider credentials or live n8n instance are needed.

Operate with **one worker**. This phase deliberately does not implement the
proposal's durable run database or cross-process idempotency. Budgets and
verification handles are in memory: process restarts reset counters and
invalidate handles, and multiple workers would have separate limits. Do not
use reload/restart as a way to bypass spending limits. Durable run reservations,
restart recovery, multi-tenant scope and per-tool approval records remain
prerequisites for production/autonomous workflows.

Caches retain existing freshness policies. Verification establishes consistency
with provider records, which may be stale or incomplete. Handle lifetime is not
independent re-verification. Production deployment, rate limiting, document
retrieval, RAG, financial HTTP operations and autonomous loops are outside Phase 1.

FastAPI references:
[testing](https://fastapi.tiangolo.com/tutorial/testing/) and
[structured error handlers](https://fastapi.tiangolo.com/tutorial/handling-errors/).
