# 6-minute live demo script

This script is designed for a live run. The two saved reports provide backup evidence if provider access is unavailable during the presentation. Do not claim a live rerun unless it actually succeeds.

## 0:00–0:40 — Problem and user

“Corporate lawyers preparing an initial client or counterparty meeting often gather registry and public-web information manually. INCEPT gives them a short, cited starting briefing. It is public-source research, not a legal opinion.”

## 0:40–1:20 — Architecture and stack

Show the architecture diagram and one active n8n workflow. Explain that n8n is the primary orchestration framework because the workflow is a visible, sequential set of tools and explicit failure branches. Point out that all requests reuse the same workflow ID.

## 1:20–2:00 — Start a research run

Run the documented command for **SAP SE** with register identifier `HRB 719915`. Show the authenticated webhook invocation and the OpenRegister exact-identity check. Do not show any API credential screen or `.env` values.

## 2:00–3:00 — Follow the research path

In the n8n execution, point to OpenRegister search/details, Tavily Search, local RAG retrieval, OpenAI Structured Synthesis, and source validation/report rendering. Explain that RAG provides methodology, not company facts, and Tavily results are labeled unverified leads.

## 3:00–4:00 — Read the first report

Open the SAP report. Show the register ID, court, legal form, registered address and purpose excerpt. Show a public-web excerpt with its source ID, URL and retrieval time. Point out the model and execution metadata.

## 4:00–5:00 — Repeat for a different company

Run **Siemens Healthineers AG** with `HRB 237558`. Show that execution 273 uses the same workflow ID as execution 272 and that the report contains Siemens Healthineers identity and medical-technology purpose, not SAP facts.

## 5:00–5:40 — Validation and failure handling

Show the report metadata and exact-source excerpts. Mention the missing-company test: execution 274 returned `exact_company_match_not_found` and stopped before Tavily and OpenAI. There are no mock results in the live path.

## 5:40–6:15 — Limitations and next steps

Explain that public search is not exhaustive, web snippets remain unverified leads, and the briefing is not a legal opinion or compliance check. Close with the proposed three GTM sprints: supervised pilot, reliability improvements, then market testing.
