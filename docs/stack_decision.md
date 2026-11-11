# Primary stack decision

n8n is primary because it makes OAuth-backed integration, branching, error paths and human review visible in one inspectable execution graph. Python/FastAPI supports validated data contracts, deterministic Decimal arithmetic, SQLite idempotency and evidence checks. Reusing LEGALFLOW adapters avoids a second provider integration stack.

Local curated RAG is small and inspectable, with jurisdiction metadata and explicit missing information. It is not a comprehensive legal database. Official-source wording verification adds bounded research without a paid search dependency. Deterministic source checks do not verify allegations or resolve legal applicability.

Tradeoffs: n8n graph and Python contracts need joint regression tests; local SQLite and loopback access are demo infrastructure, not tenant isolation; cached records lose freshness; UK substantive research remains unavailable. Existing fixture planner safety is preserved rather than enabling uncontrolled loops. Gradio provides a thin local presentation layer over the separate structured n8n demo, not a second orchestration engine. It displays real backend results or explicitly labeled saved synthetic fixtures.
