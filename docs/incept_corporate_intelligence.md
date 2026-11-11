# Optional Corporate Client Intelligence

## Implemented boundary

`POST /v1/onboarding/corporate-intelligence` accepts `CorporateRequest` and returns `CorporateResult` from `scripts/corporate_intelligence.py`. Required synthetic mandate acknowledgement, client/matter IDs, structured client identity, source policy and budget are validated. The default is `cache_only`, `max_external_requests: 0`, at most three cached operations. No network callback is executed, no retries occur and no financial operation is allowed.

Individuals return `not_applicable`, without a lookup or corporate report section. Unknown type/jurisdiction, unsupported jurisdiction or missing registration/provider identity produces review with explicit gaps. German companies require register court as well as registration and approved provider ID. UK company identity routes independently of the governing law of the dispute.

The existing `CompanyService.verify` checks provider details, legal name and registration, rather than name alone. `CompanyService.research`, existing adapters, evidence classification and `LocalRAG` are reused. A narrow register-schema compatibility shim preserves the original response. Conflicting schemas require review. Timeout/cache errors return a transparent limited assessment.

## Cache and evidence policy

Only provenance-attested cached records (`origin: live_provider_response`, matching provider, `synthetic: false`, original `retrieved_at`, and provider `payload`) qualify for the cache-only identity path. Existing unattested caches fail closed; this implementation does not upgrade or rewrite them. Missing cache evidence means unavailable through this path, not company nonexistence. Stale records over 30 days require review; no cached record is represented as current verification.

`approved_demo_fixture` is separately available only in server development mode for the explicitly catalogued synthetic IDs in `references/incept_corporate_demo.json`. It is an offline development approval scope, not permission to spend provider credits. These records are UNVERIFIED synthetic evidence, never live registry findings. Original dates, source IDs, freshness, missing evidence and limitations appear in structured output and the report. Third-party leads are unverified; absence of leads does not establish absence of risk. Signed/credential-bearing URLs are excluded.

The seven report subsections cover identity, address, management, discrepancies, background, missing evidence and freshness. Available officer records retain source/date attribution; no current representation authority is implied. No conflicts clearance, financial statement or ratio analysis is performed.

## Service and workflow

Keep the proven service on 8002 unchanged. Run the same app in a separate local development process:

```sh
python -c "import uvicorn; from scripts.http_service import create_app; uvicorn.run(create_app(development=True, service_token=None, allow_paid=False), host='127.0.0.1', port=8003, access_log=False)"
```

The loopback demo is not production authentication. The existing service token mechanism remains available for other deployments.

`workflows/incept_corporate_intake_dev.json` has **37 nodes**, imported inactive as **0zruCCbLGNUZJ8Gt**. No execution of this new workflow is claimed. Prior workflow FeRkXfcrj8dceBZh and five earlier workflows were compared before/after import and remained unchanged. No credentials were changed. Private import evidence is in `reports/incept_corporate_workflow_import.json`.

Import the sanitized JSON as a new workflow using n8n Import from File. Existing compatible Gmail/Sheets/Calendar credentials must be bound locally; exported JSON contains no credential bindings. The already imported local copy is bound. Do not activate it. Its new intake gate requires explicit `client_type`, and companies require `jurisdiction`; ambiguous input is routed to review. Supply `matter.governing_law` independently; omitted law becomes unknown in this copy. No email contract was silently changed to force a successful execution.

The imported workflow uses cache_only. It cannot obtain the synthetic fixture results below unless explicitly configured for that offline-only policy; an empty trusted cache correctly yields a limited report. No new Google or provider execution occurred during this integration task.

## Reproduce four offline cases

```sh
python -m scripts.incept_corporate_demo
python -m unittest discover -s tests -q
```

TestClient uses the real FastAPI/onboarding/SQLite/report code with socket connections blocked. The synthetic fixture catalogue is explicitly selected. Generated artifacts are in `reports/incept_corporate_demo/`; portable sample assessments are in `examples/reports/`.

| Scenario | Result | Registry evidence |
|---|---|---|
| Individual | Review-ready standard bundle; no corporate section | No registry operation |
| German company | Review-ready bundle with cited corporate section | Synthetic OpenRegister detail consistency only; UNVERIFIED |
| UK company | Review-ready bundle with cited corporate section | Synthetic Companies House detail consistency only; UK law NOT VERIFIED |
| Unknown | NEEDS_REVIEW / insufficient identity | No speculative lookup or matter creation |

All scenarios have zero provider/financial requests and zero external actions. Invoice arithmetic remains 5 × 250.00 + explicitly supplied 19% VAT = 1487.50; this is a fictional assumption, not a tax eligibility conclusion. All deadlines are unconfirmed and tasks pending lawyer approval.

Legacy intake defaults and persisted request fingerprints remain compatible. The original successful workflow retains its historical German-demo behavior. The new workflow explicitly removes that implicit governing-law assumption. No verified UK substantive-law corpus has been added.


## Isolated n8n validation (2026-11-11)

Four separate inactive fixture test copies executed successfully in n8n: individual **20**, German company **21**, UK company **22**, ambiguous **23**. The first three produced review-ready bundles; the ambiguous case stopped at NEEDS_REVIEW. Google ingress/read operations and legislation retrieval were explicitly substituted, while local onboarding, adapters, evidence checks and report assembly ran for real. Company fixtures remain UNVERIFIED; these executions do not establish live registry or new Google connectivity. Original corporate workflow 0zruCCbLGNUZJ8Gt and proven FeRkXfcrj8dceBZh remain unchanged.

Sanitized trace summary: [execution evidence](incept_corporate_n8n_validation.json). Full local artifacts: `reports/incept_corporate_n8n_validation/`. Regression suite: **285 passing tests**. Gradio remains planned.

### Reproduce isolated n8n execution

Start `python -m scripts.incept_corporate_test_service` on port 8004. This process blocks outbound socket connections and uses a separate local SQLite store. Import one of `workflows/incept_corporate_test_{individual,germany_company,uk_company,ambiguous}.json` as a new inactive workflow, then click Execute Workflow. These 37-node copies have no credentials and contact only the three local onboarding helper routes. Gmail/Sheets/Calendar are labeled fixtures; legislation retrieval is deliberately unavailable. Do not run these exports while claiming live Google or registry research.

For the installed n8n CLI, set `N8N_CLI` to its local `n8n/bin/n8n` path and use:

```sh
N8N_RUNNERS_BROKER_PORT=5689 N8N_DIAGNOSTICS_ENABLED=false N8N_VERSION_NOTIFICATIONS_ENABLED=false N8N_LICENSE_AUTO_RENEW_ENABLED=false node "$N8N_CLI" execute --id YOUR_IMPORTED_TEST_WORKFLOW_ID --rawOutput
```

The runner broker port must be free. Keep raw CLI output private. These examples use stable synthetic idempotency keys; replay returns the existing preview. Individual replay execution 24 left the separate store at three clients, three matters and three previews.

The revised portable corporate export includes the UK guidance-validator fix. The original imported corporate workflow was deliberately not updated; executing its old UK branch may still hit that validator. The isolated copies contain the fix and were the workflows actually tested.
