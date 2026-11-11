# Tavily Search dependency and safeguards

Execution 26's temporary FastAPI helper used `/opt/anaconda3/bin/python`. The configured key was present, but `tavily-python` was not installed. It was already declared without a version in `requirements-service.txt`; this was an environment/dependency installation gap, not evidence of rejected credentials or a failed Tavily API request.

SDK 0.8.5 is now installed in that interpreter and the requirement is bounded to `>=0.8.5,<0.9`. Reproduce installation using the interpreter that actually runs FastAPI:

```sh
python -m pip install -r requirements-service.txt
python -m unittest discover -s tests -q
```

The existing adapter remains `scripts/company_research.py`. It uses only basic Search, an explicit 20-second timeout, no automatic parameter escalation, no generated answer/raw-content/image retrieval, a transport with zero retries and zero allowed redirects, and a validated one-to-five result bound. The controlled live test uses three. Existing default query/cache identities remain compatible. Usage reservations and cache protections remain in the existing tracker.

Response parsing records UTC retrieval time separately from optional publication date, bounds returned rows, excludes unsafe/credential-bearing source URLs, and retains provider-reported credit usage without calling it confirmed billing. Web search excerpts remain unverified leads. The corporate helper excludes unusable/unrelated results and keeps registry findings when optional research fails; it never promotes snippets to verified legal findings.

Tests mock the SDK/transport and cover dependency import, Search parameters, response parsing, timestamps, unsafe URLs, malformed responses, duplicate/failure handling, zero-spend limits, report attribution and nonblocking failure. They consume no API credits.

Basic Search costs one API credit according to [Tavily's official credit documentation](https://docs.tavily.com/documentation/api-credits). A configured key does not establish available free quota or whether overage billing is enabled. Under a no-additional-payment instruction, an unknown monetary price with a finite zero-spending cap must fail closed. No upgrade, purchase or paid overage is authorized.

A live request/result must be documented separately after the payment and credit conditions have been established. Installing the SDK and passing mocked tests do not establish live connectivity or live report findings. No permanent n8n workflow activation or credential change is needed.


## Billing gate and actual controlled validation

The initial read-only usage check confirmed the Researcher plan and 995 included credits, but did not expose billing-enabled/top-up settings. Search remained blocked until the user personally confirmed that no payment information or paid billing was enabled and explicitly authorized exactly one included-credit Basic Search. The permission record distinguishes that user confirmation from independently verified usage metadata. No billing settings were changed.

The single authorized Search returned **HTTP 200**, **three results**, and provider-reported usage of **one credit**. No retry or Research request occurred. Subsequent read-only usage metadata still reported 995 credits remaining and zero pay-as-you-go usage. The report records both values; it does not claim billing reconciliation or silently replace the observed balance with 994.

The actual normalized response was passed through the existing CompanyService research path, deterministic evidence validator, corporate schemas and existing n8n report-assembly Code node executed locally. All three source URLs render in the Corporate Counterparty Intelligence section, with retrieval timestamps, unknown publication freshness, official/third-party source classification and UNVERIFIED search-lead labels. The live integration check found and fixed escaped underscores in report URLs. Source URLs now remain intact in safe Markdown links.

Companies House information is explicitly CACHED from execution 26; no new registry lookup occurred. The court-document lead may concern a Tesco subsidiary rather than the researched legal entity; it establishes no current case status or liability. No UK legal conclusion is verified from these snippets.

See [sanitized live evidence](tavily_live_validation.json). Actual private response and report artifacts remain under ignored `data/incept_tavily_repair/` and `reports/incept_tavily_repair/`. No private Gmail message, credential, raw trace or client record is published.

**295 offline tests pass.** There was no new n8n execution, Gmail read/send, client/matter creation, external action or financial endpoint invocation. The report reuses the existing execution-26 bundle without modifying its evidence. Original workflows remain unchanged.

The optional `max_search_results` corporate-request field and `max_results` research-request field forward a one-to-five result bound without enabling provider calls from the cache-only corporate service. The controlled request used three. Existing FastAPI processes were not restarted; start/reload a controlled helper to use the updated code in future tests. Gradio remains a separate next milestone.
