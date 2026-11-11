# Separate n8n legal-intake onboarding workflow

`workflows/legal_intake_onboarding.json` is a sanitized, inactive, **10-node**
manual-trigger workflow. It contains fictional `.invalid` addresses, no credentials,
webhooks, runtime pins or execution records. It is separate from corporate workflow
`gqHCIMt3iK8TBWTh`; the corporate 29-node graph, settings, credential bindings and
inactive state were fingerprinted before and after and remained unchanged.

## Actual installed-version validation

This machine runs n8n **2.47.3** through its local npm installation directly on
macOS, not Docker. The installed node definitions and CLI implementation were
inspected. Used versions: Manual Trigger 1, Code 2, IF 2.2, HTTP Request 4.5.

The old FastAPI process at port 8000 lacked the new onboarding route. It was left
untouched. A separate fixture-only process running the real `create_app` and real
`OnboardingService` was started on `127.0.0.1:8002`. It has server-side paid access
disabled and no service token because it is a loopback-only synthetic demonstration.
No response data was pinned, mocked or substituted in the n8n execution.

Created new workflow ID: **msZU5qMxA3kp6KFf**. It remains inactive.

**Actual n8n execution 11: success, business outcome passed.** It ran autonomously
after the CLI manual trigger and traversed all nine nodes on the success path:

1. Manual Intake Trigger
2. Fictional Intake
3. Validate Intake
4. Input Valid?
5. POST Onboarding Preview
6. Validate Onboarding Bundle
7. Bundle Valid?
8. Success Summary
9. Execution Summary

The tenth node, Failure Summary, is an alternative branch. Execution 10 actually
traversed it: HTTP 200 succeeded but business validation rejected the installed
n8n text output property (`data` rather than the expected `body`). The fix sets
`outputPropertyName: body` explicitly and accepts either documented output form.
A regression test covers this difference. Execution 10 is not counted as a passed
onboarding run. Both executions used the same synthetic idempotency key, and only
one matter/bundle was persisted.

## What execution 11 validated

- HTTP 200 from the actual local onboarding endpoint; linked DEMO client/matter
  IDs and input identity/title/summary consistency.
- Three separate DEMO documents: Vollmacht, hourly-fee agreement, draft advance.
- Five-hour arithmetic using integer cents in n8n against the Python Decimal
  result: EUR 1,250.00 net + EUR 237.50 supplied demo VAT = EUR 1,487.50 gross.
- Three factual intake statements remain unverified; ten source records resolve
  citations, including four retrieved legal-reference cards with URLs/locators/
  review dates. Missing-evidence warnings and insufficient-confidence status exist.
- Five proposed actions remain `pending_lawyer_approval`; no action executed,
  no confirmed due date, and the claimed date remains only a candidate.
- No paid calls, real email, calendar event, issued invoice or approval bypass.

Proof locations:

- `docs/legal_intake_n8n_validation.json`: safe execution metadata/checks and trace hash.
- `data/onboarding_n8n/execution_11.private.json`: full actual n8n REST execution trace,
  private and Git-ignored.
- `reports/legal_intake_n8n_execution_11.json`: exportable synthetic final bundle/summary.
- `data/legal_intake_mvp/onboarding.sqlite3`: persisted local client/matter/bundle.

A successful n8n engine status alone is not sufficient: inspect final
`business_success: true` and `outcome: passed`. Failure summaries intentionally
finish the workflow with `business_success: false` and `manual_review_required`.
No automatic retries are configured. HTTP 409 (key reused with changed intake),
422, authentication errors, timeouts, non-JSON and invalid bundles have explicit
failure classifications. Exact duplicate input returns the same matter.

## Reproduce on this installation

The separate port-8002 service was left running. If restarting it is necessary,
use the following; do not replace the corporate service on port 8000:

```sh
python -c "import uvicorn; from scripts.http_service import create_app; uvicorn.run(create_app(development=True, service_token=None, allow_paid=False), host='127.0.0.1', port=8002, access_log=False)"
```

Open the new workflow in n8n and click **Execute workflow**. No activation or form
submission is required. Alternatively use the installed CLI against the already
imported ID; a separate broker port avoids the running instance's broker:

```sh
N8N_RUNNERS_BROKER_PORT=5689 \
N8N_RUNNERS_MODE=internal \
N8N_DIAGNOSTICS_ENABLED=false \
N8N_VERSION_NOTIFICATIONS_ENABLED=false \
N8N_LICENSE_AUTO_RENEW_ENABLED=false \
/usr/local/bin/node $N8N_CLI \
  execute --id=msZU5qMxA3kp6KFf --rawOutput
```

The installed CLI emitted a non-blocking warning about its unavailable optional
Python runner. This JavaScript-only workflow still completed and was persisted
in the actual running instance's execution database. No Python-runner installation
or global n8n setting change was needed.

The JSON is importable through n8n's Import from File UI. It was created here
through the local REST API using only `name`, `nodes`, `connections`, `settings`.
To import another copy with this installed CLI instead:

```sh
/usr/local/bin/node $N8N_CLI \
  import:workflow --input=workflows/legal_intake_onboarding.json --activeState=false
```

Importing another copy creates another workflow; prefer the already imported ID.
Do not import over or edit the existing corporate workflow. For a future Docker
installation, the loopback URL would need deliberate adaptation to a reachable
host service, with an appropriate bind/auth policy. No such change was needed or
made on the actual macOS process.

## Offline checks and remaining scope

```sh
python -m unittest discover -s tests -p test_intake_workflow.py -q
python -m unittest discover -s tests -q
```

Tests execute the exported node JavaScript using Node.js against real Python-built
bundles offline. They check graph/export safety, arithmetic, citation attribution,
unsafe response rejection and HTTP/transport failure paths. Full regression also
covers onboarding's SQLite idempotency and preservation of corporate exports.
The generator is `python -m scripts.intake_workflow`.

This proves one actual n8n-to-FastAPI autonomous preview execution, not three real
external integrations or an approved legal mandate. Markdown drafts remain DEMO.
No Gmail, Calendar, Sheets, paid model or outbound action integration is added.
The next development action toward Project 3 is to authorize a narrowly scoped
Google Sheets OAuth credential and verify a read-only spreadsheet metadata call
in a separate integration test. Then design approval-gated synthetic-record write,
Gmail draft and Calendar action stages; do not enable sending/scheduling from this
preview. External OAuth access requires separate authorization; none was used here.
