# Phase 2: local RAG and bounded research demo

Implemented 2026-11-10. n8n remains the orchestrator. Python exposes independent
retrieval, planning, tool-execution and report operations. Phase 2 rejects live
mode even when paid approval is configured. All company research uses existing
development fixtures. No financial endpoint, paid search, embedding or model
request is used by this demo.

## Start and inspect

```sh
python -m uvicorn scripts.http_service:app --host 127.0.0.1 --port 8000 --workers 1
python -m unittest discover -s tests -v
```

Development is the default. Do not set `LEGALFLOW_SERVICE_MODE=live` for Phase 2.
Existing service authentication still applies if a service token is configured.
No `.env` changes are required. The local service was restarted with development
mode forced on and paid approval disabled to load these endpoints.

## Corpus and retrieval

`references/corporate_due_diligence.json` contains eight small reference cards:
German GmbHG section 8, HGB section 325, ZPO section 322; UK Companies House
research guidance, Companies Act section 441, civil pre-action conduct and CMA
merger guidance; and the EU Merger Regulation. Each preserves an official source
URL, locator, jurisdiction, topics, original document date when known, review
date, content kind and text. See `references/README.md` for curation limits.

These are authored paraphrases linked to primary sources, not downloaded full
statutes or verbatim quotations. Retrieved text is quoted exactly from the local
card, and the report labels that distinction. Unknown original dates remain
null; `reviewed_at` is not an enactment, amendment or company-event date.

`local_rag.py` builds an in-memory SQLite FTS5 index of the small corpus for each
query. Retrieval is bounded, parameterized and filtered by the verified company's
jurisdiction and optional topic before ranking. EU references may be returned
for either jurisdiction as transaction-context guidance; their applicability is
not assumed. FTS scores are ranking signals, not confidence probabilities.
Unknown/no-hit queries return an empty list; no fallback evidence is generated.

Chunk IDs include a content-hash suffix; the full SHA-256 and corpus version are
returned. Before reporting, every reference's text and metadata are compared to
the canonical local card. An invented quote, citation ID or substituted source
URL blocks report generation. General law references never establish that a
company breached a duty, has litigation, or needs a particular clearance.

## Endpoints

All POST requests use JSON. Existing verification endpoints remain unchanged.

| Endpoint | Inputs | Result |
| --- | --- | --- |
| `POST /v1/rag/query` | `verification_id`, `query`, optional `topic`, `top_k` (1–5) | Scoped reference passages, source metadata and corpus version |
| `POST /v1/research/runs` | `verification_id`, optional topics and `max_iterations` (1–2) | Run ID, bounded plan and next allowed action |
| `POST /v1/research/runs/{id}/plan` | No body | Current plan/stop reason; executes no tool |
| `POST /v1/research/runs/{id}/tools` | Exact `tool` and `plan_token` from plan | Executes one approved action; returns next plan |
| `POST /v1/research/runs/{id}/report` | No body | Structured report and Markdown after stopping |

Supported topics are `corporate_identity`, `financial_disclosures`, `litigation`
and `regulatory_risks`. Arbitrary URLs, prompts, tool names and limits above two
are rejected. Phase 1 service keys belong only in the configured authentication
header, never in JSON bodies.

Example flow, with no external requests:

1. Verify `LEGALFLOW DEMO GmbH` with jurisdiction `Germany` and provider ID `DEMO`
   at `/v1/company/verify`. Use `LEGALFLOW DEMO LTD`, `UK`, `00000000` for UK.
2. Create a research run using the returned verification handle.
3. Inspect `state`, `next_tool` and `plan_token`.
4. If state is ready, execute exactly that action through `/tools`.
5. Inspect the returned plan; repeat at most once more.
6. Once complete, fetch `/report`. A premature report request returns HTTP 409.

Plans, reports and retrieval require a valid unexpired verification handle.
Unknown run IDs return a structured 404; invalid/stale actions return 409.
Live-mode Phase 2 calls return 403 before any tool or provider operation.

## Planner and limits

The planner is deterministic and state-aware, with two allowlisted tools:

1. `retrieve_references`: retrieve relevant local cards for the requested topics.
2. `company_research`: call the existing company-service research operation,
   preserving its identity constraints, evidence annotations and usage tracker.

The server proposes actions but never recursively executes the plan. n8n decides
when to call the next action or stop. A plan token binds a specific run, iteration
and tool. An exact replay returns the current plan without repeating work.
Out-of-order or modified actions are rejected. A run lock prevents concurrent
execution of the same step. Iteration consumption is reserved before execution;
a tool failure stops the run, preserves partial references and does not retry.

The maximum is two actions, not an unbounded model loop. With a one-iteration
run, retrieval completes but company research remains an explicit gap. Plan
polling does not consume an iteration or invoke paid tools. Development tracker
binding is explicit even when the pipeline is used outside the HTTP facade.
Existing provider credit/search budgets and failure semantics are retained.

## Report grounding and confidence

Reports contain four requested topic sections, verified fixture-record
consistency facts, separate reference guidance, potential risks/review needs,
missing data, document requests, company-source annotations, limits and one
final **Undetermined** classification.

Every claim has source IDs, a status, a confidence label and a stated confidence
basis. A typed `source_index` resolves all IDs into synthetic registry, curated
reference, coverage-record or unverified-search sources. Missing-data claims cite
the run's coverage record, not a statute as supposed evidence of company conduct.
References retain their URLs, locators and dates. Reference cards and company
search evidence remain distinct.

High confidence applies only to internal consistency of a synthetic registry
fixture. Moderate reference confidence describes exact local-card attribution,
not transaction applicability. Search leads are low-confidence and unverified;
missing evidence has insufficient confidence. Overall confidence remains
insufficient. No percentage or automatic Low-risk classification is invented.

Financial disclosure coverage consists of legal background and document
requests. No financial figures were fetched, calculated or invented. Litigation
and regulatory findings remain unverified without original company records.
The default search fixtures return no company excerpts; the report explains that
this does not establish absence of adverse information.

## n8n research branch

Workflow `gqHCIMt3iK8TBWTh` was backed up privately before modification to
`a private temporary directory outside this repository` (directory
0700, files 0600). Update and post-update snapshots are retained there. This is
temporary storage; make a secure retained copy if long-term rollback is needed.

The existing 20 nodes, ID, credential references and unresolved-company routing
were preserved. The workflow remains inactive. Nine nodes were appended:

1. FastAPI Create Research Run
2. Check Research Plan
3. Research Plan Valid?
4. Research Action Needed?
5. FastAPI Research Tool
6. FastAPI Research Report
7. Check Research Report
8. Research Report Ready?
9. Due Diligence Report

The branch starts at **Verified Company**. The tool node loops back to plan
validation, then continues to the report when the server stops. n8n checks
allowlisted tool names, development flags, iteration limits and its Code-node
run index. Invalid plans/reports go to the existing manual-review node.
Retries are disabled, and all HTTP nodes target the local FastAPI service.
There is no financial request node. The final node exposes the structured report
and its Markdown in execution output; it does not publish or email it.

`workflows/legalflow_phase2_development.json` is a sanitized review snapshot with
credential references and webhook identifiers removed. It is not the private
credential-preserving rollback file. `extend_research_workflow()` preserves
existing nodes rather than rebuilding the manually tested Phase 1 graph.

## Verification and limitations

- The full offline suite passes. Retrieval evaluation has eight manually curated
  golden queries: precision at one is 8/8 on this tiny corpus. This is a smoke
  test of routing/ranking, not a general legal-search quality benchmark.
- Tests cover no-hit retrieval, jurisdiction filtering, source/hash/date metadata,
  tampered citations/URLs, unknown tools, replay rejection/idempotency, iteration
  limits, tool failure, expired identities, live-mode blocking and report output.
- Host-to-service demos for Germany and UK each completed two actions and
  returned four report sections with source links. Estimated paid usage remained
  unchanged. Demo Markdown is in `reports/LEGALFLOW_Phase2_Germany_demo.md` and
  `reports/LEGALFLOW_Phase2_UK_demo.md`.
- A fresh n8n REST read confirmed 29 nodes, the unchanged ID, preserved original
  nodes and credentials, manual-review routing and inactive state. No activation was performed. Subsequent validation of saved manual execution 9
  confirmed the complete 29-node happy path through report generation; see
  [execution validation](workflow_validation.md). Interactive ambiguous selection
  remains validated by offline fixtures rather than a full form execution.
- Run state, handles and budgets remain single-process/in-memory. Restarting
  invalidates handles and runs. Use one worker. No durable workflow resumption,
  cross-process billing protection or multi-tenant isolation is claimed.
- Corpus freshness, completeness, local paraphrase quality and legal applicability
  require ongoing review. There is no full-document ingestion, OCR, embedding
  model, vector database, case-law coverage, paid agent or legal-certification
  feature in this implementation.
