# Repository cleanup inventory

Checkpoint `f5f751f5bf46a8fb0182a4edfd6ec0fd39497391`: **194 tracked files**, **1,575,092 bytes**. Working tree was clean; cleanup branch starts exactly at that checkpoint. No newer work was discarded.

## Audit and dependency decisions

Entry point: `scripts.http_service:app` / `create_app`. Current API routes expose onboarding, corporate verification/research, local RAG and bounded fixture-only planning. Canonical graph: `workflows/incept_live_documents_v2.json`, proven in execution 28 and containing UK-validator and document-v2 guards. Four layered builder modules provide unique reusable validators/routing and remain dependencies of this graph; intermediate exports and old CLI exporters are removed.
Financial reachability to sever: `report_renderer -> due_diligence -> financial_analysis`; `research_pipeline -> due_diligence.DOCUMENT_REQUESTS`; mixed German and UK adapters contain optional financial/document download APIs. Preserve identity/search/officer APIs and safe metadata, replace the shared renderer with its active escaping helper, inline a legal-only document checklist and remove financial topics. No retained workflow invokes the retired endpoints.
Private `data/` and `reports/` are ignored. Execution 26/28 files are fingerprinted and preserved. Private ledgers, original provider caches and unknown-ownership records are REVIEW rather than deleted: resetting them could lose audit/credit history. Selected conclusively obsolete financial report exports are removed individually; no archive or broad directory wipe is used.
Project 3 retains three live Google-integration evidence, real Companies House/counterparty and Tavily summaries, official-law/RAG provenance, three synthetic assessment examples, two document-law scenarios, stack justification, GTM sprints and demo instructions. No synthetic data is relabeled live.

## Tracked files by directory

| File | Decision | Reason |
|---|---|---|
| `.env.example` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `.gitattributes` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `.gitignore` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `PROJECT3_SUBMISSION_CHECKLIST.md` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `README.md` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `config/volkswagen_live_test.json` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `docs/api_usage.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/architecture.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/day2_architecture.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/demo_script.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/german_accounts.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/github_presentation.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/gtm_future_sprints.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/incept_autonomous_intake_dev.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/incept_corporate_intelligence.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/incept_corporate_n8n_validation.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/incept_google_integrations.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/incept_google_sheets_test.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/incept_live_documents_v2.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/incept_live_documents_v2_validation.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/incept_primary_source_research.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/incept_submission_validation.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/legacy_legalflow.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/legal_document_generation.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/legal_document_http_validation.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/legal_document_quality_audit.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/legal_document_sources.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/legal_document_validation.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/legal_intake_mvp.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/legal_intake_n8n.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/legal_intake_n8n_validation.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/n8n_fastapi_development.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/phase1_service.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/phase2_research.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/shapesty_financial_test.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/stack_decision.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/tavily_integration.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/tavily_live_validation.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `docs/validation_execution9.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/volkswagen_financial_test.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/volkswagen_live_test.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `docs/workflow_validation.md` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `examples/documents/README.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/corporate/advance_invoice.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/corporate/fee_agreement.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/corporate/input.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/corporate/review_checklist.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/corporate/validation.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/corporate/vollmacht.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/individual/advance_invoice.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/individual/fee_agreement.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/individual/input.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/individual/review_checklist.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/individual/validation.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/documents/individual/vollmacht.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/incept_approved_demo_inquiry.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/onboarding_preview.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/reports/germany_company_mandate_assessment.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/reports/individual_mandate_assessment.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `examples/reports/uk_company_mandate_assessment.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `gtm_future_sprints.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/README.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/corporate_due_diligence.json` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `references/german_accounts_sigma_2024.json` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `references/incept_corporate_demo.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/corpus.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-126b.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-164.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-165.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-166.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-167.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-168.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-169.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-170.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-171.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-172.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-173.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-174.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-175.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-176.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-177.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-178.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-179.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-180.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bgb-181.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/bmf-einvoice.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/brao-49b.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/rvg-10.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/rvg-34.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/rvg-3a.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/rvg-4.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/rvg-4b.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/rvg-9.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/ustg-12.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/ustg-13.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/ustg-14.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/ustg-19.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/legal_documents/snapshots/ustg-27.txt` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `references/mandate_intake.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `requirements-accounts.txt` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `requirements-service.txt` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `requirements.txt` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `scripts/accounts_parser.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/api_usage.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/companies_house.py` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `scripts/company_research.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/company_search.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/company_service.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/corporate_intelligence.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/development_fixtures.py` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `scripts/document_examples.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/document_schemas.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/due_diligence.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/evidence_validator.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/financial_analysis.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/financial_cache.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/financial_errors.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/german_accounts.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/german_register.py` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `scripts/http_service.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/incept_autonomous_workflow.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/incept_corporate_demo.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/incept_corporate_execution_test.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/incept_corporate_test_service.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/incept_corporate_workflow.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/incept_document_workflow.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/incept_google_read_workflows.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/incept_sheets_workflow.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/intake_workflow.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/legal_documents.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/legalflow_agent.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/local_rag.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/n8n_workflow.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/onboarding.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/onboarding_demo.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/onboarding_schemas.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/primary_research.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/report_renderer.py` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `scripts/research_pipeline.py` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `scripts/research_schemas.py` | CONSOLIDATE | Active shared component; remove only retired financial branches/dependencies |
| `scripts/service_schemas.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/submission_audit.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `scripts/volkswagen_continuation.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/volkswagen_financial_test.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/volkswagen_live_test.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/volkswagen_profile.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `scripts/workflow_validation.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `templates/german_legal/v2/advance_invoice.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `templates/german_legal/v2/fee_agreement.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `templates/german_legal/v2/manifest.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `templates/german_legal/v2/vollmacht.md` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/fixtures/bgb286_sanitized.html` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/offline_support.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_404_and_research.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_api_usage.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_corporate_intelligence.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_evidence_validator.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_financial_cache_regression.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_financial_errors.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_financials.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_german_accounts.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_http_service.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_incept_autonomous_workflow.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_incept_corporate_workflow.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_incept_document_workflow.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_incept_google_read_workflows.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_incept_sheets_workflow.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_intake_workflow.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_legal_documents.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_n8n_workflow.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_onboarding.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_primary_research.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_rag_research.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_report_renderer.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_repository_exports.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_tavily_adapter.py` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `tests/test_volkswagen_continuation.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_volkswagen_financial_test.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_volkswagen_live_test.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `tests/test_workflow_validation.py` | REMOVE | Retired financial/legacy CLI or isolated-test implementation; active dependencies migrated before removal |
| `workflows/incept_autonomous_intake_dev.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_calendar_read_test.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_corporate_intake_dev.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_corporate_test_ambiguous.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_corporate_test_germany_company.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_corporate_test_individual.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_corporate_test_uk_company.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_gmail_read_test.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_google_sheets_read_test.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/incept_live_documents_v2.json` | KEEP | Current service, canonical workflow support, offline tests, curated evidence, legal source/template or deployment safeguard |
| `workflows/legal_intake_onboarding.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/legalflow_fastapi_development.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/legalflow_phase2_development.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |
| `workflows/legalflow_workflow.json` | CONSOLIDATE | Superseded by canonical execution-28 graph or consolidated current docs |

## Largest tracked files before cleanup

| Bytes | Path |
|---:|---|
| 58,858 | `workflows/incept_live_documents_v2.json` |
| 58,342 | `workflows/incept_corporate_intake_dev.json` |
| 52,081 | `workflows/incept_corporate_test_germany_company.json` |
| 51,944 | `workflows/incept_corporate_test_uk_company.json` |
| 51,934 | `workflows/incept_corporate_test_ambiguous.json` |
| 51,834 | `workflows/incept_corporate_test_individual.json` |
| 50,307 | `references/legal_documents/corpus.json` |
| 48,990 | `workflows/incept_autonomous_intake_dev.json` |
| 35,042 | `workflows/legalflow_phase2_development.json` |
| 26,953 | `docs/legacy_legalflow.md` |
| 24,803 | `workflows/legalflow_fastapi_development.json` |
| 23,866 | `scripts/volkswagen_profile.py` |

## Dependency verification method

AST import and literal-path inspection plus repository-wide `rg` checks precede removal. The complete baseline test method inventory is recorded privately and all removed methods will receive a reason in the final deletion/test ledger. Active semantic tests are adapted, not dropped merely for failing after a refactor. The full suite, imports, real ASGI routes, graph expressions, templates, links and secrets are checked after migration. No running n8n workflow is modified.
