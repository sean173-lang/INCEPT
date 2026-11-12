# API configuration

FastAPI loads the repository’s ignored `.env` when started through `scripts.http_service:app`. Existing process environment values take precedence. Do not place credentials in Gradio inputs, workflow exports, reports, or Git.

## Active routes

| Route | Purpose |
|---|---|
| `GET /health` | Service health |
| `POST /v1/onboarding/extract` | Source-exact extraction of a selected Gmail inquiry |
| `POST /v1/onboarding/payment-research/verify` | Verify official German statutory wording retrieved by n8n |
| `POST /v1/onboarding/synthesis` | Source-exact OpenAI Mandate Assessment |
| `POST /v1/onboarding/assessment` | Structured intake assessment for the separate document flow |
| `POST /v1/onboarding/preview` | Optional draft-document generation |

Company/UK classification, Companies House, registry research, corporate intelligence, generic research, usage and demo routes are not exposed by the active FastAPI app. Their archived code and execution history remain for audit.

## Private configuration

- `OPENAI_API_KEY`: existing application key; never returned by the API.
- `INCEPT_AI_MODEL`: `gpt-4o-mini`.
- `INCEPT_AI_LIVE_ENABLED`: defaults to enabled when the key is present; set to `0` only to intentionally disable live analysis.
- `INCEPT_AI_MAX_INPUT_TOKENS`: conservative input bound.
- `INCEPT_AI_MAX_OUTPUT_TOKENS`: provider output ceiling.
- `INCEPT_AI_TIMEOUT_SECONDS`: bounded request timeout.
- `LEGALFLOW_SERVICE_TOKEN`: required for service-to-service authentication when live AI is configured.

n8n sends the service key in `X-LEGALFLOW-Service-Key`; FastAPI compares it without logging or echoing it. Gradio does not receive the key.

The app does not require billing verification, an admin approval ID, a zero-dollar budget, or per-test financial approval. It retains input/output bounds, timeout, concurrency behavior, duplicate-request protection, prompt-injection defenses, source provenance and lawyer-review validation. Failed or uncertain calls are not retried automatically. Usage is reported only when supplied by OpenAI; no dollar amount is inferred.

No organization billing setting is modified by this repository. API charges follow the account’s existing OpenAI billing configuration.
