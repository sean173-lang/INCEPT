# CompanyScope — Project 3 submission checklist

| Requirement | Evidence in this project | Status |
|---|---|---|
| 1. Industry, target user and problem | README: CompanyScope for German legal services, lawyers preparing corporate meetings, manual public-source research burden | Implemented |
| 2. One primary orchestration framework | One n8n workflow; no LangGraph or second runtime orchestrator | Implemented and activated locally |
| 3. Trigger → research → synthesis → report | Authenticated webhook; registry, web and RAG nodes; OpenAI; validation and Markdown response | Executed |
| 4. Three real external APIs/tools | OpenRegister, Tavily Search and OpenAI Responses API; real run evidence and metadata | Verified in executions 272 and 273 |
| 5. RAG where useful | Four-card local methodology corpus, keyword-overlap retrieval, context separated from company evidence | Executed |
| 6. Error handling and tool validation | Stage-specific provider errors; exact identity selection; source ID validation; incomplete response rejection | Executed; missing company test 274 |
| 7. Two reports actually generated | `reports/20261112T080627Z-sap-se.md`; `reports/20261112T080643Z-siemens-healthineers-ag.md` | Complete |
| 8. GitHub repository and reproducible instructions | Isolated CompanyScope README, requirements, setup/deploy/run commands; feature branch checkpointed | Feature branch pushed to origin |
| 9. Primary-stack justification | README explains n8n’s visible tool orchestration and why LangGraph is unnecessary here | Complete |
| 10. Two or three future GTM sprints | Three proposed sprints with goals, buyer, channel, deliverable and measurable targets | Complete; no experiments claimed |
| 11. Architecture diagram and tool documentation | `architecture.mmd`, README architecture, `tools.md` | Complete |
| 12. 5–7 minute demo | Timed 6-minute live demo script in `demo_script.md`; current n8n workflow and saved reports support the walkthrough | Prepared; recording not created |

## Final checks

- [x] Same workflow ID used for both accepted company reports.
- [x] Model response status recorded as completed for both reports.
- [x] Source validation passed for both reports.
- [x] Missing exact identity returned a stage-specific failure without reaching Tavily or OpenAI.
- [x] Sanitized workflow export contains no n8n credential references or secret values.
- [x] Existing application workflows, credentials, backups and Git history were preserved.
- [x] Push the feature branch to the configured GitHub remote.
