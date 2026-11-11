# Analyze-button repair — 11 November 2026

## Observed failure

Actual Chrome/Playwright interaction reproduced two confusing paths in the running app. Without the fictional-test acknowledgement, Analyze raised only a transient error toast; the persistent workspace status did not explain failure. With acknowledgement, an existing result loaded successfully but remained in another tab, without navigation or visible completion. Selection had already rendered that cached result, making the click appear ineffective. These observations do not establish a failed n8n backend or wrong message ID.

## Repair

The primary interface now has INBOX, ANALYSIS and REPLY. Test acknowledgement sits immediately above ANALYZE. A persistent status reports progress, completion, cache reuse or actionable failure. Successful processing opens ANALYSIS. The selected dropdown ID must match the loaded-body ID before processing. Switching messages clears assessment, drafts, downloads, reply preview, acknowledgement and active case. Document-rendering failures are distinguished from input and processing errors. Fixed fallback and fresh reanalysis remain explicit advanced controls; failures never invoke fallback.

## Real browser validation

Chrome driven by Playwright clicked the actual Gradio controls on port 7860. Fresh selected-message processing completed in **n8n execution 59**. Its Gmail recheck and final result both contained the exact selected message ID. The browser displayed a 6,534-character assessment, three document previews and three PDF links. All five actions remained pending lawyer approval; external actions, financial requests and registry requests were zero. Document statuses remained MISSING_INFORMATION / NOT_READY_FOR_ISSUANCE, with EUR 1,250 + EUR 237.50 = EUR 1,487.50 unchanged.

The browser also exercised the unchecked acknowledgement error, switched to another existing fictional-thread reply, and checked missing-client-name failure. No messages were sent. Browser screenshots, private message IDs and execution traces remain in ignored `data/analyze_ui_repair/` and `data/gmail_workspace/`; they are intentionally not public artifacts. This verifies deterministic onboarding through n8n, not live AI synthesis or legal approval.

## Launch / restart

Stop the existing foreground workspace with Ctrl+C, then run from the repository root:

```sh
/opt/anaconda3/envs/bootcamp-env/bin/python -B -m scripts.gradio_app
```

Open http://127.0.0.1:7860. Keep the existing local n8n running. The launcher owns its isolated FastAPI helper on 8010; do not terminate unrelated services occupying that port.

Playwright and installed Chrome were used as local test tooling; they are not runtime dependencies. The normal offline suite does not access Gmail or launch a live workflow.

## Final checks

- Full offline suite: **307 tests passed**, including six new UI callback regressions.
- Second browser pass confirmed explicit cached-result labeling, cleared assessment placeholder, empty document previews, zero stale PDF links, reset acknowledgement and an actionable missing-client error. Neither pass reported JavaScript page errors.
- All five workflow JSON exports parsed; no workflow export changed.
- All 154 protected historical evidence files retained their original SHA-256 hashes.
- Changed-file secret scan and 389-history-blob secret scan found no matches. Pattern scanning cannot prove absence of every unknown secret. Private browser artifacts remain ignored.
- Changes are local and uncommitted on `feature/incept-gmail-workspace`; no email send, paid API request, financial call, merge or publication occurred during this repair.
