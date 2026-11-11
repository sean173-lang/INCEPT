"""Local demo transport. Only an exact inactive manual workflow may execute.

No provider credentials are loaded, no model calls are made, and no UI input can
select a workflow, CLI command, API URL or client payload.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import re
import subprocess
import threading

import requests
from dotenv import dotenv_values
from scripts.demo_workflow import ROOT,INTAKE,SAVED_BUNDLE,BACKEND,build_workflow
from scripts.onboarding_schemas import OnboardingBundle

RUNTIME=ROOT/'data/gradio_demo'
N8N='http://127.0.0.1:5678/api/v1'


class DemoError(RuntimeError):pass


def validate_bundle(value):
    bundle=OnboardingBundle.model_validate(value)
    scenario=json.loads(INTAKE.read_text())
    if bundle.client.name!=scenario['client']['name'] or bundle.matter.opposing_parties!=scenario['matter']['opposing_parties']:
        raise DemoError('Unexpected scenario; result withheld.')
    if len(bundle.documents)!=3 or {d.kind for d in bundle.documents}!={'vollmacht','fee_agreement','advance_invoice'}:
        raise DemoError('Three document drafts are required.')
    if any(d.template_version!='2.0.0' or d.ready_for_issuance or d.legally_approved or d.state!='pending_lawyer_approval' for d in bundle.documents):
        raise DemoError('Document approval guard failed.')
    if len(bundle.proposed_actions)!=5 or any(a.executed or a.state!='pending_lawyer_approval' or a.due_date is not None for a in bundle.proposed_actions):
        raise DemoError('Pending-action guard failed.')
    if (bundle.advance.net_fee,bundle.advance.vat_amount,bundle.advance.gross_total)!=('1250.00','237.50','1487.50'):
        raise DemoError('Advance arithmetic failed.')
    if next(d for d in bundle.documents if d.kind=='advance_invoice').completeness_status!='NOT_READY_FOR_ISSUANCE':raise DemoError('Incomplete demo advance must remain unissued.')
    sources={s.source_id for s in bundle.assessment.sources}
    if any(not set(f.source_ids)<=sources for f in bundle.assessment.factual_findings+bundle.assessment.guidance):raise DemoError('Unresolved citation.')
    if any(s.url and not s.url.startswith('https://www.gesetze-im-internet.de/') for s in bundle.assessment.sources):raise DemoError('Unexpected source URL.')
    return bundle


def load_saved():return validate_bundle(json.loads(SAVED_BUNDLE.read_text()))


def digest(graph):
    # n8n may add defaults at import. Compare the exact returned graph on later runs.
    return hashlib.sha256(json.dumps({k:graph[k] for k in ('nodes','connections')},sort_keys=True).encode()).hexdigest()


def check_workflow(graph):
    expected=build_workflow()
    if graph.get('active') or len(graph.get('nodes',[]))!=10:raise DemoError('Only the inactive ten-node demo workflow is allowed.')
    actual={n['name']:n for n in graph['nodes']};wanted={n['name']:n for n in expected['nodes']}
    if actual.keys()!=wanted.keys() or graph['connections']!=expected['connections']:raise DemoError('Workflow graph differs from the reviewed demo.')
    for name,n in actual.items():
        if n['type']!=wanted[name]['type'] or n['parameters']!=wanted[name]['parameters'] or n.get('credentials') or n.get('webhookId') or n.get('retryOnFail') or n.get('disabled'):
            raise DemoError('Workflow parameters differ from the reviewed demo.')
    return graph


class DemoRunner:
    def __init__(self,runtime=RUNTIME,session=None,execute=None):
        self.runtime=Path(runtime);self.session=session or requests.Session();self.session.trust_env=False
        self.execute=execute or subprocess.run
        self.lock=threading.Lock()
    def request(self,method,path,**kwargs):
        key=dotenv_values(ROOT/'.env').get('N8N_API_KEY') or os.getenv('N8N_API_KEY')
        if not key:raise DemoError('Local n8n API credential is missing. Saved DEMO mode remains available.')
        try:
            response=self.session.request(method,N8N+path,headers={'X-N8N-API-KEY':key},timeout=15,allow_redirects=False,**kwargs)
            if not response.ok:raise DemoError('Local n8n API is unavailable or unauthorized.')
            return response.json()
        except (requests.RequestException,ValueError):raise DemoError('Cannot reach the local n8n API. Saved DEMO mode remains available.') from None
    def ensure_workflow(self):
        self.runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
        path=self.runtime/'workflow.json'
        if path.exists():
            stored=json.loads(path.read_text())
            if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}',stored.get('id','')):raise DemoError('Invalid local workflow reference.')
            graph=check_workflow(self.request('GET','/workflows/'+stored['id']))
            if digest(graph)!=stored['digest']:raise DemoError('Demo workflow changed; execution blocked.')
            return stored['id']
        graph=build_workflow();check_workflow(graph)
        created=check_workflow(self.request('POST','/workflows',json={k:graph[k] for k in ('name','nodes','connections','settings')}))
        path.write_text(json.dumps({'id':created['id'],'digest':digest(created)}));path.chmod(0o600)
        return created['id']
    def command(self,wid):
        node=shutil.which('node')
        configured=os.getenv('INCEPT_N8N_CLI')
        candidates=[Path(configured).expanduser()] if configured else sorted((Path.home()/'.npm/_npx').glob('*/node_modules/n8n/bin/n8n'))
        global_cli=shutil.which('n8n')
        if not configured and global_cli:candidates=[Path(global_cli)]
        if not node or len(candidates)!=1 or not candidates[0].is_file():raise DemoError('Installed n8n CLI not uniquely found. Set INCEPT_N8N_CLI to its existing path; no package is downloaded.')
        return [node,str(candidates[0]),'execute','--id',wid,'--rawOutput']
    def run(self):
        if not self.lock.acquire(blocking=False):raise DemoError('A demo execution is already running.')
        try:
            self.runtime.mkdir(parents=True,exist_ok=True,mode=0o700)
            with (self.runtime/'run.lock').open('a') as lock:
                try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:raise DemoError('Another demo process is running.') from None
                try:return self._run()
                finally:fcntl.flock(lock,fcntl.LOCK_UN)
        finally:self.lock.release()
    def _run(self):
        try:health=self.session.get(BACKEND+'/health',timeout=3,allow_redirects=False)
        except requests.RequestException:raise DemoError('Demo FastAPI helper is unavailable. Use the one-command launcher or saved DEMO mode.') from None
        if health.status_code!=200 or health.headers.get('X-INCEPT-Demo-Profile')!='structured-preview-v1':raise DemoError('The isolated demo backend is not running; execution blocked.')
        wid=self.ensure_workflow()
        previous=self.request('GET','/executions',params={'workflowId':wid,'limit':1}).get('data',[])
        previous_id=previous[0]['id'] if previous else None
        env=dict(os.environ,N8N_RUNNERS_BROKER_PORT='5693',N8N_RUNNERS_MODE='internal',N8N_DIAGNOSTICS_ENABLED='false',N8N_VERSION_NOTIFICATIONS_ENABLED='false',N8N_LICENSE_AUTO_RENEW_ENABLED='false')
        try:process=self.execute(self.command(wid),env=env,capture_output=True,text=True,timeout=100,cwd=ROOT)
        except (OSError,subprocess.TimeoutExpired):raise DemoError('n8n execution failed or timed out; inspect local n8n. No automatic retry or success claim.') from None
        log=self.runtime/'last_cli.txt';log.write_text(process.stdout+process.stderr);log.chmod(0o600)
        latest=self.request('GET','/executions',params={'workflowId':wid,'limit':1}).get('data',[])
        if not latest or latest[0]['id']==previous_id:raise DemoError('No new n8n execution was recorded; saved output is not a live run.')
        execution=self.request('GET','/executions/'+latest[0]['id'],params={'includeData':'true'})
        trace=self.runtime/('execution_'+execution['id']+'.json');trace.write_text(json.dumps(execution));trace.chmod(0o600)
        if process.returncode!=0 or execution['status']!='success':raise DemoError('n8n execution '+execution['id']+' failed. No external actions were performed; use saved DEMO mode.')
        runs=execution.get('data',{}).get('resultData',{}).get('runData',{})
        try:result=runs['Execution Summary'][-1]['data']['main'][0][0]['json']
        except (KeyError,IndexError,TypeError):raise DemoError('n8n did not produce its final execution summary.') from None
        if not result.get('business_success') or result.get('outcome')!='passed':raise DemoError('n8n execution '+execution['id']+' requires manual review; backend validation did not pass.')
        if result.get('n8n_execution_id')!=str(execution['id']):raise DemoError('Execution summary ID mismatch.')
        bundle=validate_bundle(result['bundle'])
        for field in ('emails_sent','calendar_events_created','invoices_issued'):
            if result.get(field)!=0:raise DemoError('External-action safeguard failed.')
        return bundle,{'mode':'real_local_n8n','execution_id':execution['id'],'workflow_id':wid,'n8n_status':'success','business_success':True,'provider_requests':0,'ai_mode':'disabled; deterministic assessment','external_actions':0}
