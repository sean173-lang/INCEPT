# Existing n8n workflow: FastAPI development integration

Updated on 2026-11-10 through the local n8n REST API, with authorization.
Workflow ID: `gqHCIMt3iK8TBWTh`. Its name, Form Trigger, original input fields and
field mapping were preserved. The workflow remains **inactive**. No activate,
trigger-execution or paid-provider endpoint was called during this integration.

The original workflow was retrieved before modification and saved privately in
`a private temporary directory outside this repository`. The directory
has mode 0700 and private JSON files have mode 0600. It is outside the repository;
no credential-bearing backup was added to version control. Update-request and
updated snapshots are retained beside it. Temporary storage may be cleaned by
the OS; retain a secure long-term copy if rollback retention is needed.

## Resulting nodes

1. **On form submission** — original Form Trigger, unchanged.
2. **Edit Fields** — original field mapping, unchanged.
3. **Prepare Development Input** — validates input; preserves requested name as
   context but sends only synthetic company identities; forces financials off.
4. **Input Valid?** — stops invalid input in the review branch.
5. **FastAPI Health** — GET `http://127.0.0.1:8000/health`.
6. **Require Development Mode** — requires HTTP 200 and `development: true`.
7. **Development Ready?** — stops if health/development checks fail.
8. **FastAPI Company Search** — POST `/v1/company/search` with name/jurisdiction.
9. **Prepare Company Candidates** — validates synthetic candidates; selects one
   unique candidate for details or returns ambiguity/not-found/failure.
10. **Candidate Selected?** — sends a selection to details verification.
11. **Candidate Selection Required?** — sends multiple candidates to a form;
    routes other unresolved outcomes to review.
12. **Select Company Candidate** — a second Form page with candidate dropdown.
13. **Validate Candidate Selection** — accepts only an exact listed choice.
14. **Selection Valid?** — prevents tampered/invalid selections from proceeding.
15. **FastAPI Verify Company** — POST `/v1/company/verify` with selected ID and
    available registration information.
16. **Check Verification Response** — requires development mode, the explicit
    provider-record verification scope, a handle and successful detail checks.
17. **Company Verified?** — branches verified versus unresolved results.
18. **Verified Company** — structured synthetic verified result and handle.
19. **Verification Needs Review** — structured ambiguous/not_found/failed result;
    no further provider requests.
20. **Legacy OpenRegister Search (disabled)** — disconnected archive of the old
    HTTP node, retaining its existing credential reference. Never executed.

Germany submits `LEGALFLOW DEMO GmbH`; UK submits `LEGALFLOW DEMO LTD`. The
jurisdiction reaches the same FastAPI endpoint, whose existing backend routes to
the relevant development provider adapter. Real form company names are not sent
for provider research. The original financial selection field remains visible,
but even a Yes selection does not authorize financial calls: the development
context forces financials off and the graph has no financial endpoint.

All connected HTTP nodes target loopback FastAPI, have explicit timeouts,
disabled retries/redirect following, and route HTTP/network failures through
safe code checks. A name match is only candidate selection; it cannot produce a
verified identity without the detail-based verification endpoint and checks.

The current local FastAPI instance reports development mode and needs no
incoming service token. Existing OpenRegister credentials were not altered or
attached to the FastAPI nodes. If FastAPI authentication is enabled later, create
an appropriate distinct Header Auth credential in n8n after approval; do not
reuse the provider key or paste it into node parameters.

## Validation performed

- Read live FastAPI OpenAPI and health response before building the integration.
- Private backup created before the only workflow PUT; checked that the workflow
  had not changed since backup and was inactive before updating.
- Synthetic Germany and UK search/detail requests each returned HTTP 200 and
  `verified`, with development flags true. Estimated paid usage before and after
  those checks was unchanged. No financial or research request was performed.
- Workflow PUT returned HTTP 200. A fresh GET confirmed the same ID, inactive
  state, unchanged original input nodes and preserved archived credential binding.
- Full offline suite: 123 tests passed, including nine workflow tests that execute
  exported JavaScript with synthetic items. Tests cover invalid input, Germany/UK
  fixture routing, real-candidate rejection, ambiguity, valid/invalid selection,
  failed responses, development guards, and detail-verification requirements.
- No full n8n Form Trigger execution was started. Connectivity checks were made
  from the host to FastAPI; actual n8n node execution and the interactive dropdown
  still need a manual development test. Installed node-type metadata returned
  HTTP 401, so runtime node compatibility has not been independently confirmed.
  The configuration follows the existing HTTP version and documented Form/IF
  schemas. The current listener is a host node process; container deployment
  would require rechecking the loopback URL.

## Repository artifacts and rollback

- `scripts/n8n_workflow.py` deterministically builds the development graph from a
  private source workflow; it performs no network requests.
- `workflows/legalflow_fastapi_development.json` is a sanitized snapshot of the
  resulting graph. Credential references and trigger webhook identifiers were
  removed. It is a review artifact, not an exact credential-preserving backup.
- `workflows/legalflow_workflow.json` remains the original repository export.
- `tests/test_n8n_workflow.py` provides offline graph and code-node tests.

To roll back, use the private original snapshot to construct the allowed workflow
update fields (`name`, `nodes`, `connections`, `settings`) and PUT them to the
same workflow ID. Do not activate it. Review the current workflow/version before
restoring so newer edits are not silently overwritten. The original credential
reference and trigger metadata exist in the private backup, not the sanitized
repository snapshot.

## Remaining limitations

This is deliberately synthetic-only. Ambiguity is exercised by offline fixtures;
normal development provider searches currently return one demo candidate. The
workflow stops at verification and does not orchestrate financials, Tavily, RAG,
or an autonomous loop. No live-paid acceptance test or automatic approval has
been added. Keep FastAPI in development mode; changing to real-company research
requires a separately reviewed configuration and explicit authorization.
