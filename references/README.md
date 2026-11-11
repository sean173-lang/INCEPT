# Reference stores and evidence separation

Three distinct inputs are maintained:

- `corporate_due_diligence.json`: six curated German/UK identity, litigation and regulatory cards. They are paraphrases, not company records or a complete/current legal opinion. Former financial-disclosure cards were removed with that retired feature. Some original provision dates are unknown; review dates are not enactment dates. `LocalRAG` applies jurisdiction/topic filters and preserves chunk hashes/citations.
- `mandate_intake.json`: four curated mandate/authority/fee/advance reference cards supporting intake review. No company-specific finding is inferred from general guidance.
- `legal_documents/corpus.json` plus snapshots: 32 checked official document-law sources, exact document-type allowlists, retrieval/provenance and version hashes. BMF guidance is distinguished from legislation. See [source index](../docs/legal_document_sources.md) and [maintenance](../docs/legal_document_generation.md).

`incept_corporate_demo.json` contains explicitly synthetic approved offline evidence, not real provider responses. Provider caches remain private, provenance-labeled and separate from law/template guidance. Tavily snippets are unverified research leads; they never replace primary-law or registry evidence. No runtime download occurs during local retrieval/document generation.
