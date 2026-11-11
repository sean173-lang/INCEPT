"""Authenticated local n8n transport used by the Gmail workspace."""
import os
import re
import shutil
import subprocess
from pathlib import Path

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


class WorkspaceError(RuntimeError):
    pass


class N8NClient:
    def __init__(self, runtime, session=None, execute=None):
        self.runtime = Path(runtime)
        self.session = session or requests.Session()
        self.session.trust_env = False
        self.execute = execute or subprocess.run

    def request(self, method, path, **kwargs):
        env = dotenv_values(ROOT / '.env')
        key = env.get('N8N_API_KEY') or os.getenv('N8N_API_KEY')
        base = env.get('N8N_BASE_URL') or os.getenv('N8N_BASE_URL') or 'http://127.0.0.1:5678'
        base = base.rstrip('/')
        if not key:
            raise WorkspaceError('The local n8n API key is not configured.')
        if base.endswith('/api/v1'):
            url = base + path
        else:
            url = base + '/api/v1' + path
        try:
            response = self.session.request(method, url, headers={'X-N8N-API-KEY': key},
                timeout=15, allow_redirects=False, **kwargs)
            if not response.ok:
                raise WorkspaceError('The local n8n API is unavailable or rejected the request.')
            return response.json()
        except (requests.RequestException, ValueError):
            raise WorkspaceError('Cannot reach the local n8n API.') from None

    def command(self, workflow_id):
        node = shutil.which('node')
        configured = os.getenv('INCEPT_N8N_CLI')
        candidates = [Path(configured).expanduser()] if configured else sorted((Path.home() / '.npm/_npx').glob('*/node_modules/n8n/bin/n8n'))
        global_cli = shutil.which('n8n')
        if not configured and global_cli:
            candidates = [Path(global_cli)]
        if not node or len(candidates) != 1 or not candidates[0].is_file():
            raise WorkspaceError('The installed n8n CLI is not uniquely available.')
        if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', str(workflow_id)):
            raise WorkspaceError('Invalid local n8n workflow identifier.')
        return [node, str(candidates[0]), 'execute', '--id', str(workflow_id), '--rawOutput']
