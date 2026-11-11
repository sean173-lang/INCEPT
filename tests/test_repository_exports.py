"""Repository exports must not contain live trigger capabilities or credentials."""
import json
from pathlib import Path
from offline_support import OfflineTestCase


class SafeWorkflowExportTests(OfflineTestCase):
    def test_exports_have_no_private_runtime_or_credential_fields(self):
        root=Path(__file__).resolve().parent.parent
        forbidden={'credentials','webhookId','pinData','staticData','shared','meta'}
        def inspect(value):
            if isinstance(value,dict):
                self.assertFalse(set(value)&forbidden)
                for child in value.values():inspect(child)
            elif isinstance(value,list):
                for child in value:inspect(child)
        for path in (root/'workflows').glob('*.json'):
            document=json.loads(path.read_text())
            self.assertIs(document.get('active'),False)
            inspect(document)

    def test_canonical_and_separate_ai_development_exports(self):
        root=Path(__file__).resolve().parent.parent
        self.assertEqual({p.name for p in (root/'workflows').glob('*.json')},{'incept_live_documents_v2.json','incept_ai_synthesis_dev.json','incept_prose_intake_dev.json','incept_gradio_demo.json','incept_workspace_inbox.json'})
        workflow=json.loads((root/'workflows/incept_live_documents_v2.json').read_text())
        self.assertEqual(len(workflow['nodes']),37)
        for node in workflow['nodes']:
            if node['type'].endswith('httpRequest') and not node.get('disabled'):
                self.assertTrue(node['parameters']['url'].startswith(('http://127.0.0.1:8003/','https://gmail.googleapis.com/','https://www.googleapis.com/','https://www.gesetze-im-internet.de/','={{')))
                self.assertNotIn('/financial',node['parameters']['url'])
