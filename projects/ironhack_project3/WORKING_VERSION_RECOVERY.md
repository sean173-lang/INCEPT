# Project 3 working-version recovery point

Created 2026-11-12 before the separate form redesign task.

- Git branch: `feature/ironhack-project3-mvp`
- Workflow: `INCEPT — Company Research Agent`
- Workflow ID: `61tsMgiWvpjit2st`
- Active at backup: yes; 33 nodes
- Form: `http://localhost:5678/form/incept-company-research`
- Webhook path: `ironhack-company-research` (header authenticated)
- Private live export: `/Users/seanl/Projects/legalflow-ma/private_backups/project3-working-before-redesign-20261112T105010Z/workflow-61tsMgiWvpjit2st.json`
- Private manifest: same directory, `manifest.json` (includes credential reference identifiers; contains no credential values)
- Repository export: [`workflow.json`](workflow.json), sanitized and verified against the live graph

The private backup directory is mode `0700`; the workflow export and manifest are mode `0600`. The export parsed successfully and matched the live graph after removing n8n credential bindings and the generated webhook ID. The n8n export contained no values matching the checked inline-secret patterns. Credential values are not part of the backup.

## Roll back the workflow without creating another workflow

Do not call `POST /api/v1/workflows`. Restore the existing workflow by updating its stable ID:

1. Ensure the n8n credential records referenced by the saved workflow still exist. The backup contains credential references only.
2. From the repository root, run the following Python snippet. It reads the private export and the existing API key from the ignored `.env`, then sends only the editable workflow fields to `PUT /api/v1/workflows/61tsMgiWvpjit2st`.

   ```sh
   python - <<'PY'
   import os, json, requests
   from pathlib import Path
   from dotenv import load_dotenv

   load_dotenv('.env', override=True)
   base = (os.getenv('N8N_BASE_URL') or 'http://127.0.0.1:5678').rstrip('/')
   key = os.environ['N8N_API_KEY']
   backup = Path('private_backups/project3-working-before-redesign-20261112T105010Z/workflow-61tsMgiWvpjit2st.json')
   saved = json.loads(backup.read_text(encoding='utf-8'))
   workflow_id = '61tsMgiWvpjit2st'
   assert saved['id'] == workflow_id
   payload = {name: saved[name] for name in ('name', 'nodes', 'connections', 'settings')}
   session = requests.Session()
   session.trust_env = False
   headers = {'X-N8N-API-KEY': key}
   response = session.put(f'{base}/api/v1/workflows/{workflow_id}', headers=headers,
                          json=payload, timeout=20, allow_redirects=False)
   response.raise_for_status()
   check = session.get(f'{base}/api/v1/workflows/{workflow_id}', headers=headers,
                       timeout=12, allow_redirects=False)
   check.raise_for_status()
   current = check.json()
   assert current['id'] == workflow_id and current['name'] == saved['name']
   assert len(current['nodes']) == 33
   if not current.get('active'):
       activation = session.post(f'{base}/api/v1/workflows/{workflow_id}/activate',
                                 headers=headers, timeout=12, allow_redirects=False)
       activation.raise_for_status()
   print('Restored existing workflow ID; no workflow was created.')
   PY
   ```

3. Verify the workflow remains active with the saved form and webhook paths. Do not use a test submission that invokes research providers unless separately authorized.

The private manifest records credential reference names and identifiers for comparison. It does not contain credential values; if a referenced n8n credential was deleted, restore that credential through the authorized secret-management process before activating the workflow.
