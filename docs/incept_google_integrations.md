# INCEPT — three verified live read-only integrations

Verified using the actual local n8n **2.47.3** installation on macOS. No paid
provider/model API, email delivery, email-body access, spreadsheet write or
calendar-event creation was performed.

| Integration | Actual execution | Status | Returned data count |
| --- | --- | --- | --- |
| Google Sheets | 12 | PASS | 1 data row |
| Gmail labels list | 13 | PASS | 14 labels |
| Google Calendar calendar list | 14 | PASS | 1 calendar |

Sheets proof is the prior verified run; it was not repeated or modified here.
New sanitized proof files are `reports/incept_gmail_test.json` and
`reports/incept_calendar_test.json`. They replace the earlier blocked-state
reports with actual execution evidence. Each contains the actual workflow ID,
execution ID/status/timestamps, credential name/ID/type, response count, read-only
flags, pagination scope and protected-workflow checks. No personal API content,
OAuth material or raw Google response export is included.

## Credentials and operations

The authenticated public `GET /api/v1/credentials` metadata endpoint returned one
compatible credential of each type. n8n bound the existing credential by ID/name
and performed normal OAuth internally. Credentials were not exported, modified,
substituted between types or inspected in the credential database.

- Gmail: **Gmail account**, type `gmailOAuth2`; new workflow
  **P09yVvzUU49EZIHs**. GET
  `https://gmail.googleapis.com/gmail/v1/users/me/labels`, partial response
  `fields=labels(type)`. No messages, bodies, subjects or label names requested.
- Calendar: **Google Calendar account**, type `googleCalendarOAuth2Api`; new workflow
  **8peDK0SGudnYT6o6**. GET
  `https://www.googleapis.com/calendar/v3/users/me/calendarList`, `maxResults=100`,
  partial response `kind,nextPageToken,items(accessRole,primary)`. No calendar names,
  account identifiers or event data requested. Count is explicitly for the first
  bounded page; `has_more` records whether further results exist.

Both three-node workflows are **inactive**: Manual Trigger → authenticated HTTP
Request GET → sanitized summary. HTTP Request node version **4.5** and Code version
**2** were validated through actual n8n execution, not only offline mocks. Redirects
and configured workflow retries are disabled. Non-200 or unsupported response
shapes cannot produce a passing summary. n8n engine success and final proof output
were both checked; CLI exit codes alone were not relied upon.

The corporate workflow `gqHCIMt3iK8TBWTh` and working onboarding workflow
`msZU5qMxA3kp6KFf` were fingerprinted before/after, including nodes, connections,
settings, inactive state and credential references. Both remained unchanged.

## Repository artifacts and repeatability

- `scripts/incept_google_read_workflows.py`: deterministic builders with strict
  compatible-credential metadata binding; no token handling or network I/O.
- `workflows/incept_gmail_read_test.json`
- `workflows/incept_calendar_read_test.json`
- `tests/test_incept_google_read_workflows.py`

Exports are inactive and contain no actual credential IDs, credential bindings,
runtime pins or execution records. The imported workflows already have the correct
existing credentials bound; do not repeat OAuth or create replacement test nodes.
The same installed CLI used for the real tests can execute the already imported
IDs (substitute the Calendar ID for its separate test):

```sh
N8N_RUNNERS_BROKER_PORT=5689 \
N8N_RUNNERS_MODE=internal \
N8N_DIAGNOSTICS_ENABLED=false \
N8N_VERSION_NOTIFICATIONS_ENABLED=false \
N8N_LICENSE_AUTO_RENEW_ENABLED=false \
/usr/local/bin/node $N8N_CLI \
  execute --id=P09yVvzUU49EZIHs --rawOutput
```

Offline regressions:

```sh
python -m unittest discover -s tests -p test_incept_google_read_workflows.py -q
python -m unittest discover -s tests -q
```

The five new tests check GET-only configuration, compatible credential binding,
credential-free exports, safe counts, absence of personal content, HTTP errors,
malformed responses, empty lists and honest pagination scope. Synthetic fixtures
in tests are distinct from the real execution proof files.

All three live connectivity tests now pass. This does not by itself establish a
complete Project 3 autonomous-agent demonstration: the independently proven
integrations still need a bounded role in the agent workflow. Preserve lawyer
approval for all future sending, scheduling, invoicing or write actions. No such
side-effect integration or change to the existing onboarding flow is implemented
by this test.
