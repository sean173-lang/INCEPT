/* Dependency-free Tavily result filter for n8n's restricted Code-node VM. */
function parseTavilySources(results, company, retrievedAt) {
  const rejected = {};
  const reject = (reason) => { rejected[reason] = (rejected[reason] || 0) + 1; };
  const normalize = (value) => String(value || '').normalize('NFKD').replace(/\p{Diacritic}/gu, '').toLowerCase();
  const tokens = (value) => normalize(value).match(/[\p{L}\p{N}]+/gu) || [];
  const stop = new Set(['gmbh','ag','se','ug','kg','ohg','kgaa','ev','the','and','und','company','co','group','holding','international','deutschland']);
  const brands = tokens(company?.name).filter((word) => word.length >= 3 && !stop.has(word));
  const purpose = typeof company?.purpose === 'string' ? company.purpose : JSON.stringify(company?.purpose || '');
  const activity = tokens(purpose).filter((word) => word.length >= 5 && !stop.has(word));
  const location = tokens(JSON.stringify([company?.register?.register_court, company?.address]))
    .filter((word) => word.length >= 4 && !/^\d+$/.test(word) && !stop.has(word) && !['strasse','street','road','avenue','berlincharlottenburg'].includes(word));
  const related = (needles, text) => {
    const words = new Set(tokens(text));
    return needles.some((needle) => [...words].some((word) => word === needle ||
      (Math.min(word.length, needle.length) >= 5 && (word.startsWith(needle) || needle.startsWith(word)))));
  };
  const decode = (value) => String(value || '').replace(/&amp;/gi,'&').replace(/&quot;/gi,'"')
    .replace(/&#39;|&apos;/gi,"'").replace(/&lt;/gi,'<').replace(/&gt;/gi,'>').replace(/&nbsp;/gi,' ')
    .replace(/&#(?:x([0-9a-f]+)|(\d+));?/gi, (whole, hex, dec) => {
      const n = parseInt(hex || dec, hex ? 16 : 10);
      try { return Number.isFinite(n) ? String.fromCodePoint(n) : whole; } catch { return whole; }
    });
  const safeUrl = (value) => {
    const match = /^(https?):\/\/([^/?#]+)([^?#]*)(?:\?([^#]*))?(?:#.*)?$/i.exec(String(value || '').trim());
    if (!match || match[2].includes('@')) return null;
    const host = match[2].replace(/:\d+$/, '').toLowerCase().replace(/^www\./, '');
    if (!/^(?=.{1,253}$)[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,63}$/i.test(host) || /\.(local|internal)$/i.test(host)) return null;
    const keys = (match[4] || '').split('&').filter(Boolean).map((part) => {
      const key = part.split('=')[0].replace(/\+/g, ' ');
      try { return decodeURIComponent(key); } catch { return key; }
    });
    if (keys.some((key) => /token|signature|credential|secret|auth/i.test(key))) return null;
    return { raw: String(value).trim(), host, path: match[3] || '/' };
  };
  const sources = [], seen = new Set();
  const social = /(^|\.)(instagram|facebook|linkedin|tiktok|x|twitter|youtube)\.com$/;
  for (const row of Array.isArray(results) ? results : []) {
    const url = safeUrl(row?.url);
    if (!url) { reject('unsafe_or_invalid_url'); continue; }
    const title = decode(row?.title).replace(/[\r\n\t]+/g, ' ').trim().slice(0, 300);
    const content = decode(row?.content).replace(/\r\n?/g, '\n').trim().slice(0, 4000);
    if (!title || !content) { reject('missing_title_or_excerpt'); continue; }
    const brandedHost = url.host.split('.').some((part) => brands.includes(part));
    const brandMatch = brandedHost || related(brands, title + ' ' + content);
    if (!brandMatch) { reject('brand_mismatch'); continue; }
    const context = title + ' ' + content + ' ' + url.host;
    const activityMatch = activity.length > 0 && related(activity, context);
    const locationMatch = location.length > 0 && related(location, context);
    // A company-branded domain is a useful discovery lead even if a short snippet omits the registry's exact activity wording.
    if (!activityMatch && !locationMatch && !brandedHost) { reject('irrelevant_context'); continue; }
    const key = url.host + url.path.replace(/\/$/, '').toLowerCase();
    if (seen.has(key)) { reject('duplicate_url'); continue; }
    seen.add(key);
    const sourceType = social.test(url.host) ? 'social_media' : (brandedHost ? 'company_site_candidate' : 'public_web');
    const confidence = brandedHost && activityMatch && locationMatch ? 'medium' : 'low';
    const published = typeof row.published_date === 'string' && Number.isFinite(Date.parse(row.published_date)) ? row.published_date.slice(0, 40) : null;
    sources.push({
      id: 'WEB-' + (sources.length + 1), kind: 'web_lead', source_type: sourceType,
      title, url: url.raw, content, retrieved_at: retrievedAt, published_at: published,
      confidence,
      confidence_note: sourceType === 'company_site_candidate'
        ? 'Brand-domain signal; ownership by the registered legal entity was not independently verified.'
        : 'Unverified public web material; source identity and claims were not independently verified.',
      relevance_signals: [brandMatch ? 'company-name or brand-domain match' : null, activityMatch ? 'business-activity match' : null, locationMatch ? 'location match' : null].filter(Boolean),
      tavily_score: Number.isFinite(Number(row.score)) ? Number(row.score) : null,
    });
    if (sources.length >= 5) break;
  }
  return { sources, raw_result_count: Array.isArray(results) ? results.length : 0, rejected_reasons: rejected };
}
