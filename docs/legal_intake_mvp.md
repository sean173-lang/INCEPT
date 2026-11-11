# Fixture-only legal intake vertical slice

Branch: `feature/legal-intake-mvp`. n8n remains the intended orchestrator; this
slice supplies a single supporting endpoint. No workflow was changed. There is
no Gmail, Calendar, Sheets, Gradio, paid research, invoice issuance or action
executor. **This does not satisfy Project 3's three-real-external-API requirement.**

## Run and submit

Use the existing Python service environment. To avoid replacing any running
service, start a separate local preview process on port 8002:

```sh
python -m uvicorn scripts.http_service:app --host 127.0.0.1 --port 8002 --workers 1
```

The endpoint requires development mode (the existing default). If the environment
selects live mode, it refuses onboarding requests. Existing service-key auth also
applies when configured. No `.env` modification is necessary or authorized here.
The default local demo store is `data/legal_intake_mvp/onboarding.sqlite3`.

Submit the supplied fictional intake:

```sh
curl --fail-with-body --silent --show-error \
  -X POST http://127.0.0.1:8002/v1/onboarding/preview \
  -H 'Content-Type: application/json' \
  --data-binary @examples/onboarding_preview.json
```

The body must explicitly assert `synthetic_data: true`. Only `.invalid` email
addresses and German jurisdiction are accepted. This is an input policy, not a
classifier capable of proving a name/address fictional. Do not submit real data.
Extra fields cannot approve actions, set hours or authorize spending.

Repeat the same body/key to receive the identical persisted bundle. Reusing the
key with changed input returns HTTP 409. Use a new key intentionally for a new
matter; this is request idempotency, not a full cross-request client deduplication
system. SQLite transactions serialize concurrent submissions. Client and matter
records and the complete bundle commit together; failed generation rolls back.
Storage errors return safe structured responses without paths or intake values.
The SQLite file is private (0600) and ignored by Git. This local demo is not a
production multi-tenant case-management store.

## Bundle

- Typed client/matter records with generated DEMO identifiers and draft status.
- Personalized, separate **DEMO Vollmacht** and **DEMO hourly-fee agreement** in
  Markdown. No signatures or legal acceptance are asserted. The power draft does
  not contain the remuneration terms. These templates need lawyer review and
  adaptation; DOCX/PDF generation is deliberately outside this first slice.
- **DRAFT Vorschussrechnung**, five hours of anticipated work, never completed
  services. Decimal with half-up cent rounding calculates net, supplied VAT and
  gross. The sample is 5 × EUR 250 = EUR 1,250 net; supplied demo 19% VAT = EUR
  237.50; gross EUR 1,487.50. No statutory tax IDs, bank details, payment deadline
  or official invoice number are invented. Five hours is a demo assumption, not
  a confirmed appropriate advance. Draft date is supplied by the intake.
- VAT modes: `taxable` requires an explicit percentage and supplied treatment
  basis; `exempt` requires a supplied basis and gives zero VAT; `unknown` leaves
  VAT/gross unavailable. All supplied tax treatment remains unverified. No
  default VAT rate or legal tax exemption is inferred.
- Structured **Mandate Assessment Report**, with synthetic-intake evidence IDs,
  legal-reference IDs/URLs/locators/dates, corpus version, missing evidence and
  explicit uncertainty. A claim in intake is repeated only as an unverified
  statement, never promoted to a judgment, established liability or legal advice.
- Proposed conflict/document/fee-review tasks, a potential-deadline review and a
  draft email. **Every action and document is `pending_lawyer_approval`.** All
  action `executed` flags are false. `due_date` remains null; a client-supplied
  claimed date is merely `candidate_date`, never an approved calendar deadline.
  No approval/send/execute endpoint exists.

## References and implementation

`references/mandate_intake.json` holds four short curated paraphrases with primary
links: BGB §167 (authority), RVG §3a (fee agreement), RVG §9 (advance), and BRAO
§43a (confidentiality/conflicts). Public texts were checked November 10, 2026;
review date is distinguished from unknown enactment/amendment dates. These cards
are guidance, not original client documents or a complete legal research corpus.

The existing `LocalRAG` retrieves these cards offline through bounded FTS search;
no corporate corpus or retrieval guards are weakened. `Schema`, `ServiceError`,
FastAPI error responses and Markdown escaping are reused. Bundle building is
rule-based; there is no OpenAI call or autonomous live research in this slice.

## Offline acceptance and sample files

```sh
python -m scripts.onboarding_demo
python -m unittest discover -s tests -p 'test_onboarding.py' -v
python -m unittest discover -s tests -q
```

The demo uses in-process FastAPI HTTP calls, a temporary SQLite database and
blocked external socket connections. It verifies duplicate submissions, exact
sample arithmetic, complete drafts, citations and action safety, then exports
only synthetic sample artifacts:

- `reports/legal_intake_mvp/bundle.json`
- `reports/legal_intake_mvp/vollmacht.md`
- `reports/legal_intake_mvp/fee_agreement.md`
- `reports/legal_intake_mvp/advance_invoice.md`
- `reports/legal_intake_mvp/mandate_assessment.md`
- `reports/legal_intake_mvp/proposed_actions.json`

These are local ignored reports, not live records or external actions. Existing
corporate and financial reports are preserved. Generated samples are reproducible
in structure/calculation; new temporary demo runs produce new UUIDs. A repeated
idempotency key against the persistent HTTP service returns the original UUIDs.

Remaining gaps: lawyer-approved production wording, substantive legal research,
original-document ingestion, actual deadline computation/validation, professional
conflict systems, production authorization/audit/retention, real API integrations,
and workflow orchestration of this endpoint. No regulatory or billing compliance
certification is claimed by these demo drafts.


## Optional corporate extension

See [corporate integration](incept_corporate_intelligence.md). Explicit individual/company/unknown intake and independent governing law are supported. The new 37-node copy uses port 8003; the proven workflow remains unchanged. Company intelligence is cache-only and nonblocking, with original provenance and stale-data warnings. Legacy input fingerprints remain compatible. Financial operations are excluded; UK substantive analysis is unverified.
