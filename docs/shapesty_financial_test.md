# Shapesty public-record financial test

The controlled public-source investigation is saved privately in
`reports/Shapesty_GmbH_financial_discovery.md` (reports are Git-ignored).
Structured stage annotations are in `data/shapesty_discovery/assessment.json`.
No provider adapter, workflow, credential, budget or existing ledger is changed.

Target: Shapesty GmbH, Berlin, Amtsgericht Charlottenburg, HRB 246468 B.
Scope: discover and assess official 2022–2024 financial filings without paid API
calls, purchases, retries, account registration, CAPTCHA bypass or document bulk
retrieval. The target's legal identity/status must be confirmed from original
records before financial figures are relied upon.

The handoff distinguishes secondary document listings, official filing discovery,
actual document access, extraction and verified calculations. A lead is never
promoted to an accessed or verified filing merely because it references an
official host. Missing revenue stays unavailable. The existing evidence classifier,
identity normalization and Decimal financial analyzer are reused offline; no UK
XBRL extraction is assumed to work for German filings.

Manual next step: use the official
[all-areas search](https://www.unternehmensregister.de/de/suche/alle-bereiche),
confirm the exact register identity, then check Rechnungslegung/Finanzberichte
and company-specific deposited accounts. Search broadly enough to cover filings
published after their reporting year. Stop at login, payment or CAPTCHA barriers
and record them accurately rather than inferring that filings do not exist.
See [search guidance](https://www.unternehmensregister.de/de/so-gehts/suche) and
[deposited accounts guidance](https://www.unternehmensregister.de/de/so-gehts/hinterlegungen).

No new automated provider path is enabled by this preparation. Run existing
regressions with `python -m unittest discover -s tests -q`.
