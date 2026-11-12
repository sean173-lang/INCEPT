# German legal assessment synthesis

The active INCEPT Analyze path sends the selected inquiry and server-verified official German statutory excerpts to the OpenAI Responses API with `gpt-4o-mini`. It produces a preliminary German Mandate Assessment for lawyer review.

## Model contract

The request contains a minimized evidence packet: case identity, exact intake excerpts, verified statutory excerpts, source provenance, and review limitations. For each substantive legal analysis item, the structured output requires separate selections for one official legal excerpt and one exact excerpt from the selected inquiry. The server supplies those source IDs and quotes; the model cannot invent them. The selected excerpt IDs are enumerated in the request schema, and each field is checked against the excerpt’s role.

The server retains factual-span membership, client/counterparty identity, source provenance and citation checks, prompt-injection checks, conditional-law wording, unsupported-number/deadline checks, adverse-evidence checks, and lawyer-review/action-state controls. A source or citation match proves attribution, not legal correctness or semantic entailment. A lawyer must review the preliminary assessment.

If an official statute is retrieved, a substantive conditional analysis is required. If no relevant statute is available, no legal rule is invented. When governing law is unconfirmed, the analysis must condition its application on German law applying.

## Runtime and privacy

`OPENAI_API_KEY` and `INCEPT_AI_MODEL=gpt-4o-mini` are read by FastAPI from the existing private environment. n8n authenticates to FastAPI with `X-LEGALFLOW-Service-Key`. The browser does not receive either key.

The application does not require billing-verification flags, an approval ID, a zero-dollar budget, or a per-test financial approval. Request-size bounds, output limits, timeouts, duplicate-request protection, and validation remain. The ledger prevents automatic retries after failed or uncertain calls. The application does not change organization billing settings, purchase credits, or configure auto-recharge.

Model usage is returned when the provider supplies it. No actual cost is inferred from token counts. A rejected response is shown as a sanitized failure; the application does not substitute the retired deterministic payment-dispute report.

## Separate actions

AI assessment does not generate legal documents, send email, issue invoices, or accept a mandate. Optional document drafts remain a separate lawyer-review action. Gmail replies require preview and explicit confirmation; duplicate-send protection remains active.
