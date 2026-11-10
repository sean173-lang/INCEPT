"""Build the inactive development-only n8n integration from a private live export.

This module performs no network I/O. Deployment must back up and inspect the
live workflow, keep its ID/trigger, and verify development mode separately.
"""
import copy
import uuid

BASE_URL = 'http://127.0.0.1:8000'

PREPARE = r'''
const input = $input.first().json;
const jurisdiction = input.jurisdiction;
const requested = typeof input.company_name === 'string' ? input.company_name.trim() : '';
const valid = requested.length > 0 && requested.length <= 200 && !/[\x00-\x1f\x7f]/.test(requested)
  && ['Germany', 'UK'].includes(jurisdiction);
return [{json: {requested_company: requested, jurisdiction,
  requested_include_financials: input.include_financials === true,
  include_financials: false, financial_requests_enabled: false, development: true,
  company_name: jurisdiction === 'UK' ? 'LEGALFLOW DEMO LTD' : 'LEGALFLOW DEMO GmbH',
  ready: valid, status: valid ? 'pending' : 'verification_failed',
  message: valid ? 'Development fixtures only; requested real company will not be queried.' : 'Company name and Germany/UK jurisdiction are required.'}}];
'''

HEALTH = r'''
const context = $('Prepare Development Input').first().json;
const response = $input.first().json;
const body = response.body;
const ready = response.statusCode === 200 && body?.status === 'ok' && body?.development === true;
return [{json: {...context, ready, status: ready ? 'pending' : 'verification_failed',
  message: ready ? 'FastAPI development mode confirmed.' : 'FastAPI unavailable or not in development mode; workflow stopped.'}}];
'''

CANDIDATES = r'''
const context = $('Prepare Development Input').first().json;
const response = $input.first().json;
const body = response.body;
function result(status, message, extra={}) {
  return [{json: {...context, status, message, candidates: [], ...extra}}];
}
if (response.statusCode !== 200 || body?.development !== true || !Array.isArray(body?.candidates)) {
  return result('verification_failed', 'Development company search failed or returned an unsupported response.');
}
const candidates = body.candidates;
if (body.status === 'not_found' && candidates.length === 0) return result('not_found', 'No company candidates returned.');
if (body.status !== 'candidates_found' || candidates.length === 0) return result('verification_failed', 'Inconsistent search response.');
// Only synthetic identities can enter this workflow, even if a caller edits the form.
const allowed = candidates.every(c => c.jurisdiction === context.jurisdiction &&
  typeof c.name === 'string' && typeof c.provider_company_id === 'string' &&
  (context.jurisdiction === 'UK' ? c.provider_company_id === '00000000' && c.name === 'LEGALFLOW DEMO LTD'
    : /^DEMO(?:-[A-Za-z0-9_-]+)?$/.test(c.provider_company_id) && c.name === 'LEGALFLOW DEMO GmbH'));
if (!allowed) return result('verification_failed', 'Non-synthetic candidates rejected.');
const unique = new Map(candidates.map(c => [JSON.stringify(c), c]));
const rows = [...unique.values()];
const options = rows.map(c => ({option: `${c.provider_company_id} | ${c.name} | ${c.register_court || 'UK register'}`}));
function request(c) {
  const payload = {company_name: c.name, jurisdiction: c.jurisdiction, provider_company_id: c.provider_company_id};
  if (c.registration_number) payload.registration_number = c.registration_number;
  if (c.jurisdiction === 'Germany' && c.register_court) payload.register_court = c.register_court;
  if (c.jurisdiction === 'Germany' && ['HRB','HRA'].includes(c.register_type)) payload.register_type = c.register_type;
  return payload;
}
if (rows.length === 1) return result('selected', 'Candidate selected; company details still require verification.',
  {candidates: rows, verification_request: request(rows[0]), candidate_options: options});
return result('ambiguous', 'Select a candidate before details can be verified.', {candidates: rows, candidate_options: options});
'''

SELECTION = r'''
const context = $('Prepare Company Candidates').first().json;
const choice = $input.first().json['Company Candidate'];
const matches = context.candidates.filter(c => `${c.provider_company_id} | ${c.name} | ${c.register_court || 'UK register'}` === choice);
if (matches.length !== 1) return [{json:{...context, status:'verification_failed', message:'Invalid or ambiguous candidate selection.'}}];
const c = matches[0];
const verification_request = {company_name:c.name, jurisdiction:c.jurisdiction, provider_company_id:c.provider_company_id};
if (c.registration_number) verification_request.registration_number = c.registration_number;
if (c.jurisdiction === 'Germany' && c.register_court) verification_request.register_court = c.register_court;
if (c.jurisdiction === 'Germany' && ['HRB','HRA'].includes(c.register_type)) verification_request.register_type = c.register_type;
return [{json:{...context, status:'selected', verification_request, message:'Candidate selected; details verification required.'}}];
'''

CHECK_VERIFY = r'''
const context = $('Prepare Development Input').first().json;
const response = $input.first().json;
const body = response.body;
if (response.statusCode !== 200 || body?.development !== true ||
  !['verified','ambiguous','not_found','verification_failed'].includes(body?.status)) {
  return [{json:{...context,status:'verification_failed',message:'Development details verification failed; no automatic retry.'}}];
}
const valid = body.status !== 'verified' ||
  (body.verification_scope === 'provider_record_identity' && /^[a-f0-9]{32}$/.test(body.verification_id || '') &&
   body.company?.jurisdiction === context.jurisdiction &&
   typeof body.checks === 'object' && Object.keys(body.checks).length >= 3 && Object.values(body.checks).every(v=>v === true) &&
   (context.jurisdiction === 'UK' ? body.company.provider_company_id === '00000000' && body.company.name === 'LEGALFLOW DEMO LTD'
     : /^DEMO(?:-[A-Za-z0-9_-]+)?$/.test(body.company?.provider_company_id || '') && body.company.name === 'LEGALFLOW DEMO GmbH'));
return [{json:{...context,status:valid ? body.status : 'verification_failed',
  message:valid ? 'Provider detail verification result received.' : 'Verification result failed local consistency checks.',
  ...(valid ? {verification_result:body} : {})}}];
'''

VERIFIED = r'''
const item = $input.first().json;
return [{json:{status:'verified', development:true, financial_requests_enabled:false,
  requested_company:item.requested_company, company:item.verification_result.company,
  verification_id:item.verification_result.verification_id, verification_scope:'provider_record_identity',
  message:'Synthetic provider-record identity verified. Financial requests remain disabled.'}}];
'''

REVIEW = r'''
const item = $input.first().json;
return [{json:{status:['ambiguous','not_found','verification_failed'].includes(item.status) ? item.status : 'verification_failed',
  development:true, financial_requests_enabled:false, requested_company:item.requested_company || '',
  jurisdiction:item.jurisdiction, candidates:item.candidates || [],
  message:item.message || 'Verification requires review; no further provider requests were made.'}}];
'''


def build_workflow(original):
    if original.get('active') is True:
        raise ValueError('Refusing to update an active workflow')
    original_nodes = {n['name']: n for n in original['nodes']}
    trigger = copy.deepcopy(original_nodes['On form submission'])
    fields = copy.deepcopy(original_nodes['Edit Fields'])
    old_search = original_nodes['OpenRegister Company Search']
    nodes = [trigger, fields]
    connections = {}

    def add(name, kind, parameters, version=2, position=(0, 0)):
        node = {'id':str(uuid.uuid5(uuid.NAMESPACE_URL, 'legalflow-phase1-development/' + name)),
                'name':name, 'type':'n8n-nodes-base.' + kind, 'typeVersion':version,
                'position':list(position), 'parameters':parameters}
        nodes.append(node)
        return node

    def code(name, source, position):
        return add(name, 'code', {'jsCode':source}, position=position)

    def condition(name, expression, position):
        return add(name, 'if', {'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},
                    'conditions':[{'id':str(uuid.uuid4()),'leftValue':expression,'rightValue':True,
                                   'operator':{'type':'boolean','operation':'true','singleValue':True}}],
                    'combinator':'and'},'options':{}}, version=2.2, position=position)

    def http(name, path, position, body=None):
        params = {'method':'POST' if body else 'GET', 'url':BASE_URL + path,
                  'options':{'timeout':15000,'redirect':{'redirect':{'followRedirects':False}},
                             'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}}
        if body:
            params.update(sendBody=True,specifyBody='json',jsonBody=body)
        node = add(name, 'httpRequest', params, version=old_search.get('typeVersion',4.5), position=position)
        node.update(retryOnFail=False, onError='continueRegularOutput')
        return node

    def link(source, target, branch=0):
        main = connections.setdefault(source, {'main':[]})['main']
        while len(main) <= branch:
            main.append([])
        main[branch].append({'node':target,'type':'main','index':0})

    code('Prepare Development Input', PREPARE, (460,0))
    condition('Input Valid?', '={{ $json.ready === true }}', (680,0))
    http('FastAPI Health', '/health', (900,0))
    code('Require Development Mode', HEALTH, (1120,0))
    condition('Development Ready?', '={{ $json.ready === true }}', (1340,0))
    http('FastAPI Company Search', '/v1/company/search', (1560,0),
         '={{ JSON.stringify({company_name: $json.company_name, jurisdiction: $json.jurisdiction}) }}')
    code('Prepare Company Candidates', CANDIDATES, (1780,0))
    condition('Candidate Selected?', "={{ $json.status === 'selected' }}", (2000,0))
    condition('Candidate Selection Required?', "={{ $json.status === 'ambiguous' }}", (2220,280))
    add('Select Company Candidate', 'form', {
        'operation':'page', 'defineForm':'json',
        'jsonOutput':"={{ JSON.stringify([{fieldLabel: 'Company Candidate', fieldType: 'dropdown', requiredField: true, fieldOptions: {values: $json.candidate_options}}]) }}",
        'options':{'formTitle':'LEGALFLOW — select synthetic company', 'formDescription':'Development only. No financial requests will be made.'}},
        version=2.3, position=(2440,280))
    code('Validate Candidate Selection', SELECTION, (2660,280))
    condition('Selection Valid?', "={{ $json.status === 'selected' }}", (2880,280))
    http('FastAPI Verify Company', '/v1/company/verify', (3100,0), '={{ JSON.stringify($json.verification_request) }}')
    code('Check Verification Response', CHECK_VERIFY, (3320,0))
    condition('Company Verified?', "={{ $json.status === 'verified' }}", (3540,0))
    code('Verified Company', VERIFIED, (3760,0))
    code('Verification Needs Review', REVIEW, (3760,440))
    archive = copy.deepcopy(old_search)
    archive.update(id=str(uuid.uuid5(uuid.NAMESPACE_URL, 'legalflow-archived-openregister')),
                   name='Legacy OpenRegister Search (disabled)', disabled=True, position=[1560,700],
                   notes='Archived solely to retain the existing credential reference. No incoming or outgoing connections.', notesInFlow=True)
    nodes.append(archive)

    chain = ['On form submission','Edit Fields','Prepare Development Input','Input Valid?','FastAPI Health',
             'Require Development Mode','Development Ready?','FastAPI Company Search','Prepare Company Candidates','Candidate Selected?']
    for source,target in zip(chain,chain[1:]):
        link(source,target)
    for gate in ('Input Valid?','Development Ready?','Selection Valid?','Company Verified?'):
        link(gate,'Verification Needs Review',1)
    link('Candidate Selected?','FastAPI Verify Company')
    link('Candidate Selected?','Candidate Selection Required?',1)
    link('Candidate Selection Required?','Select Company Candidate')
    link('Candidate Selection Required?','Verification Needs Review',1)
    link('Select Company Candidate','Validate Candidate Selection')
    link('Validate Candidate Selection','Selection Valid?')
    link('Selection Valid?','FastAPI Verify Company')
    link('FastAPI Verify Company','Check Verification Response')
    link('Check Verification Response','Company Verified?')
    link('Company Verified?','Verified Company')
    return {'name':original['name'], 'nodes':nodes,'connections':connections,'settings':copy.deepcopy(original.get('settings',{}))}


RESEARCH_PLAN = r'''
const context = $('Verified Company').first().json;
const response = $input.first().json;
const body = response.body;
const runIndex = typeof $runIndex === 'number' ? $runIndex : 0;
const valid = runIndex <= 2 && response.statusCode === 200 && body?.development === true &&
  /^[a-f0-9]{32}$/.test(body.run_id || '') && Number.isInteger(body.iteration) && body.iteration >= 0 && body.iteration <= 2 &&
  body.max_iterations <= 2 && ['ready','complete'].includes(body.state) &&
  (body.state === 'complete' || (body.iteration < 2 && ['retrieve_references','company_research'].includes(body.next_tool)
    && /^[a-f0-9]{64}$/.test(body.plan_token || '')));
return [{json: valid ? {...context,...body,ready:true} : {...context,ready:false,status:'verification_failed',
  message:'Research plan failed development, tool or iteration checks; manual review required.'}}];
'''

RESEARCH_REPORT = r'''
const context = $('Verified Company').first().json;
const response = $input.first().json;
const body = response.body;
const ready = response.statusCode === 200 && body?.development === true && body.risk_assessment === 'Undetermined' &&
  body.overall_confidence === 'insufficient' && typeof body.markdown === 'string' && Array.isArray(body.sections) &&
  body.sections.length > 0 && body.sections.length <= 4 && Number.isInteger(body.iterations) && body.iterations <= 2 &&
  body.company?.provider_company_id === context.company?.provider_company_id;
return [{json:ready ? {ready:true,status:'research_complete',development:true,financial_requests_enabled:false,report:body}
  : {...context,ready:false,status:'verification_failed',message:'Research report failed validation; manual review required.'}}];
'''


def extend_research_workflow(original):
    """Preserve the existing Phase 1 graph and credential bindings in-place."""
    if original.get('active') is True:
        raise ValueError('Refusing to edit an active workflow')
    nodes = copy.deepcopy(original['nodes'])
    connections = copy.deepcopy(original['connections'])
    by_name = {n['name']:n for n in nodes}
    if 'Verified Company' not in by_name or 'Verification Needs Review' not in by_name:
        raise ValueError('Phase 1 verification nodes are required')
    if 'FastAPI Create Research Run' in by_name:
        raise ValueError('Research branch already exists; review changes before reapplying')

    def add(name, kind, params, version=2, position=(0,0)):
        node={'id':str(uuid.uuid5(uuid.NAMESPACE_URL,'legalflow-phase2/'+name)), 'name':name,
              'type':'n8n-nodes-base.'+kind,'typeVersion':version,'parameters':params,'position':list(position)}
        nodes.append(node)
        return node
    def http(name, url, body, position):
        node=add(name,'httpRequest',{'method':'POST','url':url,'sendBody':True,'specifyBody':'json','jsonBody':body,
                 'options':{'timeout':15000,'redirect':{'redirect':{'followRedirects':False}},
                            'response':{'response':{'fullResponse':True,'neverError':True,'responseFormat':'json'}}}},4.5,position)
        node.update(retryOnFail=False,onError='continueRegularOutput')
    def gate(name, expression, position):
        add(name,'if',{'conditions':{'options':{'caseSensitive':True,'leftValue':'','typeValidation':'strict','version':2},
            'conditions':[{'id':str(uuid.uuid4()),'leftValue':expression,'rightValue':True,
                           'operator':{'type':'boolean','operation':'true','singleValue':True}}],'combinator':'and'},'options':{}},2.2,position)
    def link(source,target,branch=0):
        outputs=connections.setdefault(source,{'main':[]})['main']
        while len(outputs)<=branch:outputs.append([])
        outputs[branch].append({'node':target,'type':'main','index':0})

    http('FastAPI Create Research Run',BASE_URL+'/v1/research/runs',
         '={{ JSON.stringify({verification_id:$json.verification_id,max_iterations:2}) }}',(3980,0))
    add('Check Research Plan','code',{'jsCode':RESEARCH_PLAN},position=(4200,0))
    gate('Research Plan Valid?','={{ $json.ready === true }}',(4420,0))
    gate('Research Action Needed?',"={{ $json.state === 'ready' }}",(4640,0))
    http('FastAPI Research Tool',"={{ 'http://127.0.0.1:8000/v1/research/runs/' + $json.run_id + '/tools' }}",
         '={{ JSON.stringify({tool:$json.next_tool,plan_token:$json.plan_token}) }}',(4860,-220))
    http('FastAPI Research Report',"={{ 'http://127.0.0.1:8000/v1/research/runs/' + $json.run_id + '/report' }}",
         '={{ JSON.stringify({}) }}',(4860,140))
    add('Check Research Report','code',{'jsCode':RESEARCH_REPORT},position=(5080,140))
    gate('Research Report Ready?','={{ $json.ready === true }}',(5300,140))
    add('Due Diligence Report','code',{'jsCode':'return [{json:$input.first().json.report}];'},position=(5520,140))
    link('Verified Company','FastAPI Create Research Run')
    link('FastAPI Create Research Run','Check Research Plan')
    link('Check Research Plan','Research Plan Valid?')
    link('Research Plan Valid?','Research Action Needed?')
    link('Research Plan Valid?','Verification Needs Review',1)
    link('Research Action Needed?','FastAPI Research Tool')
    link('FastAPI Research Tool','Check Research Plan')
    link('Research Action Needed?','FastAPI Research Report',1)
    link('FastAPI Research Report','Check Research Report')
    link('Check Research Report','Research Report Ready?')
    link('Research Report Ready?','Due Diligence Report')
    link('Research Report Ready?','Verification Needs Review',1)
    return {'name':original['name'],'nodes':nodes,'connections':connections,'settings':copy.deepcopy(original.get('settings',{}))}
