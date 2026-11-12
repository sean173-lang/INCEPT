# Tool and validation notes

## OpenRegister

- `GET https://api.openregister.de/v1/autocomplete/company?query=…`
- `GET https://api.openregister.de/v1/company/{company_id}?export=true` (omits signed source-document links from workflow data)
- Auth: n8n `httpHeaderAuth` credential with an `Authorization: Bearer …` value restricted to `api.openregister.de`.
- Identity selection requires a unique exact normalized legal name or a matching register number/company ID. It does not choose a fuzzy name result.
- The details node retains legal form, register, address, purpose, status and a workflow retrieval timestamp. Missing values render as “Not returned.”

## Tavily

- `POST https://api.tavily.com/search`
- Advanced search, maximum eight results, answer/raw-content/image retrieval disabled, automatic parameter expansion disabled, timeout 30 seconds, no redirects/retries.
- Search results must contain an HTTP(S) URL, title and content. Unsafe credential-bearing URLs are excluded. Each accepted result receives a UTC retrieval timestamp and any provider publication date.
- Search excerpts are labeled unverified public web leads.

## OpenAI

- `POST https://api.openai.com/v1/responses`
- Model: `gpt-4o-mini`; output is strict JSON Schema; `store:false`; maximum 3,500 output tokens; timeout 60 seconds; no retries.
- A non-completed response is rejected. The model selects existing source IDs and writes neutral questions; the workflow renders facts directly from source content.
- The validator rejects unknown IDs, malformed output, and malformed uncertainty/follow-up questions. Company profile fields and factual excerpts are source-derived, not model-invented; quoted passages are capped at 600 characters for readability.

## RAG

`reference_corpus.json` has four short cards for identity matching, source quality, due-diligence meeting preparation, and scope limits. A keyword-overlap retriever selects up to three cards. The workflow passes these as methodology context only; company facts can only come from OpenRegister and Tavily data.

## Failure handling

Provider request nodes have retries disabled and route to step-specific error responses. No exact registry match and ambiguous identities stop before details/search/synthesis. A Tavily empty result list can continue as a partial registry-only report; a malformed provider response fails. OpenAI incomplete/failed/refused responses are not accepted. No mock result is used in live execution.
