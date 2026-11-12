# CompanyScope

**Company research, made simple.**

> CompanyScope is an autonomous company research agent that combines German commercial-register data, public web research, retrieval-augmented generation and AI-assisted analysis to produce structured, source-referenced corporate research reports.

CompanyScope addresses the time and context-switching involved in preparing an initial company briefing. It is designed for **law firms, corporate legal teams and business research professionals** who need a fast, reviewable starting point for a meeting or counterparty review.

CompanyScope is an Ironhack Project 3 MVP, not a production-ready legal or due-diligence product. Public-web findings are discovery leads and require human verification. Automated source-ID checks do not prove that every claim is semantically supported.

## What it does

A user submits a German company name and, optionally, a commercial-register identifier. The workflow verifies the legal entity against OpenRegister, gathers a bounded set of public-web leads, retrieves short research-method notes from a local RAG corpus, and asks OpenAI for structured analysis. It validates source identifiers and report structure, then produces a Markdown briefing. The browser form can show the accepted report as a styled completion page.

- Exact legal-entity matching; ambiguous candidates are returned for user selection and are never silently chosen.
- OpenRegister registry profile and source-derived facts.
- Focused Tavily public-web search with source filtering and provenance.
- Local RAG for research methodology, never company facts.
- OpenAI Responses API synthesis using gpt-4o-mini and Structured Outputs.
- Source-ID, output-status and content-shape validation.
- Saved Markdown reports and a responsive form result page.
- Stage-specific failure responses; no automatic provider retries.

The currently deployed local workflow is active under stable workflow ID 61tsMgiWvpjit2st and contains 34 nodes. The sanitized export in this repository matches that deployed workflow after credential references are removed.

## Architecture

~~~mermaid
flowchart LR
  F[CompanyScope browser form] --> N[n8n workflow]
  H[Authenticated webhook] --> N
  M[Manual Trigger] --> N
  N --> O[OpenRegister]
  O --> T[Tavily public-web search]
  T --> R[Local RAG corpus]
  R --> A[OpenAI Responses API]
  A --> V[Source and structure validation]
  V --> P[Markdown report and form result page]
~~~

See the [workflow architecture source](docs/architecture.mmd) and [tool details](docs/tools.md). The primary orchestration stack is **n8n**. We chose it over LangGraph because this MVP has a short, mostly sequential tool path with explicit branches for identity and provider errors. The visual workflow makes those steps reviewable. Adding a second graph framework would duplicate orchestration without improving this flow.

## Research tools

| Component | Role | Boundary |
|---|---|---|
| OpenRegister | Resolve the exact German registered company and retrieve registry details | Registry data is provider-reported; missing fields remain missing. |
| Tavily | Find a small set of relevant company and industry web pages | Results are unverified leads; search coverage is not comprehensive. |
| Local RAG | Supply source-quality and meeting-preparation guidance | Methodology only; never a source of company facts. |
| OpenAI Responses API | Create structured, company-specific synthesis and research questions | gpt-4o-mini; schema and source IDs are checked before report output. |

## Setup

The workflow was verified with n8n **2.47.3**. Python helper requirements are in [requirements.txt](requirements.txt); the offline JavaScript renderer tests also require Node.js. No frontend framework or JavaScript package install is needed.

1. Install n8n 2.47.3 and start a local n8n instance. For a new installation, install the corresponding package with:

   ~~~sh
   npm install --global n8n@2.47.3
   ~~~

2. Create a local environment file and fill in credentials. Do not commit it:

   ~~~sh
   cp .env.example .env
   ~~~

   Required names are N8N_BASE_URL, N8N_API_KEY, OPENREGISTER_API_KEY, TAVILY_API_KEY, and OPENAI_API_KEY. The n8n API key needs permission to manage workflows and credentials. Setup generates or records PROJECT3_WEBHOOK_TOKEN and PROJECT3_WORKFLOW_ID locally. Keep all credentials in n8n or the ignored .env; never put key values in workflow JSON.

3. Install the Python helper dependencies:

   ~~~sh
   python -m pip install -r requirements.txt
   ~~~

4. Allow n8n to write to the reports directory and start n8n in a dedicated terminal:

   ~~~sh
   mkdir -p projects/ironhack_project3/reports
   N8N_RESTRICT_FILE_ACCESS_TO="$HOME/.n8n-files;$PWD/projects/ironhack_project3/reports" n8n start
   ~~~

   In a second terminal, from the repository root, build the sanitized export and create or update the stable workflow:

   ~~~sh
   python projects/ironhack_project3/build_workflow.py
   python projects/ironhack_project3/deploy_workflow.py
   ~~~

   deploy_workflow.py updates the existing CompanyScope workflow when present. Do not run multiple copies of n8n against the same data directory. The current exported Save Markdown Report node is configured for the verified local checkout path; on a different host, update that node’s path in projects/ironhack_project3/build_workflow.py and the n8n file-access allowlist before deployment.

## Run research

### Browser form

The production form path is /form/incept-company-research. In the local verified setup, open http://localhost:5678/form/incept-company-research after signing in to n8n with workflow execution permission. This is a **local-only address**, not a public deployment link. Enter the company name and optionally a register number. The required fields and candidate fallback are handled by the existing workflow.

### Authenticated webhook helper

Run from the repository root:

~~~sh
python projects/ironhack_project3/run_research.py "SAP SE" --register-identifier "HRB 719915"
~~~

This calls the configured local webhook POST /webhook/ironhack-company-research using PROJECT3_WEBHOOK_TOKEN. It is a live research request and can consume provider usage. The workflow requires the authenticated header X-Project3-Token and reuses the same workflow for each request.

### Manual execution

Open the existing workflow in n8n and click **Execute workflow**. The Manual Trigger uses the configured demonstration input. For a real research run, use the production form or authenticated webhook.

## Reports and files

- Accepted research produces a Markdown report under projects/ironhack_project3/reports/ on the n8n host.
- The browser form renders that validated report in the completion page; manual and webhook runs retain their JSON response contract.
- Two redacted examples from successful runs are provided: [Urban Sports GmbH](examples/sample_report_1.md) and [someform Studio GmbH](examples/sample_report_2.md). Their run IDs and model-run metadata were removed; report content and source links were retained.
- The workflow export is [projects/ironhack_project3/workflow.json](projects/ironhack_project3/workflow.json). It is sanitized and has no credential values or credential references; use the setup script to bind n8n credentials.

## Validation, errors and limitations

An exact company match is required. Ambiguous candidates stop before company research; the user can restart with an exact registered name or register number. Provider errors, non-completed model responses, invalid structured output and invalid source identifiers return stage-specific failures. Failed output is not presented as a completed report. Existing workflow request timeouts and duplicate/retry protections remain in place.

Registry records are provider-reported. Public-web findings are unverified leads, and source identity may not be independently established. Search coverage is limited. The automated validator checks source IDs and output structure, not the semantic truth of every sentence. A qualified reviewer must check the report and sources before relying on it. This is not a legal opinion, audit, sanctions clearance, solvency assessment or management-authority verification.

## Ironhack Project 3 deliverables

- [Workflow architecture](docs/architecture.mmd)
- [OpenRegister, Tavily, OpenAI and RAG notes](docs/tools.md)
- [Six-minute demo script](docs/demo_script.md)
- [Future GTM sprints](gtm_future_sprints.md)
- [Sample report: Urban Sports GmbH](examples/sample_report_1.md)
- [Sample report: someform Studio GmbH](examples/sample_report_2.md)
- [Deliverable status](docs/deliverables.md)

**Slides PDF:** outstanding. **Workflow screenshots:** outstanding; no authentic screenshots were available in this repository. **Demo recording:** outstanding; no recording URL is available yet.

## Repository map

~~~text
projects/ironhack_project3/  workflow builder, deploy/run helpers, prompts, RAG and sanitized export
examples/                    sanitized copies of two actual successful reports
tests/                       focused offline Project 3 and validation regression tests
docs/                        architecture, provider notes, demo script and deliverable status
gtm_future_sprints.md         three proposed future GTM sprints
~~~
