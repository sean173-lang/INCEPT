# GitHub presentation and review

Repository: `sean173-lang/legalflow` (retain its name and history).

Public description:

> INCEPT is an AI-powered legal onboarding agent that automates client intake, mandate assessment, and German/UK corporate intelligence using n8n, FastAPI, and RAG.

Metadata update verified through the authorized GitHub REST API on 2026-11-11. The repository name and default branch were not changed.

Topics: `legal-tech`, `ai-agents`, `n8n`, `fastapi`, `rag`, `legal-automation`, `corporate-intelligence`, `ironhack`.

The About description and topics are repository metadata, independent of the default branch README. If API permission is unavailable, open the repository homepage, click the gear beside About, paste the description and topics above, then save. No repository rename is needed.

Publish documentation to `feature/legal-intake-mvp`, then open a pull request with base `main` and compare `feature/legal-intake-mvp`. Review includes the accumulated tested implementation because main still contains the historical LEGALFLOW baseline. Preserve earlier commits; do not force-push or merge automatically.

Private `.env`, OAuth tokens, caches, raw executions, runtime reports, databases and backups remain excluded. Only synthetic sample reports and sanitized execution summaries belong in the review.
