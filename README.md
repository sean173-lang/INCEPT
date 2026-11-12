# INCEPT — German Legal Intake

INCEPT analyzes a selected Gmail inquiry as a preliminary German-law mandate assessment for lawyer review.

```text
Gmail → Gradio → n8n → FastAPI → official German legal sources → OpenAI → source-validated assessment
```

The intake records client name, contact email, optional address, optional counterparty, the original inquiry, any facts extracted from it, and requested assistance. Missing information stays missing. Company names are plain text; no company classification or jurisdiction-routing step is required.

## Run the workspace

Configure the existing `.env` values for Gmail/n8n, `LEGALFLOW_SERVICE_TOKEN`, `OPENAI_API_KEY`, and `INCEPT_AI_MODEL=gpt-4o-mini`. The FastAPI service loads this file without returning credentials from its API.

Start the helper and UI in separate terminals:

```sh
python -m uvicorn scripts.http_service:app --host 127.0.0.1 --port 8003 --no-access-log
python -m scripts.gradio_app
```

Open `http://127.0.0.1:7860`, refresh the inbox, select a message, authorize processing, and click **Analyze**. The UI displays the current model, n8n execution ID, whether OpenAI ran, and whether source-exact validation passed. A rejected analysis is shown as an error; the old deterministic payment report is not substituted.

Optional German legal-document drafts use a separate action. Reply preparation and email sending are separate; sending still requires a reviewable preview and explicit confirmation. Duplicate-send protection remains enabled.

## Active service surface

- `POST /v1/onboarding/extract` extracts exact source spans from the selected inquiry.
- `POST /v1/onboarding/payment-research/verify` verifies retrieved official German statutory wording.
- `POST /v1/onboarding/synthesis` calls the Responses API using `gpt-4o-mini` and validates the source-exact assessment.
- `POST /v1/onboarding/preview` and `/assessment` support the separately requested optional document workflow.

All n8n calls to FastAPI use `X-LEGALFLOW-Service-Key`. API keys are never sent to Gradio. AI request timeouts, duplicate-request protection, source provenance, factual excerpt checks, prompt-injection checks, lawyer-review requirements, and send/document approval safeguards remain enabled.

## Scope and evidence

The active intake path does not expose Companies House, UK/German company classification, company registry lookup, corporate intelligence, or demo fallback routes. Historical modules, fixtures, and execution traces remain in the repository for audit; they are not part of the active intake path.

See [workspace operations](docs/gmail_workspace.md), [API configuration](docs/api_usage.md), and [document-generation boundary](docs/legal_document_generation.md). Historical demo and corporate documents are retained as archive material and may describe retired behavior.
