# CompanyScope — six-minute demo

This timing includes the live demo. Avoid opening credential values. Use the current active n8n workflow and the production form; do not use the editor test-form URL.

## 0:00–0:40 — Problem and audience

Explain that law firms, corporate legal teams and business research professionals spend time assembling basic company context before meetings and counterparty reviews. CompanyScope creates a bounded, source-referenced starting briefing; it is not a legal opinion.

## 0:40–1:20 — Architecture and stack

Show the architecture diagram, then the existing n8n graph. Explain why n8n fits a short, visible workflow with explicit identity and provider failure branches. Point out OpenRegister, Tavily, local RAG, OpenAI Structured Outputs, validation and report rendering.

## 1:20–2:00 — Submit a company

Open the local production form (requires n8n sign-in), enter a company name and optionally a register number, and submit. Explain that an ambiguous identity stops for user input rather than selecting a similar legal entity. This live step may consume provider usage.

## 2:00–3:00 — Follow the execution

Show the execution using the same stable workflow ID. Highlight exact registry matching, filtered Tavily results, RAG methodology cards, completed model response and source-ID validation. Clarify that RAG is not company evidence and web material is unverified.

## 3:00–4:30 — Review the report page

Show the completion page and one report section. Open a source link. Distinguish registry facts, web leads and analytical inferences. Point out that long source URLs are linked from readable titles and that the original Markdown is saved separately.

## 4:30–5:20 — Failure handling

Use a saved missing-company execution or explain the error branch. Show that no report is labeled complete when identity, provider response or validation fails. Do not trigger an extra research run just to demonstrate an error.

## 5:20–6:00 — Limitations and next steps

State that web search is incomplete, source claims require human verification, and the output is not a legal opinion or compliance clearance. Close with the three proposed GTM sprints: supervised firm pilot, reliability/workflow fit, then market testing.
