# Project 3 submission checklist

Current primary UI: [Gmail workspace and verification](docs/gmail_workspace.md); [preserved deterministic fallback](docs/gradio_demo.md). The original course rubric was not located, so grading compliance must be confirmed with the instructor. This table distinguishes current demonstration, historical real integrations and experimental AI.

| Requirement | Evidence and honest status |
|---|---|
| Working Gradio UI | Real inbox/selection, selected-message analysis, editable missing details with backend regeneration, PDF downloads, guarded composer; fixed DEMO fallback retained |
| n8n primary orchestration | Real Gmail selected-message processing **45**, corrections **46**, confirmed self-send **49**; original structured demo **38–39** preserved |
| One-command launch | `python -m scripts.gradio_app`; existing local n8n needed only for a fresh orchestration run; saved mode works without it |
| Three real external integrations | Gmail, Google Sheets and Google Calendar previously verified in real executions; recorded combined intake/research evidence in [execution 26](docs/live_integration_evidence.json), [execution 28](docs/incept_live_documents_v2_validation.json). Current workspace Gmail read/self-send also verified in 41–49; Sheets/Calendar evidence remains historical |
| Autonomous research → report | Historical bounded official-source research and local RAG are preserved. The workspace retrieves allowlisted official German provisions when applicable and builds deterministic reports; it does not perform fresh model synthesis |
| Real AI reasoning / synthesis | **Not yet an accepted live synthesis.** Real extraction response was grounded, but synthesis in **34** was rejected. Source-exact v2 passes offline mock tests. Present as experimental, not completed live AI |
| RAG and source attribution | Existing scoped local legal corpus, original source URLs/review dates and evidence labels retained; reference guidance separated from case findings |
| German / UK corporate capabilities | Existing adapters/cache-only helpers and offline matching tests retained. Current fictional Gradio scenario does not require registry calls or claim real company verification |
| Mandate Assessment | Real backend deterministic result or explicitly labeled saved synthetic backend fixture; citations and missing evidence visible |
| Three legal documents | Existing engine v2.0.0; representative/mandatory details remain placeholders; all drafts unapproved and advance NOT_READY_FOR_ISSUANCE |
| Error handling / idempotency | n8n validation branches, exact-workflow execution guard, real-trace requirement, explicit saved fallback, locks and persistent matter idempotency |
| Human approval | Five original actions remain pending. Explicit, revision-bound complete-draft transmission releases exist. One separately authorized self-send verified in **49**, no attachments; external recipients/invoices/mandate acceptance remain blocked |
| Two sample reports | Existing distinct [assessment examples](examples/reports/individual_mandate_assessment.md) and [UK example](examples/reports/uk_company_mandate_assessment.md) retained; new fixed synthetic German bundle in `examples/gradio_demo/` |
| 5–7 minute presentation | [Script](docs/demo_script.md), with truthful AI and historical-integration boundaries |
| GitHub checkpoint | Demo feature branch; reviewed safe artifacts only; no automatic main merge |

Production authentication/tenancy, professional legal approval, a reliable accepted live AI synthesis and instructor confirmation of the original rubric remain outstanding. The application is ready to demonstrate deterministic onboarding, n8n orchestration and document review; this does not guarantee every AI grading criterion is satisfied.
