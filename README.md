# LEGALFLOW

### AI-Powered Corporate Due Diligence | Germany & United Kingdom

[![Python](https://img.shields.io/badge/Python-3.x-blue)](https://www.python.org/)
![Status](https://img.shields.io/badge/status-working%20prototype-orange)
![Jurisdictions](https://img.shields.io/badge/jurisdictions-Germany%20%7C%20UK-blue)

**LEGALFLOW** is a Python-based legal research prototype that combines corporate register information, public web research, and AI-assisted analysis to generate preliminary company due diligence reports.

It is designed for corporate lawyers, M&A teams, and legal operations professionals who need an initial, source-aware overview of a company before conducting a full legal review.

> **Project status (9 November 2026):** Four API integrations have been tested, and an end-to-end German company research report has been generated. The application remains a prototype: independent evidence verification, a web interface, and n8n orchestration are not yet implemented.

## The Problem

Early-stage corporate due diligence often involves moving between commercial registers, corporate filings, public websites, and news sources. Manually collecting and reconciling these records is time-consuming. Search results can also refer to similarly named but legally distinct companies, and historical information can easily be mistaken for current information.

## What LEGALFLOW Does Today

- Searches the **UK Companies House** register by company name and retrieves company profiles, officers, and recent filing metadata.
- Retrieves **German company records via OpenRegister** using an OpenRegister company ID, including available management, registration, capital, and historical-name data.
- Uses **Tavily** to search for potentially relevant litigation, insolvency, regulatory, and other public information.
- Uses **OpenAI** to synthesize retrieved information into a preliminary Markdown due diligence report.
- Saves generated reports locally in the `reports/` directory.

The current pipeline executes a predefined sequence of API calls. It is **not yet a fully autonomous agent** with dynamic tool selection or independently verified legal conclusions.

## API Integrations

| Integration | Purpose | Current status |
| --- | --- | --- |
| **Companies House REST API** | Official UK company profiles, officers, and filing metadata | ✅ Integrated and tested |
| **OpenRegister API** | German company-register information and available corporate history | ✅ Integrated and tested |
| **Tavily Search API** | Public web research and potential risk leads | ✅ Integrated and tested |
| **OpenAI API** | AI-assisted synthesis and Markdown report generation | ✅ Integrated and tested |

**Not integrated:** GNews. **Optional future enhancement:** Pinecone for retrieval-augmented document analysis.

## Current Workflow

```text
User selects jurisdiction
          |
          v
Company identification
   |                |
   v                v
UK: Companies     DE: OpenRegister
House             (company ID)
   |                |
   +-------+--------+
           |
           v
     Tavily search
           |
           v
     OpenAI analysis
           |
           v
 Preliminary Markdown report
           |
           v
       reports/
```

**Important:** An evidence verification layer is planned, but it is **not currently an implemented stage** of this workflow.

## Project Structure

```text
legalflow/
├── scripts/
│   ├── companies_house.py   # UK register integration
│   ├── german_register.py   # OpenRegister integration
│   ├── company_research.py  # Tavily research
│   └── legalflow_agent.py   # End-to-end CLI workflow and AI report
├── .env.example             # Example API key configuration
├── .gitignore
└── README.md
```

The application creates `reports/` locally when saving a generated report. Additional local folders may exist without being tracked in Git.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/sean173-lang/legalflow.git
cd legalflow
```

### 2. Set up Python

Use Python 3 and a virtual environment (or an existing Conda environment):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install the dependencies used by the current scripts:

```bash
python -m pip install requests python-dotenv openregister-sdk tavily-python openai
```

### 3. Configure API credentials

Copy the example environment file:

```bash
cp .env.example .env
```

Set the following variables in `.env`:

```dotenv
COMPANIES_HOUSE_API_KEY=your_companies_house_key
OPENREGISTER_API_KEY=your_openregister_key
TAVILY_API_KEY=your_tavily_key
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4o-mini
```

`OPENAI_MODEL` is optional; the script defaults to `gpt-4o-mini`.

**Never commit API keys.** The repository's `.gitignore` excludes `.env`. Access to external APIs may consume credits or incur costs.

### 4. Run LEGALFLOW

Run the main application **from the repository root**:

```bash
python -m scripts.legalflow_agent
```

Choose a jurisdiction:

- **United Kingdom:** enter a company name, then select a matching company if prompted.
- **Germany:** enter an **OpenRegister company ID** (German name-based search is not yet implemented).

For a German integration test, the project has used the OpenRegister example ID:

```text
DE-HRB-F1103-267645
```

The report is printed in the terminal and saved as a timestamped Markdown file under `reports/`.

### 5. Run individual integrations (optional)

```bash
python scripts/companies_house.py
python scripts/german_register.py
python scripts/company_research.py
```

## Validation and Limitations

LEGALFLOW currently produces **preliminary research**, not verified legal due diligence. In particular:

- Tavily search snippets are **research leads**, not proof of allegations, sanctions, or current litigation.
- Similar company names can produce **incorrect entity matches**; external sources are not yet systematically verified against register identifiers.
- Source URLs in AI-generated reports are **not yet independently checked claim by claim**.
- The model can misstate dates, confuse entities, or assign an unjustifiably confident risk rating.
- A missing negative search result does **not** establish that a company is low risk.
- The current workflow does not retrieve and examine every underlying filing or shareholder document.
- The CLI does not yet provide a full financial, beneficial-ownership, sanctions, or insolvency assessment.

**Do not rely on generated risk ratings without human review and validation against authoritative sources.** Where material evidence is unavailable, the appropriate result may be **Undetermined**.

## Development Roadmap

| Feature | Status |
| --- | --- |
| UK Companies House integration | ✅ Complete for prototype |
| German OpenRegister integration | ✅ Complete for ID-based lookup |
| Tavily public web search | ✅ Complete for prototype |
| OpenAI report generation | ✅ Working prototype |
| Integrated command-line workflow | ✅ Working prototype |
| Evidence verification and entity matching | 🔜 Next priority |
| Claim-level source attribution and date checking | 🔜 Planned |
| Automated tests with mocked API responses | 🔜 Planned |
| German company search by name | 🔜 Planned |
| Gradio web interface | 🔜 Planned |
| n8n workflow orchestration and agent behavior | 🔜 Planned |
| PDF report export | 🔜 Planned |
| Pinecone-based document RAG | 💡 Optional |

## Tech Stack

- **Python** — Current application and API integrations
- **Requests** — Companies House HTTP requests
- **OpenRegister Python SDK** — German company records
- **Tavily Python SDK** — External research
- **OpenAI Python SDK** — AI report generation
- **python-dotenv** — Local environment configuration
- **Git / GitHub** — Version control
- **Codex** — Planned assistance for implementation and tests
- **Gradio / n8n** — Planned interface and workflow orchestration

## Intended Audience

Corporate lawyers, M&A professionals, compliance researchers, and legal operations teams evaluating a **preliminary** company research workflow.

## Disclaimer

LEGALFLOW is an educational and experimental legal technology project. Its output is not legal advice, a legal opinion, a certified corporate investigation, or a substitute for professional due diligence. Information may be incomplete, outdated, or inaccurate. A qualified reviewer must verify material findings against reliable primary sources before acting on them.

### Legal evidence verification

`scripts/evidence_validator.py` runs offline before the AI analysis. Registry
adapters retain original API responses so normalized identity, incorporation,
UK officer appointment, and filing dates can be checked against their source.
German provider IDs are checked separately from legal registration numbers and
register courts. Web results receive identity, hostname provenance, publication
age, and unverified allegation/litigation annotations. Conflicting identities,
invalid URLs, future publication dates, and empty excerpts are excluded from
analysis. Missing and outdated dates remain explicit verification gaps.

The current registry-and-search workflow yields **Undetermined** overall risk:
absence of adverse search results does not establish low risk. Reports are rendered deterministically from validation results, with one final
risk assessment and readable evidence gaps. OpenAI prioritizes an allowlisted
set of follow-up investigations; model-written conclusions are not published. Host classification does not authenticate page content;
search excerpts cannot verify court findings, sanctions, or whether litigation
is ongoing. Publication dates are not event dates. The default freshness window
is 365 days and can be configured through `validate_evidence(max_age_days=...)`.
Name and registration comparisons are conservative heuristics, not independent
identity certification. Additional original legal documents and verified search
coverage are required before implementing stronger risk classifications.

Run the offline mocked test suite without API credits:

```sh
python -m unittest discover -s tests -v
```

Register references include the legal registration number, register authority,
provider identifier, and recorded retrieval timestamp. German records identify
OpenRegister separately as the data provider. No register document URLs are
constructed. Older inputs without retrieval metadata explicitly say it is not
available; analysis time is never substituted. Technical evidence-gap codes
remain in structured validation output and are translated only for display.
Malformed or conflicting model output falls back to the default investigation
order and cannot alter report findings, sources, or the final risk category.

### Phase 1: financial and transaction due diligence

The existing UK/German pipeline now produces corporate structure, financial
analysis, legal and regulatory findings, evidence-linked issues, document
requests, transaction considerations, and sources/limitations. Financial
indicators and missing information are distinguished from verified legal
findings. Overall coverage remains incomplete and the deterministic final
classification remains authoritative. OpenAI only prioritizes approved
follow-up actions; it cannot invent report figures or legal conclusions.

Financial retrieval is **off by default**. No financial or document API calls
were made during implementation or testing. Normal research still uses the
existing register, Tavily and OpenAI integrations and their usual charges.

```sh
# Existing workflow, no additional financial retrieval:
python -m scripts.legalflow_agent

# Explicit opt-in: Germany costs 10 OpenRegister credits for financials;
# UK retrieves one page containing at most five accounts filings:
python -m scripts.legalflow_agent --financials

# UK only: additionally retrieve at most one document, maximum 5 MB:
python -m scripts.legalflow_agent --financials --download-accounts

# Offline tests:
python -m unittest discover -s tests -v
```

German financial retrieval prefers `client.company.get_financials_v1` if the
installed SDK supports it; otherwise it uses the documented Bearer-authenticated
REST endpoint. The active development interpreter has no OpenRegister SDK.
The SDK can be installed separately as `openregister-sdk`; existing company
lookup still uses the SDK as before. The financial adapter disables automatic
SDK retries and never falls back after an SDK request failure, avoiding repeat
credit consumption. Missing data, access errors and quota failures are recorded
as unavailable, not interpreted as adverse findings.

OpenRegister indicators are joined to report dates and consolidation scope by
report ID. Provider estimates are excluded. Revenue, earnings, assets, equity,
liabilities, cash and other supported figures are retained when returned.
Currency and scale must be explicitly supplied: the published financial schema
does not currently document these fields, so ordinary responses can show
reported numbers with unknown units while monetary calculations remain
unavailable. Do not silently label these figures as EUR or infer units from
registered capital. Underlying report references are retained when supplied.

UK retrieval uses an accounts-category filing-history query, the returned
`document_metadata` link, advertised resource formats, and the official Document
API. One bounded stream is downloaded only with `--download-accounts`. Storage
redirects receive no Companies House credentials. Document bytes are returned in
`financial_data.document_content` for programmatic callers, not sent to OpenAI
or automatically saved to disk. Reports retain document references. PDF-only,
ZIP, malformed HTML, unsupported taxonomies/transforms, conflicting facts and
unmatched entity contexts require manual extraction; no OCR/LLM guessing occurs.
The extractor supports a limited exact UK GAAP/FRC concept and namespace list.
Unresolved XBRL dimensions/scope block comparisons across periods.

The financial analyzer uses Decimal arithmetic. Ratios are equity/assets,
liabilities/assets, current assets/current liabilities and net income/revenue.
Each calculation retains its formula and explicit unavailable reason. Zero or
negative denominators, invalid dates and incompatible or missing units block
calculations. Comparable periods require known matching scope and similar,
non-overlapping durations; short years and duplicate/restated periods block
trend calculations. Absolute changes use normalized currency units; percentages
require a positive base. Negative equity, losses, liquidity ratios below one
and declines are review triggers, not findings of insolvency or wrongdoing.
Accounting policy changes and audit opinions still require professional review.

Each issue includes a description, supporting evidence, source, potential legal
significance, recommended follow-up action and verification status. Document
requests cover signed accounts, management information, funding, security,
ownership and legal records. Transaction considerations are conditional review
prompts rather than transaction-specific legal advice.

API documentation checked on 2026-11-09 (documentation only, no authenticated calls):

- [OpenRegister financial endpoint and SDK example](https://docs.openregister.de/endpoint/company-financials)
- [OpenRegister credit pricing](https://docs.openregister.de/pricing): financials cost 10 credits; published Pro overage is EUR 0.01/credit (EUR 0.10 per financial request at that rate). Account entitlement and actual billing were not queried.
- [OpenRegister authentication](https://docs.openregister.de/authentication)
- [OpenRegister financial coverage](https://docs.openregister.de/sources/bundesanzeiger): availability depends on published company accounts.
- [Companies House filing history](https://developer-specs.company-information.service.gov.uk/companies-house-public-data-api/reference/filing-history/list)
- [Document API metadata and retrieval](https://developer-specs.company-information.service.gov.uk/document-api/reference)
- [Companies House free public API data](https://www.gov.uk/guidance/searching-the-companies-house-register)

Limits: no company-specific financial availability has been confirmed live;
small-company/abridged accounts can omit profit and loss figures. One filing
page is not complete history, and retrieving one UK document does not guarantee
multiple comparable periods. Unknown units, scope and dates remain explicit.
The current report cannot establish comprehensive legal or financial clearance.

### Diagnosing OpenRegister financial failures

Financial failures now print a fixed, credential-safe terminal diagnostic and
return `error_code`, `http_status`, `failure_stage`, `transport` (when selected),
and `plan_access`. Exception text, HTTP response bodies, headers, redirect URLs
and API credentials are never printed by the financial adapter. No automatic
retry or REST fallback follows an SDK request failure.

Diagnostics distinguish authentication (401), permissions/possible entitlement
(403), missing company/resource or ambiguous route (404), quota/rate limiting
(429), billing/credits (402), invalid operations, provider errors, network
failures/timeouts, SDK incompatibility and unsupported JSON/schema responses.
An explicit route-not-found machine code can identify an invalid endpoint;
an ordinary 404 cannot establish either an invalid route or absence of filings.
A successful empty financial response is recorded separately from a failed
request and does not prove that no statements exist.

The prior generic message discarded exception details, so the cause of the
2026-11-09 Descartes failure cannot be recovered from its report. The documented
SDK accepts `get_financials_v1(company_id=...)`, and REST uses
`GET /v1/company/{company_id}/financials` with Bearer authentication. The active
development interpreter has no installed SDK, so it cannot establish which SDK
version the live test used. Account plan access has not been verified; public
pricing lists the endpoint at 10 credits, but does not establish entitlement for
a particular API key. A dedicated single financial request after explicit user
approval is required to confirm the live outcome. Do not rerun the whole
research workflow merely to diagnose this endpoint: that would incur additional
register, research and model calls.

### Interpreting financial 404 responses and choosing a positive control

Financial 404 classification now uses `scripts/financial_errors.py` for both
REST responses and SDK exception bodies (or the SDK's already-received response).
It distinguishes an explicitly missing company, missing financial dataset,
missing route/endpoint, and unknown cause. Specific code/message compatibility
aliases are matched exactly in recognized JSON envelope fields. Generic `404`,
`Not Found`, unrecognized text, malformed bodies and conflicting signals do not
establish a cause. Provider text and unknown codes are never printed verbatim.

The public [financial endpoint reference](https://docs.openregister.de/endpoint/company-financials)
reviewed on 2026-11-09 provides the success schema but no exhaustive 404 code or
message catalogue. The classifier's explicit aliases are conservative
compatibility rules tested with synthetic fixtures, not documented guarantees
about provider error vocabulary. Extend them when verified provider responses
or further official documentation establish new precise meanings.

Structured financial data and report output keep these independent dimensions:

- API request outcome (`request_status`): failed versus succeeded.
- Provider data availability (`financial_data_status`): unknown, explicitly unavailable through provider, figures returned, or no figures returned by a successful response.
- Independent publication status (`publication_status`): unknown in this API workflow. Neither a provider 404 nor an empty successful response proves that no figures were published.
- Specific 404 cause and classification basis: preserved through financial analysis.

The existing Descartes 404 report did not retain a specific provider error body,
so its cause remains unknown. A provider coverage gap is a plausible hypothesis
given the successful company profile lookup, but the current evidence cannot
exclude identifier or routing issues. It does not establish missing filings.
Do not rerun authenticated requests without separate explicit approval.

Volkswagen AG is a suitable *candidate* positive control because it publishes
annual financial statements and identifies itself as HRB 100484 at the
Braunschweig Local Court, domiciled in Wolfsburg. See its own
[2025 annual-report basis of presentation](https://annualreport2025.volkswagen-group.com/notes/basis-of-presentation.html)
and [standalone 2025 accounts](https://www.volkswagen-group.com/en/publications/more/annual-financial-statements-of-volkswagen-aktiengesellschaft-as-at-31-12-2025-3214/download?disposition=attachment).
Group IFRS statements and parent-company HGB accounts must remain distinct;
group figures use EUR millions in the cited presentation. Do not transfer those
units to API indicators without confirming their representation. OpenRegister
coverage and the correct provider company ID have not been verified; do not
construct an ID from the HRB number.

Recommended live verification, separately approved in advance: resolve or reuse
a verified OpenRegister ID for Volkswagen AG, then issue one financial request
without retries and inspect only safe error classifications, status, field
names/counts, and parser compatibility. Financial requests are documented at
10 credits each; any ID search/details requests require separate authorization
and their own credit allowance. Compare a positive control with Descartes only
after authorization, rather than assuming both have equal provider coverage.

Tavily research now performs one bounded exact-name query, including the legal
registration number and register court when supplied, plus jurisdiction and a
single legal topic. The OpenRegister provider ID is not substituted for a legal
registration number. Query and coverage notes are retained in structured results.
No risk-keyword OR chain or extra paid searches are added. The evidence validator
continues to exclude unrelated sources. A single narrow query can miss relevant
material and is not comprehensive sanctions, insolvency or litigation screening.

### API usage monitoring and cost protection

The central usage tracker now protects OpenRegister, Tavily, OpenAI and Companies
House operations. Search, company details and Tavily results use an expiring cache;
the existing financial cache is preserved. Use `--dev` for synthetic responses
without external calls, and `--approve-api` to authorize live paid cache misses.
Hard credit/search limits cannot be overridden by approval. Monetary prices are
unknown unless reliable per-operation upper bounds are configured; finite money
caps block unknown-cost calls. Estimates are never presented as confirmed billing.

See [configuration, CLI examples, ledger format and limitations](docs/api_usage.md).
Run the complete offline suite with `python -m unittest discover -s tests -v`.
Tests use temporary cache directories and block socket connections.
