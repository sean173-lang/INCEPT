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
