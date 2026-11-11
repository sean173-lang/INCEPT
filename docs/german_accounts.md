# Local German SME financial due diligence

Use `scripts/german_accounts.py` for local PDFs and reviewed structured German
statements. It reuses `financial_analysis.analyze_financials` (Decimal ratios,
comparable-period movements, evidence-based review indicators) and
`report_renderer.financial_section`. There is no API, identity infrastructure,
service, workflow, Gradio integration or research loop in this change.

## Working authentic demonstration

The requested Shapesty accounts remain secondary listings only: CompanyHouse lists
2022, 2023 and 2024 balance sheets, but the prior public-source test did not obtain
company-specific official records or document contents. Shapesty financial figures
are **unavailable**, not zero; no proxy figures are attributed to Shapesty.
See private `reports/Shapesty_GmbH_financial_discovery.md` for exact access limits
and the manual official-record check.

The clearly labeled alternative is SIGMA Inklusionsbetrieb gemeinnützige GmbH,
Straubing. Its openly published
[2024 annual account](https://bistum-regensburg.de/fileadmin/Bilder/Themenslider/Finanzkommunikation/Finanzberichte_2024/gb_sigma_FINAL.pdf)
identifies it as a small capital company in the notes (p.9). This nonprofit inclusion
enterprise is a real SME, not a direct commercial comparator for Shapesty. The
account has standalone statements, calendar periods, balance sheets on pp.6–7 and
P&L on p.8. The 2024 column is EUR; 2023 comparative figures are rounded TEUR.
Figures and column headers were visually checked on rendered PDF pages.

The freely readable PDF disallows automatic extraction via its PDF permission
flags. The importer refuses this PDF rather than overriding its permissions.
The demo uses reviewed visual transcription through the structured input path.
A failed 2023 publisher URL was not retried; a separately located public 2024
publisher document supplied the demo. No paid or authenticated request occurred.
The downloaded source remains ignored in `data/german_accounts_demo/SIGMA_2024.pdf`.
It is not redistributed as a repository fixture.

```sh
python -m scripts.german_accounts references/german_accounts_sigma_2024.json \
  --output reports/SIGMA_German_SME_financial_DD.md
```

This produces Markdown and private JSON with facts, provenance and analysis. The
reference manifest contains manually checked financial facts and page mappings,
not a synthetic account. The source SHA256 binds it to the downloaded PDF. In
structured mode it is an attested transcription, not automatic authentication.

## Supplying another SME account

Install `requirements-accounts.txt` for PDF mode. Supply a version-1 JSON manifest
using the demo as a template:

- `reviewed: true`, company label, source URL, document ID, SHA256 and retrieval date.
- `context`: page and source excerpt supporting reporting period/scope.
- Periods: explicit ISO start/end, standalone/consolidated scope, short-year flag.
- Facts: metric from the existing financial metric allowlist, source page, and
  `unit` containing page, excerpt, explicit currency and scale (or null if unknown).
- Structured input: `raw_value` in German number notation and a checked source
  excerpt containing the value. Omit unavailable facts or use null; never use zero
  as a missing-value placeholder. This is a human-reviewed transcription; the tool
  cannot authenticate an invented transcription or source hash without the PDF.
- PDF input: an explicit reviewed `pattern` with a named numeric capture, `column`
  naming that capture, and an explicit occurrence when a row is ambiguous. Unit
  header `pattern` must match the source page. This is layout-specific mapping,
  not universal German-table understanding. Re-review each new document/layout.

```sh
python -m scripts.german_accounts path/to/statement.json \
  --pdf path/to/authorized-account.pdf --output reports/target_financial_DD.md
```

The PDF must match the manifest hash, allow extraction, have a usable text layer,
be no larger than 20 MB and have no more than 100 pages. No passwords, OCR,
permission overrides, downloads or network calls are attempted. Missing/ambiguous
rows and mismatched units/context fail closed. Automated support for a new layout
requires reviewed mappings; manual transcription remains available for readable
scans or restricted-copy PDFs. Do not bypass access restrictions to obtain one.

## Interpretation and limits

The demo checks five metrics: revenue, net income, assets, equity and cash.
2023 TEUR values are multiplied by 1,000 **only because the column explicitly says
TEUR**. EUR/TEUR comparisons and prior-year ratios are approximate due to rounding.
Net margin and equity/assets work; current ratio, EBITDA, cash flow and full net
debt remain unavailable. Verbindlichkeiten is not silently mapped to all debt or
all non-equity liabilities because provisions and grant items are separate.

The report distinguishes source-backed findings, potential buyer risks and missing
information. Cash decline, changing equity ratio and thin net margin are supported
review triggers, not insolvency findings. The 5% margin screen is disclosed as a
heuristic. Buyer questions address cash conversion, receivable collectibility,
related parties, earnings normalization, grants, tax/charitable constraints,
change-of-control consents and completion-account adjustments. No Shapesty or
SIGMA transaction recommendation or independent audit assurance is implied.

Signed/session URLs stay in private input provenance and are represented in output
by document IDs. Reports and derived data are ignored by Git. Financial numbers,
source pages and extraction mappings remain inspectable for review.

## Offline tests

```sh
python -m unittest discover -s tests -q
```

Tests cover manually checked real-demo arithmetic, mixed EUR/TEUR, decimal commas,
negative/missing/zero amounts, incompatible scope, provenance, PDF hashes,
ambiguous matches and signed URL removal. A generated **synthetic unrestricted
PDF** exercises actual PDF extraction; it is clearly separate from the authentic
manually transcribed SME demo. No copyrighted source PDF or paid request is needed
for the regression suite.
