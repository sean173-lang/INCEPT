# Source-exact synthesis contract 2.0

Status: **offline validated; no live request or workflow execution in this repair**. The complete suite passes 274 tests (255 baseline plus 19 new regressions). Mock reports demonstrate the contract, not actual model reasoning quality or legal correctness.

## Diagnosis of execution 34

The retained response passed JSON schema validation. Its mandate summary was exact. The first failure was `factual_background[0]`: the model wrote that the client had its seat in Germany, but the cited intake JSON only supplied a German jurisdiction. That extra residence/seat inference was unsupported. It must not be accepted merely as a paraphrase.

The second background statement paraphrased a supplied counterparty identity: source-supported, but still incompatible with an excerpt-only factual contract. Corporate items also attempted broader conclusions, supplied inexact coverage quotations, and placed questions/coverage in the corporate-facts section. These defects were independent of model authentication, budget or the presence of known source IDs. The failure fixtures distinguish them without retaining private email/account/case identifiers.

The old validator was right to reject this output. The design flaw was allowing free factual prose in the model schema while requiring it to be extractive afterward. The repair removes that choice from the version-2 wire contract. It does not automatically rehabilitate the old model response or weaken version-1 validation.

## Request and model contract

Existing endpoint: `POST /v1/onboarding/synthesis`.

```json
{
  "contract_version": "2.0",
  "bundle": "<existing typed onboarding bundle object>",
  "corporate_result": null,
  "primary_research": null
}
```

The bundle above is schematic: send the actual object, not a string. Omitted `contract_version` defaults to `1.0` for existing consumers. Unknown versions and caller-supplied catalogues are rejected. There is no new HTTP spending/approval switch.

After existing provenance and jurisdiction checks, the server builds a bounded catalogue of exact excerpts. Each record contains:

- A source ID and stable excerpt ID, bound to case identity, source-content digest, exact text, role, classification and allowed sections.
- Text copied directly from the projected evidence, not generated wording.
- The original evidence classification and source metadata: URL, dates, synthetic flag, freshness and acquisition limits where available.
- Client/counterparty role and governing-law context. Context is not evidence of registered seat or sender authority.
- Allowed factual sections or `reasoning` only; coverage and legal guidance cannot become corporate case facts.

Intake is still unverified input, not established truth. Corporate and legal metadata must pass existing server corpus/cache/receipt resolution. An exact excerpt establishes attribution, not the truth of an allegation. Short/oversized or unsupported spans are not silently rewritten; excessive catalogue size fails closed. Explicit adverse allegations use only existing category-specific supporting spans with attributed status. Denying evidence remains available for uncertainty.

The version-2 model selects factual references such as:

```json
{"source_id": "synthesis:intake:client", "excerpt_id": "excerpt:<server-issued identifier>"}
```

No factual `statement`, quote, classification or provenance field is accepted from the model. Mandate summary, background and corporate observations use these selections. Separate interpretation items contain controlled questions or conditional analysis and cite source/excerpt ID pairs. The server fills exact quote text for those references too.

After validating IDs and allowed sections, the server constructs the existing `AISynthesis` representation and runs the **unchanged** factual, citation, role, jurisdiction, adverse-allegation, contradiction and approval validators. Model text cannot set performed/approved/issued flags. All four flags remain false, action states remain pending, and legally significant deadlines remain unconfirmed.

## Response and n8n compatibility

Responses add `contract_version`, `excerpt_catalog` and `factual_references`. `synthesis` retains the existing expanded shape: factual text and citations are populated by the server, and interpretations remain separately labeled. Existing version-1 responses remain supported.

Only `workflows/incept_ai_synthesis_dev.json`, the separate inactive 40-node export, opts into version 2. n8n sends the upstream bundle/corporate/primary evidence, not a caller-created catalogue. FastAPI generates the catalogue before model transport. The response validator checks selected IDs, source membership, exact expanded text, classifications, issue categories, permitted sections, fixed states and unchanged deterministic fields/documents. Missing or mismatched selection proof falls back safely.

The canonical 37-node export is unchanged. The earlier prose-test export remains on its legacy request contract for compatibility; a future isolated live continuation must explicitly request `contract_version: "2.0"`. No running workflow was imported, edited or executed during this repair.

Persistent reservations, failed attempts and historical ledgers are not reset. Version/schema/prompt fingerprints change; an existing approval cannot silently authorize the new policy. Version-2 caches store validated selection proposals and rehydrate/revalidate them against current server evidence before reuse. Token reservations include the catalogue and versioned schema/prompt. Larger inputs can hit existing limits and fail closed; the repair does not increase configured budgets or enable live calls.

## Offline demonstration and tests

```sh
python -m unittest discover -s tests -q
python -m scripts.ai_excerpt_demo
python -m scripts.incept_ai_workflow
```

Complete local reports: ignored `reports/incept_source_exact_offline/`. The `german_payment_dispute` sample includes the fictional parties, alleged EUR 18,750 claim, disputed performance, local curated BGB sections 611/320/641, contract-classification/acceptance/withholding questions, conditional analysis, unresolved authority and missing original documents. It does not claim fresh source retrieval or verified case facts. All output says mock; no live model is used. Three document drafts are byte-checked unchanged, with all five actions pending and the explicit demo advance unchanged at EUR 1,487.50 gross.

Tests cover sanitized execution-34 failure shapes, valid selections, fabricated/mismatched IDs, wrong section/role, injected factual text/classifications, irrelevant legal-only analysis, unsupported adverse escalation, client-alleged fraud and denial, forged corporate provenance, missing-source uncertainty, approval assertions, deterministic fallback/no retry, cache rehydration, version-policy isolation, HTTP compatibility, intercepted SDK requests, and n8n response tampering. German individual, German company, UK company and ambiguous intake remain covered. UK intake receives no automatic German-law analysis.

## Limits and next live test

A supplied quotation plus a conditional statement still does not prove full semantic entailment. The existing bounded issue/adverse controls remain conservative and can reject unfamiliar legitimate phrasing. The catalogue supports attribution and role discipline; it does not verify client allegations, replace legal research, establish liability or confer professional legal approval. Local trusted storage integrity remains a boundary.

A further controlled live synthesis is justified to evaluate whether a real model reliably selects the new IDs and produces useful supported interpretations. It requires fresh explicit approval and reviewed token limits. No live success or Gradio readiness is established by these offline tests.
