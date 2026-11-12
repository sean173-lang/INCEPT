# Gmail workspace operations

## Start the services

Use the configured `.env` and the existing authenticated n8n instance. Start FastAPI and Gradio in separate terminals:

```sh
python -m uvicorn scripts.http_service:app --host 127.0.0.1 --port 8003 --no-access-log
python -m scripts.gradio_app
```

Open `http://127.0.0.1:7860`. n8n must have its existing Gmail OAuth reference and `LEGALFLOW_SERVICE_TOKEN` binding to FastAPI. Secrets stay in the server environment and n8n credential store; they are never entered in Gradio.

## Analyze a selected message

1. Refresh Gmail and select the exact inquiry.
2. Review the original message and authorize sending that inquiry to the configured AI provider.
3. Click **Analyze**.

The active path is selected-message read → exact-span extraction → official German source retrieval when relevant → `POST /v1/onboarding/synthesis` → server validation → Gradio assessment. The synthesis uses the OpenAI Responses API and `gpt-4o-mini`. The report stays tied to the selected message and is not replaced with a fixture or deterministic payment report.

The final status identifies the n8n execution ID, model, whether OpenAI was called, and whether source-exact validation passed. If validation fails, Gradio shows the sanitized reason and the failed field. No assessment is called functional unless the selected message is confirmed and the live synthesis is accepted.

## Intake and safeguards

The single intake has client name, contact email, optional address and counterparty, original inquiry text, exact extracted facts/dates/amounts/documents, and requested assistance. Blank fields remain unknown. Company names are plain text.

Analyze does not generate documents or send email. Optional document generation is a separate action and returns lawyer-review drafts only. Reply drafting is separate; sending requires an exact preview and explicit confirmation. Duplicate-send protection remains active.

## Current API surface

- `POST /v1/onboarding/extract` — extracts selected-message facts as exact spans.
- `POST /v1/onboarding/payment-research/verify` — verifies official statutory source wording for the current German-law retrieval workflow.
- `POST /v1/onboarding/synthesis` — OpenAI source-exact assessment.
- `POST /v1/onboarding/assessment` and `/preview` — separate optional document processing.

Company classification, Companies House, UK routing, registry research and demo fallback are not active endpoints or Analyze branches. Archived workflows and execution traces remain for historical evidence.
