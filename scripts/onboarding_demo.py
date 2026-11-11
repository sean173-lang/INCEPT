"""Reproducible offline HTTP acceptance test and synthetic sample bundle export."""
import json
from pathlib import Path
import socket
import tempfile
from unittest.mock import patch
from fastapi.testclient import TestClient
from scripts.http_service import create_app

ROOT=Path(__file__).resolve().parent.parent


def main():
    body=json.loads((ROOT/'examples/onboarding_preview.json').read_text())
    with tempfile.TemporaryDirectory() as tmp, patch.object(socket.socket,'connect',side_effect=AssertionError('External connections prohibited')):
        app=create_app(development=True,allow_paid=False,cache_dir=None,ledger_path=None,onboarding_db=Path(tmp)/'demo.sqlite3')
        with TestClient(app) as client:
            first=client.post('/v1/onboarding/preview',json=body)
            assert first.status_code==200,first.status_code
            bundle=first.json()
            assert client.post('/v1/onboarding/preview',json=body).json()==bundle
            assert len(bundle['documents'])==3
            assert bundle['advance']['gross_total']=='1487.50'
            assert all(a['state']=='pending_lawyer_approval' and a['executed'] is False and a['due_date'] is None for a in bundle['proposed_actions'])
            sources={s['source_id'] for s in bundle['assessment']['sources']}
            assert all(f['source_ids'] and set(f['source_ids'])<=sources for f in bundle['assessment']['factual_findings']+bundle['assessment']['guidance'])
            assert bundle['external_actions_executed'] is False and bundle['paid_api_calls']==0
    output=ROOT/'reports/legal_intake_mvp';output.mkdir(parents=True,exist_ok=True)
    (output/'bundle.json').write_text(json.dumps(bundle,indent=2,ensure_ascii=False))
    for document in bundle['documents']:(output/(document['kind']+'.md')).write_text(document['content_markdown'])
    (output/'mandate_assessment.md').write_text(bundle['assessment']['content_markdown'])
    (output/'proposed_actions.json').write_text(json.dumps(bundle['proposed_actions'],indent=2,ensure_ascii=False))
    print('Vertical-slice acceptance: PASSED (in-process HTTP, networking blocked).')
    print('Synthetic samples:',output)


if __name__=='__main__':main()
