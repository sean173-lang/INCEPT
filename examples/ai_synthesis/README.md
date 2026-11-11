# Synthetic mock synthesis examples

These two reports demonstrate the output/grounding contract only. They use hand-authored mock LLM responses, not OpenAI model inference. `model_used` and `live_request` are false. No real reasoning quality or lawyer approval is established.

- [German individual](individual_mock.md).
- [German company](german_company_mock.md), with unverified representative authority and explicitly synthetic registry evidence.
- [Four-scenario summary](summary.json), including UK abstention and ambiguous-intake blocking.

Regenerate with `python -m scripts.ai_synthesis_demo`; all four complete outputs go to ignored `reports/incept_ai_synthesis_mock/`. Synthetic record IDs may differ between runs. No provider call occurs. See the [architecture and limitations](../../docs/ai_synthesis.md).
