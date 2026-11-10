# End-to-end n8n validation — 2026-11-10

**The current workflow's complete verified-company development path passed.**
Workflow: `gqHCIMt3iK8TBWTh`. Evidence: saved n8n manual execution **9**, status
success, using the **29-node** workflow snapshot and ending at
**Due Diligence Report**. This conclusion is based on saved n8n node outputs,
not just direct FastAPI tests or the execution's success flag.

## What actually ran

- Form submission, field mapping and development-input validation.
- FastAPI development health check and synthetic German company search.
- Candidate selection and provider-detail identity verification.
- Research-run creation at iteration 0, proposing `retrieve_references`.
- Research tool execution 1, returning iteration 1 and `company_research` next.
- Research tool execution 2, returning iteration 2, state complete and no next tool.
- Plan validation ran three times (initial state plus both transitions).
- Structured report generation and the final Due Diligence Report node.

The final report has four diligence topics and four reference citations. Its
risk assessment is Undetermined and overall confidence insufficient. Every topic
has missing-data warnings. Original dates remain unknown where not established;
review dates and locators are preserved.

## Evidence and source checks

`scripts/workflow_validation.py` checks the actual execution envelope, required
nodes, two tool transitions and stopping condition, development flags, report
schema, verified-company identity, corpus version, topic coverage, confidence,
missing data, document requests, exact reference attribution and resolved claim
source IDs. All checks passed; machine-readable results are in
`docs/validation_execution9.json`.

References match canonical local corpus text, source URLs and dates. There are
no placeholder source links. Verified facts are limited to synthetic record
consistency; background law and unverified leads are not promoted to company
findings. High confidence applies only to fixture consistency, not a real legal
assessment. The report does not establish that no litigation or regulatory issues
exist or that financial information is unpublished.

## Ambiguity and manual review

Offline execution of the **saved live workflow's** candidate JavaScript with two
synthetic candidates returns ambiguous and creates no automatic verification
request. The saved graph routes this case to **Select Company Candidate**, an
interactive human selection form. Invalid selections and failed/unresolved
verification route to **Verification Needs Review**. Research is connected only
after the verified branch.

The multiple-candidate interactive form was not reached by execution 9: ordinary
development search fixtures return one candidate. Thus this branch is checked
against the saved graph and offline execution, not claimed as a second genuine
end-to-end ambiguous-company run. A future interactive ambiguity test requires
controlled multiple-candidate fixture data and a human choice; no such live
workflow or provider-fixture modification was made during this validation.

## Manual actions and earlier execution

Execution 8 was a successful **20-node Phase 1** snapshot stopping at Verified
Company. It did not exercise research/report generation and cannot count as a
Phase 2 pass. The new validator explicitly rejects this false-positive case.

The test form was initially not listening (HTTP 404), and the supported retry API
rejected replay with HTTP 409. The user refreshed/started the current workflow in
the n8n editor. A subsequent manual form execution produced execution 9 and the
complete report. Starting **Execute workflow** and submitting the test form are
manual interactions; workflow activation is not required. No separate automated
API-start capability is claimed.

## Changes, tests and safety

No workflow defect was demonstrated by execution 9, so no live workflow edits
were made during this validation. Added the reusable execution-evidence validator
and six offline regression tests for old/partial successes, complete execution
fixtures, missing tool work, tampered sources/warnings and wrong-company reports.

Full offline suite: **147 tests passed**. Python compilation and whitespace
checks passed. Private execution snapshots and the inspected workflow remain
outside the repository in a mode-0700 temporary directory, with files mode 0600.
Only the sanitized pass/fail evidence was added to documentation.

Final REST reads confirmed the same workflow ID, unchanged credential bindings
and inactive state. FastAPI remained in development mode; estimated
OpenRegister credits, Tavily searches and unknown-cost reservations were all zero.
No paid provider, financial endpoint, activation, `.env` modification, commit or
push was performed.
