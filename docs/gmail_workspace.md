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

Open http://127.0.0.1:7860. The existing n8n instance must be running on http://127.0.0.1:5678 with its existing private `N8N_API_KEY` and authorized `gmailOAuth2` credential. The launcher starts the isolated assessment/document FastAPI helper on loopback port 8010. The existing synthesis FastAPI service on loopback port 8003 must also be reachable for the Analyze action to attempt AI synthesis; no credentials are entered into the browser or changed by setup. If an unrelated process occupies either port, stop and resolve it; the launcher never kills it.

The previous fixed demonstration remains under **Advanced → Fixed DEMO FALLBACK**, clearly separate from selected-email processing. `python -m scripts.gradio_app --demo-only` opens that original interface alone. No selected message is ever replaced by the fallback scenario.

## Actual user journey

1. **INBOX:** the page loads recent metadata automatically; click Refresh Gmail to reload. At most eight recent messages are listed, using real IDs and sender/date/subject/snippet metadata. Optional Gmail search stays within the inbox. Bodies are fetched only on selection, rendered as plain text with attachments listed. No remote images/scripts execute. Selecting another message clears the previous report, documents, downloads, reply preview and test acknowledgement; refresh retains a selected message.
2. **ANALYZE:** confirm the selected inquiry is an authorized fictional/test message. Confirm the client profile under ANALYSIS → Client details, then analyze. The existing paid extractor remains disabled. The prior real extraction may be reused only for the exact original message/body hash; otherwise unknown client identity/type/law requires manual confirmation. The email body itself supplies the unverified facts. No dummy analysis or fixed-case substitution occurs. Status remains visible above the three primary tabs and identifies **accepted live AI analysis** or **deterministic fallback with a sanitized reason**; mock output is never labeled AI-generated. Analyze calls the assessment-only FastAPI endpoint through n8n, checks relevant official BGB wording, then calls the existing `POST /v1/onboarding/synthesis` with contract v2. Synthesis must pass source-exact evidence, citation, identity, jurisdiction and lawyer-safety validation to be displayed as AI analysis. It does not call the document engine or create PDFs. Cached accepted analyses are labeled as existing results; Advanced → Reanalyze requests fresh processing.
3. **ANALYSIS → Client details:** edit the supplied client/firm details, sender's claimed role, client representative and known counterparty details. Client jurisdiction and matter governing law are separate: Germany is never inferred merely from company country. Blank addresses/representatives remain visibly missing. Click Save details & regenerate to refresh the assessment through n8n/FastAPI. The workspace case stays tied to the message; assessment results remain versioned and are not silently edited approvals.
4. **ANALYSIS → Legal documents:** only if needed, click **Generate legal document drafts (optional)** after reviewing the assessment. This starts a separate n8n execution against the existing FastAPI preview/document engine. Then inspect the three v2 drafts, statuses and missing fields and download each as PDF. Rendering converts existing template Markdown to PDF; it is not a second legal-document engine. Downloads are permitted for internal review even when external transmission is blocked.
5. **Lawyer transmission review:** no attachments are selected by default. Only `DRAFT_COMPLETE_FOR_LAWYER_REVIEW` Vollmacht/fee drafts with supplied client/firm details can receive a named, explicit, revision/hash-bound transmission release. MISSING_INFORMATION, LEGAL_REVIEW_REQUIRED, NOT_READY_FOR_ISSUANCE and other blocked drafts cannot be attached. The advance request is always blocked for attachment in this pilot. Editing/regenerating invalidates previous releases. A transmission release is not legal approval, mandate acceptance, signing authority or invoice issuance.
6. **REPLY:** inspect/edit the suggested sender-based recipient, subject and body. The sender is not presumed to be the client or authorized representative. Preview shows the exact recipient, content and filenames. Any change after preview requires another preview. Explicit final confirmation is mandatory for each send. The controlled pilot permits **only the connected account's own address**; external companies/clients, CC/BCC and header injection are blocked. Actual Gmail results and n8n IDs are shown; failed/uncertain sends never automatically retry. MIME threading preserves the source thread and headers where available.

## Backend and n8n path

The workspace uses separate FastAPI assessment, existing synthesis and optional document-preview operations, local legal/RAG references, payment-source verification and document engine v2.0.0. Paid synthesis remains disabled unless the existing FastAPI configuration, service authentication, explicit approval and persistent request/token budgets permit it; extraction, registry and financial operations remain disabled. If explicit German governing law and invoice/payment indicators are present, n8n reads the allowlisted official BGB §§ 611, 614, 631, 632a, 633, 634, 640, 641 and 320 pages and checks original bytes through the existing verifier. Source failures remain visible and are not presented as verified rules.

n8n is the orchestrator: separate inactive manual workflows perform Gmail operations, assessment and optional document generation. Before either generation action the workflow rereads the exact selected Gmail message and validates its encoded text-part identity. UI form data cannot choose HTTP destinations, credential types or CLI commands. Node destinations/verbs are allowlisted, retries disabled, operations serialized, and raw results privately recorded. Historical workflows remain untouched. The sanitized inbox export is `workflows/incept_workspace_inbox.json`; private bound per-case/send workflows are never exported to Git.

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

The Analyze graph is now connected to source-exact synthesis v2, but no paid AI call occurred during this integration. The current shell environment exposes the configured OpenAI key to the application code without printing it; the active FastAPI process on port 8003 returned health but its OpenAPI document did not expose the synthesis route. AI budgets are unset/zero and the persistent synthesis ledger is absent, so no live call is presently authorized or runnable. No company lookup, automatic mandate acceptance, confirmed deadline, Google Sheets/Calendar write or invoice issuance is performed. External-recipient sending is deliberately disabled. Professional review, production authentication/tenancy, comprehensive attachment ingestion, unrestricted real-client processing and advanced mailbox pagination remain out of scope.
