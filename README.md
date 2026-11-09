# LEGALFLOW
## Autonomous M&A Due Diligence & Corporate Risk Intelligence

LEGALFLOW is an AI-powered research agent designed to assist corporate lawyers and M&A teams with preliminary company due diligence.

### Industry
Legal Tech / Corporate Law

### Target Users
Corporate lawyers, M&A teams, and legal operations professionals.

### Problem
Preliminary corporate due diligence requires lawyers to collect and analyze information from multiple corporate registries, news sources, and public databases.

### Solution
LEGALFLOW automates public company research, identifies potential risk indicators, and generates structured reports with source references.

### MVP Scope
- UK-registered companies
- Publicly available corporate information
- Automated company and news research
- AI-assisted risk identification
- Structured preliminary due diligence reports
- Human review required for legal conclusions

### Primary Stack
n8n

n8n is well suited to LEGALFLOW because it allows the integration of multiple external data sources into a single automated workflow. Its visual orchestration simplifies API integration, branching logic, error handling, and report delivery. Compared with LangGraph, n8n offers a faster path to a working MVP and is particularly suitable for legal operations automation. LangGraph would provide more granular control over complex agent reasoning, but that level of customization is unnecessary for the initial five-day project.

### Planned Integrations
1. Companies House API — UK corporate records
2. Tavily API — Web research
3. GNews API — Recent news
4. OpenAI API — Analysis and synthesis
5. Pinecone — Retrieval-augmented generation

### Workflow
Trigger → Identify Company → Collect Research → Validate Sources → Retrieve Legal Context → Analyze Findings → Generate Report → Deliver Report

### Disclaimer
LEGALFLOW provides preliminary research assistance, not legal advice or a substitute for professional due diligence.
