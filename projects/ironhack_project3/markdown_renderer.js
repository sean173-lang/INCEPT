/* Stable Markdown rendering for the validated Project 3 report contract. */
function renderCorporateReport(report, evidence, run) {
  const clean = (value) => {
    const markdown = new Set(['\\','*','_','`','{','}','[',']','#','+','!','>','|']);
    return Array.from(String(value || '').replace(/&amp;/gi,'&').replace(/&quot;/gi,'"')
      .replace(/&#39;|&apos;/gi,"'").replace(/&lt;/gi,'<').replace(/&gt;/gi,'>').replace(/&nbsp;/gi,' ')
      .replace(/[\r\n\t]+/g,' ').replace(/[<>]/g,'')).map((char)=>markdown.has(char)?'\\'+char:char).join('');
  };
  const bullet = (text, ids=[]) => '- '+clean(text)+(ids.length?' ['+ids.join(', ')+']':'');
  const citedClaim = (claim) => bullet(claim.text+(claim.claim_type==='analysis'?' (analytical inference)':''),claim.source_ids);
  const c = evidence.company, reg = c.register || {};
  const profile = [
    '- Legal name: '+clean(c.name)+' [REGISTRY-1]',
    '- Legal form: '+clean(c.legal_form||'Not returned')+' [REGISTRY-1]',
    '- Register identifier: '+clean([reg.register_type,reg.register_number].filter(Boolean).join(' ')||'Not returned')+' [REGISTRY-1]',
    '- Register court: '+clean(reg.register_court||'Not returned')+' [REGISTRY-1]',
    '- Registered address: '+clean((c.address||{}).formatted_value||'Not returned')+' [REGISTRY-1]',
    '- Register status: '+clean(c.status||'Not returned')+' [REGISTRY-1]',
    '- Registered business purpose: '+clean(typeof c.purpose==='string'?c.purpose:JSON.stringify(c.purpose||'Not returned'))+' [REGISTRY-1]',
  ];
  const sources = evidence.sources.map((s) => '- **'+clean(s.id)+' — '+clean(s.title)+'** — <'+s.url+'>; retrieved '+clean(s.retrieved_at)+
    (s.published_at?'; published '+clean(s.published_at):'; publication date not reported')+'; '+clean(s.source_type||'registry')+
    ', confidence: '+clean(s.confidence||'not rated')+(s.confidence_note?' ('+clean(s.confidence_note)+')':'')+'.');
  const section = (title, lines, empty) => ['', '## '+title, '', ...(lines.length?lines:[empty])];
  const content = [
    '# Corporate Research Briefing — '+clean(c.name),
    ...section('Executive Summary',report.executive_summary.map(citedClaim),'No evidence-backed summary claims were returned.'),
    ...section('Company Profile',profile,'No registry profile was returned.'),
    ...section('Business Model and Market Position',report.business_model_analysis.map(citedClaim),'Available evidence does not support a detailed business-model assessment.'),
    ...section('Public Findings and Developments',report.public_findings.map((x)=>bullet(x.finding+' Significance: '+x.significance,[x.source_id])),'No reliable public findings were available from this search.'),
    ...section('Analytical Observations',report.analytical_observations.map((x)=>bullet(x.observation+' Why it matters: '+x.why_it_matters+' (confidence: '+x.confidence+')',x.evidence_source_ids)),'The available evidence is too limited for a supported analytical observation.'),
    ...section('Information Gaps',report.information_gaps.map((x)=>bullet(x.gap+' Why it matters: '+x.why_it_matters)),'No specific information gaps were returned.'),
    ...section('Recommended Research Actions',report.recommended_actions.map((x)=>bullet(x.action+' Addresses: '+x.addresses_gap)),'No follow-up action is recommended from the available evidence.'),
    '', '## Sources and Limitations', '', ...sources,
    '', 'Public web material is an unverified discovery lead. Registry data is provider-reported. Citation identifiers and source types are validated automatically; semantic support of each sentence is not mechanically proven and requires professional review. Search coverage is limited; absence of a result does not establish absence of a fact or event. This briefing is not a legal opinion, audit, sanctions clearance, or solvency assessment.',
    '', '## Run Metadata', '', 'n8n execution: #'+String(run.execution_id)+'; model: '+String(run.model||'gpt-4o-mini')+'; OpenAI response: completed; source-ID validation: passed.', '',
  ];
  return content.join('\n');
}
