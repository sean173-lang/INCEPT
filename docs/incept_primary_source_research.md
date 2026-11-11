# INCEPT — one bounded primary-source research action

Current development workflow: `FeRkXfcrj8dceBZh`, inactive, **30 nodes**.
The original 23-node execution #15 remains historical evidence of
`NEEDS_DEMO_EMAIL`. The initial preparation stopped pending user input. After the user supplied the
email, **execution 19 completed successfully** with verified source guidance and
all draft actions still pending lawyer approval. See `reports/incept_execution_19/`.
The sender, recipient, exact subject, body marker, size cap and sample inquiry
are unchanged. No email was created or sent.

## Phase 1: unchanged manual email contract

- Sender: `ironhackproject3@gmail.com`.
- Recipient: `ironhackproject3@gmail.com`.
- Exact subject: `[INCEPT DEMO APPROVED] Fictional intake v1`.
- Body: paste `examples/incept_approved_demo_inquiry.txt` verbatim, including the
  `INCEPT_SYNTHETIC_INTAKE_V1` first line and all existing JSON fields. Its dates,
  VAT assumption and requested scope are deliberately not changed to force a pass.
- Received copy must be in Inbox, not Spam/Trash/Drafts; unique matching message,
  exact headers, valid metadata and no more than 64 KB. No original email/thread
  or attachment is needed. The workflow fetches only an approved specific body.

To print the exact body locally:

```sh
cat examples/incept_approved_demo_inquiry.txt
```

After manually sending it, click **Execute workflow** on
`FeRkXfcrj8dceBZh`. No activation is needed. Exact alternative on this installation:

```sh
N8N_RUNNERS_BROKER_PORT=5689 \
N8N_RUNNERS_MODE=internal \
N8N_DIAGNOSTICS_ENABLED=false \
N8N_VERSION_NOTIFICATIONS_ENABLED=false \
N8N_LICENSE_AUTO_RENEW_ENABLED=false \
/usr/local/bin/node $N8N_CLI \
  execute --id=FeRkXfcrj8dceBZh --rawOutput
```

Keep raw execution output private. No send action is included in the workflow.

## Phase 2: plan, fetch, verify, enrich

For a German contractual payment-demand allegation, the rule-based planner
selects exactly one approved source/tool:

[Official BGB §286 — Verzug des Schuldners](https://www.gesetze-im-internet.de/bgb/__286.html).

The n8n plan has `max_source_requests: 1`; the URL is fixed, not taken from intake.
No commercial search, paid provider, retry, redirect following or arbitrary URL
fetch is allowed. Unrelated matters take a `not_applicable` branch without a
fetch. Network failures, HTTP errors and oversized responses become unavailable
research, rather than preventing the underlying DEMO preview or inventing law.

The node retrieves text from the official publisher, records receipt time, and
submits original source bytes plus the real typed onboarding bundle and original matter to:

```text
POST http://127.0.0.1:8002/v1/onboarding/research/verify
```

The existing separate port-8002 helper was reloaded with this endpoint; the
corporate port-8000 service and all n8n credentials remain untouched. The helper
performs **no networking**. It checks:

- Development/synthetic request constraints and exact bundle/matter consistency.
- Exact allowlisted URL, HTTP status, timestamp and a maximum 200 KB HTML body.
- Strict decoding using the declared HTTP/HTML charset (UTF-8, ISO-8859-1 or Windows-1252); conflicting, lossy or unsupported encoding is unavailable.
- Expected BGB/provision heading and paragraph elements, excluding scripts/styles.
- Reviewed exact wording for the first sentence of §286(1) and for §286(4).
- Each separately supported claim gets a paragraph citation, source ID, literal
  supporting quote, source URL, retrieval timestamp and original source-byte SHA256.

The two selected claims concern the **general** reminder-after-maturity rule and
non-performance not attributable to the debtor. They do not establish the
validity of this alleged debt, payment maturity, responsibility, receipt of a
reminder or applicability of exceptions. Other §286 paragraphs and other legal
rules still require review. Source amendment dates are not inferred from retrieval.

Changed/missing wording withholds that claim; one intact rule may be reported as
`partially_verified`. Unrelated pages, missing headings, unavailable network data,
stale/future timestamps or unsupported helper responses yield `unavailable`.
No claim is extracted from a search excerpt or hidden script.

The helper enriches a **copy** of the Mandate Assessment Report: new source-backed
guidance and sources, unresolved-research warnings and a Potential Deadline
Analysis. The immutable idempotent base preview remains unchanged. The final n8n
report uses this enriched assessment and records source status and verification
limits. Client allegations remain unverified; legal source rules are not promoted
to case findings. No untrusted HTML is included in the final report.

## Potential Deadline Analysis

The input's claimed date is only a candidate. Both `confirmed_deadline` and
`calculated_deadline` remain null, and the state remains
`pending_lawyer_approval`. Contract/due-date evidence, original demand and receipt,
any procedural document/service and applicable exceptions are listed as missing.
No 30-day period, limitation date, payment due date or procedural deadline is
calculated from missing evidence. No Calendar event is created.

## Actual verification and tests

A standalone read of the real official page returned **HTTP 200**. The retrieved
page was then checked through the actual local helper: **HTTP 200**, two supported
source rules, source hash recorded, and no confirmed/calculated deadline.
The standalone source receipt timestamp is the immediate cached-file receipt
mtime from that download; workflow retrieval uses its own post-response timestamp.

Evidence: `reports/incept_primary_source_verification.json`. It is explicitly
labeled `standalone_real_official_source_and_helper_check_not_full_email_workflow`
and has no n8n execution ID. It contains source evidence, not an invented Gmail
execution. The cached public source is in ignored `data/incept_primary_research/`.

Offline tests use a sanitized statutory excerpt, never a claimed live response:

```sh
python -m unittest discover -s tests -p test_primary_research.py -q
python -m unittest discover -s tests -p test_incept_autonomous_workflow.py -q
python -m unittest discover -s tests -q
```

They cover citation support, partial/source-change rejection, unrelated pages,
hidden text, network/HTTP errors, timestamps, mismatched matter context, helper
guards, source selection, enrichment, and refusing unsafe confirmed deadlines.
Full offline result at preparation: **269 tests passed**.

## Completed live run and Project 3 limits

Actual n8n execution **19** completed the user-sent approved inquiry, Sheets lookup,
Calendar metadata check, real onboarding bundle, official-source GET, verified
paragraphs and enriched report in one trace. Source status was `verified` with
two supported rules; no case merits or legally significant date was confirmed.

Earlier failed executions 17 and 18 remain recorded. Email string wraps now have
an explicit whitespace-only normalization audit flag. The public source is fetched
as bytes because its response lacked a charset header while its HTML declared
ISO-8859-1. No lost characters are guessed or replaced. The final report explicitly
uses the validated onboarding bundle, not the research node's input item.

This is a bounded, rule-selected primary-source check plus RAG, not a comprehensive
legal opinion or general-purpose autonomous legal research agent. Case-document
review, production-ready terms, lawyer approval and additional sample cases remain
outstanding. No outgoing email, external write, paid API call, commit or push was
performed to obtain this result.
