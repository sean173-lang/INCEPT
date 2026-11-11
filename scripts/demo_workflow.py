"""One fixed synthetic scenario; adapt the previously verified structured flow."""
import json
from pathlib import Path
from scripts.intake_workflow import build_workflow as intake_workflow
from scripts.incept_document_workflow import V2_CHECK

ROOT=Path(__file__).resolve().parents[1]
INTAKE=ROOT/'examples/gradio_demo/intake.json'
SAVED_BUNDLE=ROOT/'examples/gradio_demo/bundle.json'
BACKEND='http://127.0.0.1:8010'


def build_workflow():
    graph=intake_workflow();graph['name']='INCEPT — Gradio structured DEMO (manual; no external providers)'
    for node in graph['nodes']:
        if node['name']=='Fictional Intake':node['parameters']['jsCode']='return [{json:'+json.dumps(json.loads(INTAKE.read_text()),ensure_ascii=False)+'}];'
        if node['name']=='POST Onboarding Preview':node['parameters']['url']=BACKEND+'/v1/onboarding/preview'
        if node['name']=='Validate Onboarding Bundle':
            js=node['parameters']['jsCode'];anchor=' check(r && r.title';assert anchor in js
            node['parameters']['jsCode']=js.replace(anchor,V2_CHECK+anchor)
    return graph


if __name__=='__main__':
    (ROOT/'workflows/incept_gradio_demo.json').write_text(json.dumps(build_workflow(),ensure_ascii=False,indent=2)+'\n')
