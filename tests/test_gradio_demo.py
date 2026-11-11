"""Regression checks for the Gmail based production workspace surface."""
import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from scripts.gradio_app import main
from scripts.workspace_ui import build_workspace_app
from scripts.workspace_workflow import analysis_graph, extraction_graph
from scripts.gmail_workspace import GmailWorkspace


def test_launcher_has_only_the_gmail_workspace_entrypoint():
    import scripts.gradio_app as app
    assert callable(app.main)
    assert not hasattr(app, 'DemoUI')
    assert not hasattr(app, 'display')
    assert not hasattr(app, 'build_app')


def test_gradio_has_three_areas_and_no_demo_copy():
    with tempfile.TemporaryDirectory() as tmp:
        workspace=GmailWorkspace(root=Path(tmp),transport=MagicMock())
        app=build_workspace_app(workspace=workspace)
        try:
            config=app.config
            labels=[]
            for item in config['components']:
                props=item.get('props',{})
                for key in ('label','value','title','placeholder'):
                    value=props.get(key)
                    if isinstance(value,str):labels.append(value.lower())
            visible=' '.join(labels)
            assert all(name in visible for name in ('inbox','analysis','reply'))
            assert not any(term in visible for term in ('demo','fictional','simulation','saved fixture'))
        finally:
            app.close()


def test_live_graphs_recheck_selected_message_and_call_authenticated_fastapi():
    message={'id':'a1b2c3d4e5f6','encoded_parts':['YWJj'],'body':'This is an inquiry with a sufficiently long body for extraction.'}
    extraction=extraction_graph(message,{'id':'gmail','name':'Gmail'})
    node=next(n for n in extraction['nodes'] if n['name']=='POST Selected Inquiry Extraction')
    assert node['parameters']['url'].endswith('/v1/onboarding/extract')
    assert node['parameters']['headerParameters']['parameters'][0]['name']=='X-LEGALFLOW-Service-Key'
    assert extraction['active'] is False


def test_analysis_graph_calls_source_exact_synthesis_without_document_generation():
    from dotenv import dotenv_values
    from scripts.workspace_workflow import GMAIL
    profile={'name':'Example Client','client_type':'company','jurisdiction':'Germany','governing_law':'Germany','counterparty':'Other Party','scope':'Review the supplied contract'}
    from scripts.gmail_workspace import GmailWorkspace
    with tempfile.TemporaryDirectory() as tmp:
        workspace=GmailWorkspace(root=Path(tmp),transport=MagicMock())
        payload=workspace.payload({'id':'a1b2c3d4e5f6','subject':'Contract review','body':'A sufficiently long source inquiry.'},profile,True)
    graph=analysis_graph({'id':'a1b2c3d4e5f6','encoded_parts':['YWJj']},payload,{'id':'gmail','name':'Gmail'})
    synthesis=next(n for n in graph['nodes'] if n['name']=='POST Source-Exact AI Mandate Synthesis')
    assert synthesis['parameters']['url'].endswith('/v1/onboarding/synthesis')
    assert synthesis['parameters']['headerParameters']['parameters'][0]['name']=='X-LEGALFLOW-Service-Key'
    assert not any(n['name']=='POST Optional Document Draft Generation' for n in graph['nodes'])
    assert next(n for n in graph['nodes'] if n['name']=='Workspace Case Result')
