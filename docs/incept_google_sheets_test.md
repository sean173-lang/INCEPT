# INCEPT — real Google Sheets read-only integration

Actual installed n8n: **2.47.3**, directly on macOS. Existing credential metadata
was found through authenticated `GET /api/v1/credentials`: Google Sheets account,
type `googleSheetsOAuth2Api`. Only credential name/ID/type were inspected. No
credential data export, encrypted credential-database inspection, OAuth reset,
client-secret access or authentication bypass was used. n8n's own normal OAuth
request mechanism bound and used the credential internally.

The internal UI's `/rest/credentials` requires session auth and rejected the API
key. It was not bypassed. The supported public credential metadata API worked,
and supported HTTP Request predefined-credential authentication allowed the same
read-only metadata discovery used by the Google Sheets document selector.

## Actual result

- Spreadsheet: **INCEPT_CLIENTS**, discovered from Google's Drive metadata API
  using the existing Sheets credential, not a guessed ID.
- Dedicated account ownership was matched. Exactly one spreadsheet and one GRID
  worksheet were returned; the worksheet is **Tabellenblatt1**, ID 0.
- Separate temporary workflow: **bCVtrny7XwQnhyRY**, inactive, ten nodes.
- **Execution 12: success**. Nine nodes completed on its unique-selection path,
  including the real **Google Sheets Get Row(s)** operation (`resource: sheet`,
  `operation: read`, installed node version **4.7**).
- **One real data row**, three data columns, returned within A1:Z101. No cell
  values are copied into the proof file or this documentation.
- No spreadsheet writes, emails, calendar events or paid provider/model requests.
- Corporate `gqHCIMt3iK8TBWTh` and onboarding `msZU5qMxA3kp6KFf` workflows were
  fingerprinted before/after and remained unchanged and inactive.

Sanitized proof: `reports/incept_google_sheets_test.json`. It records spreadsheet,
worksheet, credential metadata, actual workflow/execution IDs, timestamps, row
count and safety checks, but no OAuth material or cell contents. n8n retains the
actual execution in its normal database; no raw execution export was made.

## Flow and safety

Manual Trigger → metadata GET → unique spreadsheet gate → worksheet metadata GET
→ unique worksheet gate → Google Sheets Get Row(s) → sanitized summary.
Both ambiguous-selection branches stop with candidates for review; there is no
write branch. Metadata discovery reads only owned, non-trashed spreadsheets for
the dedicated account. Incomplete pagination fails closed. Multiple matching
spreadsheets or GRID worksheets are not guessed. Requests have no configured
workflow retries; the row range is bounded. Header rows do not count as data rows.
Empty sheet output cannot produce a successful real-row proof.

The repository artifact `workflows/incept_google_sheets_read_test.json` is an
inactive, credential-free template. It deliberately contains no actual credential
binding or document ID. Runtime binding used name/ID metadata through the normal
n8n API and did not change credentials. `scripts/incept_sheets_workflow.py` builds
the export and binds only existing credential metadata for deployment.

The already imported workflow can be rerun without OAuth setup, manual test-node
creation or activation. On this installation:

```sh
N8N_RUNNERS_BROKER_PORT=5689 \
N8N_RUNNERS_MODE=internal \
N8N_DIAGNOSTICS_ENABLED=false \
N8N_VERSION_NOTIFICATIONS_ENABLED=false \
N8N_LICENSE_AUTO_RENEW_ENABLED=false \
/usr/local/bin/node $N8N_CLI \
  execute --id=bCVtrny7XwQnhyRY --rawOutput
```

CLI exit status alone is not evidence of a successful read: inspect the saved n8n
execution status and the final `Sanitized Read Proof` row count. Selecting a second
spreadsheet later will intentionally require review rather than automatically
reading an arbitrary file. Raw output from future CLI executions may include cell
contents; keep it private and export only the final sanitized summary.

## Regression checks and next step

`tests/test_incept_sheets_workflow.py` checks the actual exported graph, GET-only
metadata operations, Google Sheets read-only operation/version, bounded range,
credential-free export, metadata-only binding, ambiguous selection, worksheet ID
zero, and omission of row values from proof. JavaScript selection code is executed
offline with explicitly synthetic metadata, separate from the real execution proof.

```sh
python -m unittest discover -s tests -p test_incept_sheets_workflow.py -q
python -m unittest discover -s tests -q
```

This evidences Google Sheets as one real integration. It does not claim the full
three-integration Project 3 requirement. Next: inspect existing Gmail credential
metadata and execute a separate read-only labels-list test through an authorized
credential; follow with a Calendar calendar-list test. Do not send email or create
events. Any missing authorization must be established before those separate tests.
No Python modules/directories were renamed as part of the INCEPT product rename.
