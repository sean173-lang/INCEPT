# INCEPT integrated intake development workflow

Current inactive workflow: **FeRkXfcrj8dceBZh**, **30 nodes** (primary-source revision).
Export: `workflows/incept_autonomous_intake_dev.json`.
Builder: `scripts/incept_autonomous_workflow.py`.

## Latest live acceptance

**Execution 19 succeeded**, business state `PREVIEW_READY_FOR_LAWYER_REVIEW`.
Actual approved Gmail processing, Sheets read, Calendar list, real local preview,
official-source verification and enriched assessment completed in one n8n trace.
Artifacts and sanitized evidence: `reports/incept_execution_19/` and
`reports/incept_autonomous_intake_execution_19.json`. All actions remain pending.

Execution 17 exposed email line wraps inside JSON strings. The parser now
normalizes only those line breaks to spaces and records a lawyer-review warning;
it never fills fields, removes trailing text or substitutes sample data. Execution
18 exposed source charset decoding and final-node context bugs. The source GET
now preserves bytes; the helper follows the declared charset strictly and hashes
the original bytes. The report reads the named validated bundle after research.
Both bugs have regression checks. No approval contract was weakened.

## Historical execution 15: clean stop, not a completed intake

**Actual n8n execution 15** ran the original 23-node revision and finished with engine status `success` and business
state **NEEDS_DEMO_EMAIL**. The dedicated Gmail account's narrowly targeted search
returned HTTP 200 and zero matching message IDs. No message headers/body were
retrieved. No fixture was substituted. Sheets, Calendar and the onboarding POST
were not executed in this run, and no new onboarding documents were generated.

This state does not assert that the mailbox contains no fictional inquiries;
only that none matched this workflow's explicit approval contract. It is not a
successful integrated live-email onboarding run. The prior independent live
Sheets #12, Gmail #13 and Calendar #14 tests remain valid but are not represented
as downstream steps executed by #15.

Sanitized actual-state proof: `reports/incept_autonomous_intake_dev.json`.
Human-readable status: `reports/incept_autonomous_intake_dev.md`.
Five prior successful workflow definitions were fingerprinted before/after and
remain unchanged, including corporate, onboarding and all three API test flows.
No existing credential or workflow was edited. The new workflow remains inactive.

## Approval contract and example inquiry

The sender and recipient must both be **ironhackproject3@gmail.com**, i.e. the
explicitly dedicated demo account sending an approved fictional inquiry to itself.
Required exact subject:

```text
[INCEPT DEMO APPROVED] Fictional intake v1
```

The versioned plain-text body is supplied in
`examples/incept_approved_demo_inquiry.txt`. It begins with:

```text
INCEPT_SYNTHETIC_INTAKE_V1
```

followed by the fictional intake JSON. The example is **not read by the workflow**
and is not a runtime fallback. No email was created or sent by this implementation.
A lawyer/user must approve and supply this synthetic inquiry before the next live
run; no sender or outgoing action is authorized by this document alone.

The query restricts inbox, exact-account from/to, both subject phrases and excludes
spam/trash. Gmail returns at most two matching IDs without snippets or bodies.
Zero matches stop cleanly; multiple candidates or pagination require review. For
a unique candidate, the workflow requests only metadata headers and validates:

- Exact approval subject and one sender/recipient matching the dedicated account.
- Matching message ID, inbox labels, non-draft/non-spam/non-trash state.
- Internal-date metadata and a maximum message-size estimate of 64 KB.

Only the approved metadata branch can fetch that specific message body. No thread
lookup, attachment download, broad personal-email query, mailbox scraping or
outgoing operation exists. Messages/headers alone are not case fact verification.

## Structured extraction and downstream path

This bounded iteration parses versioned JSON from exactly one unambiguous
`text/plain` body, rather than using an LLM to infer missing names, dates, fees or
VAT. Missing required fields yield **NEEDS_INTAKE_INFORMATION**. Natural-language
inquiries, malformed JSON, absent synthetic acknowledgement or multiple plain-text
parts require review. The existing typed FastAPI request remains authoritative.
Client/firm emails must use `.invalid`; all case assertions remain unverified.

The actual approved Gmail message ID determines a stable local idempotency key:
`incept-gmail-<message-id>`. A repeated message reuses the same persisted preview;
changed content with a reused key is rejected by the existing API's conflict rule.

For valid extracted intake, the graph performs:

1. Read-only Sheets lookup in the previously verified dedicated INCEPT_CLIENTS
   spreadsheet, worksheet ID 0, bounded to A1:Z101. No row is created or updated.
   Existing columns are `client_name`, `matter_id`, `status`. Name-only matches are
   explicitly **candidates requiring lawyer review**, not established identity or
   a reliable cross-system case match. If an idempotency-key column exists later,
   it is preferred. No bounded-search result is treated as proof of nonexistence.
2. Read-only Calendar calendar-list metadata check. It is **not** an availability,
   event-content, calendar-conflict or legal-deadline calculation. No event is
   created or read. Empty/unsupported Sheets schemas and API failures are explicit.
3. POST the extracted intake to the existing real onboarding endpoint on
   `127.0.0.1:8002`. No new Python service, identity logic or paid model call is
   introduced. The existing local SQLite idempotency, Decimal invoice arithmetic,
   reviewed local RAG cards, typed schemas and draft generation are reused.
4. Validate the actual bundle using the previous strict n8n response checks:
   identities, draft status, exact five-hour arithmetic, all source references,
   missing data, confidence and every approval-pending action.
5. Select at most one case-relevant allowlisted primary-source retrieval, verify its wording through the local FastAPI helper, and enrich the assessment and potential-deadline analysis. See `docs/incept_primary_source_research.md`.
6. Assemble **PREVIEW_READY_FOR_LAWYER_REVIEW** with live email provenance, Sheets
   lookup uncertainty, Calendar scope, structured assessment and three DEMO draft
   documents. It is not accepted representation, a sent email or an issued invoice.

Every gate has a clean error/review/needs-input branch. HTTP nodes have no workflow
retries, follow no redirects, and use only GET for Google APIs. The only POST is
local onboarding preview. Existing credential types are strictly matched and
bound by metadata on import; repository exports contain no credential bindings,
OAuth material, runtime pins or execution records.

## What has and has not been proved

Ten new offline regressions test absent/ambiguous email, header approval before
body access, body extraction, missing fields, no fixture substitution, stable
idempotency, real FastAPI bundle creation, citation/approval safety, Sheets
limitations, Calendar scope, credential binding and accurate stop-state reporting.
Offline synthetic-email success tests are not passed off as real email execution.

```sh
python -m unittest discover -s tests -p test_incept_autonomous_workflow.py -q
python -m unittest discover -s tests -q
```

Once an approved matching fictional inquiry is supplied, click Execute Workflow
on the new inactive workflow or execute the installed CLI (the same method used
for #15):

```sh
N8N_RUNNERS_BROKER_PORT=5689 \
N8N_RUNNERS_MODE=internal \
N8N_DIAGNOSTICS_ENABLED=false \
N8N_VERSION_NOTIFICATIONS_ENABLED=false \
N8N_LICENSE_AUTO_RENEW_ENABLED=false \
/usr/local/bin/node $N8N_CLI \
  execute --id=FeRkXfcrj8dceBZh --rawOutput
```

Keep raw execution data private. Only sanitized counts/provenance/status and
explicitly fictional generated bundles should be exported. Do not activate the
workflow or edit successful prior workflows to run this test.

## Current research scope and remaining limits

The workflow selects one bounded primary-source action for a contractual payment
allegation: GET official BGB §286. Execution 19 verified source rules in paragraphs
1 and 4 and incorporated their citations into the assessment and potential-deadline
analysis. This is real rule-selected primary-source verification beyond static
RAG, not broad autonomous legal investigation. The source does not prove the
claim, maturity, receipt or responsibility in this fictional matter.

All confirmed/calculated deadlines remain null. The local preview is idempotent;
execution 19 reused the matter created in execution 18. No pending action executed.
The five prior successful workflows remain unchanged. Production legal templates,
original case evidence, lawyer approval and broader Project 3 acceptance remain
outside this bounded live connectivity/research demonstration.
