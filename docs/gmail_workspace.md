# INCEPT Gmail-to-mandate workspace

## Launch

From the repository root, in the installed backend environment:

```sh
python -m scripts.gradio_app
```

Exact direct command for this machine (also avoids unrelated base-Conda plugin warnings):

```sh
/opt/anaconda3/envs/bootcamp-env/bin/python -m scripts.gradio_app
```

Open http://127.0.0.1:7860. The existing n8n instance must be running on http://127.0.0.1:5678 with its existing private `N8N_API_KEY` and authorized `gmailOAuth2` credential. The launcher starts the isolated FastAPI helper on loopback port 8010. No credentials are entered into the browser or changed by setup. If an unrelated process occupies 8010, stop and resolve it; the launcher never kills it.

The previous fixed demonstration remains in **DEMO FALLBACK**, clearly separate from selected-email processing. `python -m scripts.gradio_app --demo-only` opens that original interface alone. No selected message is ever replaced by the fallback scenario.

## Actual user journey

1. **INBOX:** the page loads recent metadata automatically; click Refresh real Gmail inbox to reload. At most eight recent messages are listed, using real IDs and sender/date/subject/snippet metadata. Optional Gmail search stays within the inbox. Bodies are fetched only on selection, rendered as plain text with attachments listed. No remote images/scripts execute. Selecting another message clears/replaces its workspace content; refresh retains a selected message.
2. **Analyze mandate:** confirm the selected inquiry is an authorized fictional/test message. Confirm the client profile on MANDATE, then analyze. The existing paid extractor remains disabled. The prior real extraction may be reused only for the exact original message/body hash; otherwise unknown client identity/type/law requires manual confirmation. The email body itself supplies the unverified facts. No dummy analysis or fixed-case substitution occurs.
3. **MANDATE:** edit the supplied client/firm details, sender's claimed role and optional company/representative details. Client jurisdiction and matter governing law are separate: Germany is never inferred merely from company country. Blank addresses/representatives remain visibly missing. Click Save corrections & regenerate; the real backend creates a versioned draft through n8n. The workspace case stays tied to the message; backend preview records are immutable versions, not silently edited approvals. Identical requests reuse an existing result unless reanalysis is explicitly requested.
4. **DOCUMENTS:** inspect the three actual v2 drafts, statuses and missing fields. Download each as PDF. Rendering converts existing template Markdown to PDF; it is not a second legal-document engine. Downloads are permitted for internal review even when external transmission is blocked.
5. **Lawyer transmission review:** no attachments are selected by default. Only `DRAFT_COMPLETE_FOR_LAWYER_REVIEW` Vollmacht/fee drafts with supplied client/firm details can receive a named, explicit, revision/hash-bound transmission release. MISSING_INFORMATION, LEGAL_REVIEW_REQUIRED, NOT_READY_FOR_ISSUANCE and other blocked drafts cannot be attached. The advance request is always blocked for attachment in this pilot. Editing/regenerating invalidates previous releases. A transmission release is not legal approval, mandate acceptance, signing authority or invoice issuance.
6. **REPLY:** inspect/edit the suggested sender-based recipient, subject and body. The sender is not presumed to be the client or authorized representative. Preview shows the exact recipient, content and filenames. Any change after preview requires another preview. Explicit final confirmation is mandatory for each send. The controlled pilot permits **only the connected account's own address**; external companies/clients, CC/BCC and header injection are blocked. Actual Gmail results and n8n IDs are shown; failed/uncertain sends never automatically retry. MIME threading preserves the source thread and headers where available.

## Backend and n8n path

The workspace uses existing FastAPI preview, local legal/RAG references, payment-source verification and document engine v2.0.0. No paid extraction/synthesis, registry or financial operation is enabled. If explicit German governing law and invoice/payment indicators are present, n8n reads the allowlisted official BGB 611/320/641 pages and checks original bytes through the existing verifier. Source failures become visible missing evidence, not invented findings or deadlines.

n8n is the orchestrator: separate inactive manual workflows perform Gmail operations and selected-message processing. Before preview generation the analysis flow rereads the exact selected Gmail message and validates its encoded text-part identity. UI form data cannot choose HTTP destinations, credential types or CLI commands. Node destinations/verbs are allowlisted, retries disabled, operations serialized, and raw results privately recorded. Historical workflows remain untouched. The sanitized inbox export is `workflows/incept_workspace_inbox.json`; private bound per-case/send workflows are never exported to Git.

New files are narrow adapters/UI: `scripts/gmail_workspace.py`, `scripts/workspace_workflow.py`, `scripts/workspace_ui.py`. Existing report/evidence/document modules are reused. No parallel legal reasoning engine or new provider API was built.

## Verified real results

- Read-only n8n executions **41–42** verified inbox metadata and the existing approved fictional email. Gradio callbacks then performed actual reads and analysis.
- **45:** selected email generated a new matter assessment and three backend drafts, preserving the claimed client, counterparty and alleged amount.
- **46:** a deliberately fictional address correction regenerated the backend artifacts. Three official source checks succeeded, five actions remained pending and EUR 1,250 + EUR 237.50 demo VAT = EUR 1,487.50 remained unchanged.
- All three current PDFs downloaded over Gradio HTTP with status 200.
- **49:** after separate explicit user authorization, the real Gradio preview/confirmation path sent **one self-addressed reply with no attachments**. Gmail returned an actual message ID. This verifies effective read/send capability of the existing OAuth credential; the OAuth scope/token strings were not read or exported.
- Complete-draft attachment eligibility, revision invalidation and actual PDF MIME construction are regression-tested offline. The real self-send deliberately carried no attachments because the current case documents were incomplete. No live attachment-send success is claimed.

[Sanitized verification](gmail_workspace_validation.json). Full Gmail IDs, raw inbox content, credential references, previews, n8n traces and SQLite records remain under ignored `data/gmail_workspace/`; PDFs under ignored `downloads/`. Do not commit them. The UI serves generated downloads only, blocks private runtime/report/env/Git paths and binds to loopback with no public share.

## Honest limits

This remains a local, single-account **fictional/test-matter pilot**, not a production law-firm inbox system. The existing preview backend intentionally rejects real contact domains; a clearly artificial `.invalid` noncontact placeholder stays in its internal demo record. The actual Gmail contact is retained separately for display/reply and is never represented by that placeholder. Missing details are not fabricated. Long bodies are retained in the inbox viewer, but only 2,900 whitespace-normalized characters enter bounded assessment; omission is explicitly warned.

No paid AI calls occurred. The deterministic assessment is labeled accordingly; source-exact synthesis v2 remains an offline-tested experiment with no accepted live synthesis. No company lookup, automatic mandate acceptance, confirmed deadline, Google Sheets/Calendar write or invoice issuance is performed. External-recipient sending is deliberately disabled. Professional review, production authentication/tenancy, comprehensive attachment ingestion, unrestricted real-client processing and advanced mailbox pagination remain out of scope.
