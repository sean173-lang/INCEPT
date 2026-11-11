# Pre-Gradio checkpoint: live document engine v2

The document engine was already committed in `bdc7fbadf3d71ef7a2db2764fb0e327d5d3dde75`. This checkpoint adds the reproducible, sanitized execution-28 development graph and evidence documentation; it does not replace that implementation or rewrite earlier work.

## Actual execution

The separate inactive workflow `cjECMFGDqC8MpYfF` (37 nodes) completed real n8n **execution 28** with business outcome **PREVIEW_READY_FOR_LAWYER_REVIEW**. A single explicitly authorized self-addressed synthetic email was sent in execution 27. The message was retrieved through the actual Gmail metadata/body gate. No fixture substituted for Gmail, Sheets, Calendar or FastAPI.

The fictional German corporate client and its representative remain unverified intake facts. Corporate research selected the German/OpenRegister helper but returned NEEDS_REVIEW because registration/court/provider identifiers were missing. There was no live registry lookup or invented corporate evidence. Sheets returned one row and Calendar one calendar via read-only operations. Bounded official BGB §286 retrieval returned HTTP 200 and two source-wording checks passed; no case finding or confirmed deadline resulted. Local RAG and document-law references were used.

All three actual Markdown documents were inspected in full and validated for party/matter/firm consistency, restricted authority, rate/tax arithmetic, mandatory fee notice and pending approval. There was no blocking generation defect observed; this is not a professional legal opinion.

| Document | Version | Actual status | Open issues |
|---|---|---|---|
| Rechtsanwaltsvollmacht | 2.0.0 | LEGAL_REVIEW_REQUIRED | Representative authority asserted only |
| Vergütungsvereinbarung | 2.0.0 | LEGAL_REVIEW_REQUIRED | Authority and individual professional review |
| Vorschussanforderung | 2.0.0 | NOT_READY_FOR_ISSUANCE | Issue date, unique invoice number, tax number/VAT ID; tax/e-invoice review |

Explicit demo calculation: **5 × EUR250 net = EUR1250; 19% VAT EUR237.50; gross EUR1487.50**. No bank credentials or fiscal identifiers were fabricated. Five actions stayed pending lawyer approval. No mandate was accepted or invoice issued; no Sheet/Calendar write, Tavily request, financial request or live registry query occurred.

[Sanitized execution summary](incept_live_documents_v2_validation.json). Full private documents and checklists remain under `reports/incept_live_documents_v2/`. Raw traces remain under `data/incept_live_documents_v2/`. Neither runtime directory is published. Execution 26 and historical workflows are preserved.

## Reproduce the export safely

```sh
python -m scripts.incept_document_workflow
python -m unittest discover -s tests -q
```

The generated file is `workflows/incept_live_documents_v2.json`. It preserves the tested graph, bounded corporate cache policy and added v2 metadata checks. It has no OAuth credential bindings, webhook identifiers, message bodies, execution payloads or account/spreadsheet identifiers. The workflow is manual-only and inactive. It contains no sending, scheduling, Sheet-writing or linked-workflow node.

For local import, use n8n **Import from File** as a separate inactive workflow. Bind existing compatible credentials locally: Gmail OAuth2 for the Gmail GETs, Sheets OAuth2 for the read node, Calendar OAuth2 for calendar-list. Configure the authorized dedicated Gmail account in the search and metadata gate, and the project spreadsheet ID in the read node and lookup summary. `build_workflow(project_account=..., spreadsheet_id=...)` can produce those bindings in memory; keep any account-bound file private. Do not reconfigure the already successful local workflow to match the placeholders.

Leave placeholders unchanged until configuration is explicit; the metadata gate will not silently accept a different sender. The exact subject is `[INCEPT DEMO APPROVED] German corporate onboarding v2`; the body starts `INCEPT_SYNTHETIC_INTAKE_V1` followed by a complete typed synthetic request, including `document_options`. The tested input is private; safe schema examples are under `examples/documents/`. A new test must have a unique test/matter identifier. Sending an email or executing Google integrations requires separate explicit authorization: import does not authorize either. No one-email sending workflow or raw email is included in this export.

The service is the existing loopback helper on port 8003 with development mode and paid APIs disabled. See [document setup and schemas](legal_document_generation.md). Existing idempotency uses the actual approved message ID; do not send another message merely to retry processing an existing test.

## Verification boundaries

The live run passed the 315-test baseline. Four additional offline checkpoint tests verify export reproducibility, sanitization, manual/read-only node configuration and v2 approval/issuance guards. They execute no external API or n8n workflow. A fresh execution is not claimed by this checkpoint.

The backend is ready for controlled Gradio **draft-review** integration. Gradio is not implemented here; template/legal approval, representative evidence, tax configuration and valid issuance details remain outstanding. No automatic external-action execution is authorized. Checkpoint publication is feature-branch only, with no merge into main.
