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

    def test_current_export_is_29_node_development_workflow(self):
        root=Path(__file__).resolve().parent.parent
        workflow=json.loads((root/'workflows/legalflow_phase2_development.json').read_text())
        self.assertEqual(len(workflow['nodes']),29)
        for node in workflow['nodes']:
            if node['type'].endswith('httpRequest') and not node.get('disabled'):
                self.assertIn('127.0.0.1:8000',node['parameters']['url'])
                self.assertNotIn('/financial',node['parameters']['url'])
