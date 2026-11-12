/* Safe, deliberately small Markdown renderer for the validated company report. */
function escapeHtml(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  })[char]);
}

function safeHref(value) {
  const match = /^(https?):\/\/([^/?#\\\s]+)([/?#][^\s]*)?$/i.exec(String(value));
  if (!match || match[2].includes('@') || !/^[A-Za-z0-9.-]+(?::\d{1,5})?$/.test(match[2])) return null;
  const hostname = match[2].replace(/:\d+$/, '');
  if (!hostname || hostname.startsWith('.') || hostname.endsWith('.') || hostname.includes('..')) return null;
  return match[1].toLowerCase() + '://' + match[2] + (match[3] || '');
}

function inlineMarkdown(text) {
  const links = [];
  const source = String(text).replace(/[\u0000-\u001f\u007f]/g, ' ');
  const tokenized = source.replace(/\[([^\]]{1,600})\]\(([^)\s]{1,2048})\)|<(https?:\/\/[^\s<>]{1,2048})>/gi,
    (match, label, target, bareUrl) => {
      const href = safeHref(target || bareUrl);
      if (!href) return escapeHtml(match);
      const textLabel = label || 'Open source ↗';
      const token = `\uE000${links.length}\uE001`;
      links.push(`<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(textLabel)}</a>`);
      return token;
    });
  let html = escapeHtml(tokenized)
    .replace(/`([^`\n]{1,500})`/g, '<code>$1</code>')
    .replace(/\*\*([^*\n]{1,1000})\*\*/g, '<strong>$1</strong>')
    .replace(/(^|[^*])\*([^*\n]{1,1000})\*(?!\*)/g, '$1<em>$2</em>');
  return html.replace(/\uE000(\d+)\uE001/g, (_match, index) => links[Number(index)] || '');
}

function markdownToSafeHtml(markdown) {
  const output = [];
  let paragraph = [];
  let list = false;
  let section = false;
  const closeParagraph = () => {
    if (paragraph.length) output.push(`<p>${paragraph.map(inlineMarkdown).join('<br>')}</p>`);
    paragraph = [];
  };
  const closeList = () => { if (list) output.push('</ul>'); list = false; };
  const closeSection = () => {
    closeParagraph(); closeList();
    if (section) output.push('</section>');
    section = false;
  };
  for (const rawLine of String(markdown || '').split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) { closeParagraph(); closeList(); continue; }
    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      closeParagraph(); closeList();
      const level = heading[1].length;
      if (level === 2) {
        closeSection();
        output.push('<section class="cs-report-section">');
        section = true;
      } else if (level === 1 && section) {
        closeSection();
      }
      output.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
      continue;
    }
    const bullet = /^[-*+]\s+(.+)$/.exec(line);
    if (bullet) {
      closeParagraph();
      if (!list) { output.push('<ul>'); list = true; }
      output.push(`<li>${inlineMarkdown(bullet[1])}</li>`);
      continue;
    }
    closeList(); paragraph.push(line);
  }
  closeSection(); closeParagraph(); closeList();
  return output.join('\n');
}

function renderCompanyScopeResult(item, themeCss) {
  const result = item || {};
  const safeCss = String(themeCss || '').replace(/<\/style/gi, '<\\/style');
  const style = safeCss ? `<style>${safeCss}</style>` : '';
  if (result.ok !== true || typeof result.report_markdown !== 'string' || result.validation?.source_ids_valid !== true) {
    const message = result.message || 'The report was not accepted. No report is shown as complete.';
    const code = result.error_code || 'research_not_completed';
    const stage = result.failed_step || 'Research';
    return `${style}<main class="cs-report-shell cs-report-error"><header class="cs-report-header"><p class="cs-report-eyebrow">CompanyScope · Research status</p><h1>Research not completed</h1><p class="cs-report-status">No validated report was produced.</p></header><section class="cs-report-card"><h2>${escapeHtml(stage)}</h2><p>${escapeHtml(message)}</p><p class="cs-report-code">Reference: ${escapeHtml(code)}</p>${Array.isArray(result.candidates) && result.candidates.length ? `<h2>Company candidates</h2><ul>${result.candidates.map((candidate) => `<li>${escapeHtml(typeof candidate === 'string' ? candidate : [candidate.name, candidate.register_identifier, candidate.register_court].filter(Boolean).join(' · '))}</li>`).join('')}</ul>` : ''}</section></main>`;
  }
  const company = result.company && result.company.name ? result.company.name : 'Company report';
  const file = result.report_file ? `<p class="cs-report-file">Markdown report saved: <code>${escapeHtml(result.report_file)}</code></p>` : '';
  return `${style}<main class="cs-report-shell"><header class="cs-report-header"><p class="cs-report-eyebrow">CompanyScope · Research complete</p><h1>${escapeHtml(company)}</h1><p class="cs-report-status"><span aria-hidden="true">●</span> Validated report ready for review</p></header><article class="cs-report-body" aria-label="Generated company research report">${markdownToSafeHtml(result.report_markdown)}</article>${file}<footer class="cs-report-footer">Source IDs and citation types passed automated validation. Semantic support remains subject to human review.</footer></main>`;
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = { escapeHtml, safeHref, markdownToSafeHtml, renderCompanyScopeResult };
}
