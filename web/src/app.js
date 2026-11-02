import {createCompanyCompletion} from './completion.js?v=20261101-universe-35';
import {resultHeadline} from './feed.js';
import {businessHtml,trajectoryHtml} from './company.js?v=20261101-universe-35';
import {createTickerSearch} from './search.js';
import {createAnalysisProgress} from './analysis.js?v=20261101-progressive-3';
const $ = s => document.querySelector(s);
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const icon = name => `<svg aria-hidden="true"><use href="#i-${name}"/></svg>`;
const safeUrl = value => { try { const u = new URL(value); return ['https:','http:'].includes(u.protocol) ? esc(u.href) : '#'; } catch { return '#'; } };
const number = value => value == null ? '—' : Number(value).toLocaleString('en-IN', {maximumFractionDigits:1});
const date = value => value ? new Date(value).toLocaleDateString('en-IN', {day:'numeric',month:'short',year:'numeric',timeZone:'Asia/Kolkata'}) : 'Date not disclosed';
const period = value => value ? new Date(value).toLocaleDateString('en-IN', {month:'short',year:'numeric',timeZone:'Asia/Kolkata'}) : 'Period not established';
const labels = {revenue:'Revenue',ebitda:'EBITDA',pbt:'PBT',pat:'PAT',revenue_growth_yoy:'Revenue growth · YoY',revenue_growth_qoq:'Revenue growth · QoQ',ebitda_margin:'EBITDA margin',results:'Results',management_change:'Management',litigation:'Litigation',fund_raise:'Capital raise','M&A':'M&A',price:'Price move',volume:'Volume spike',credit_rating:'Credit rating',unclassified:'Routine'};
const state = {digest:null,filter:'all',ticker:'INFY',company:null,polling:new Set(),citations:[],requestId:0,digestRequest:0,resetVersion:0,startingAnalysis:new Set()};
async function api(path, options={}) { const r = await fetch(path,{...options,headers:{'Content-Type':'application/json',...options.headers},signal:AbortSignal.timeout(12000)}); const data = await r.json(); if(!r.ok)throw new Error(data.detail || `Request failed (${r.status})`); return data; }
function status(selector,text,error=false){const el=$(selector);el.textContent=text;el.className=`status-line${error?' error':''}`;}
function toast(text){$('#toast').textContent=text;$('#toast').hidden=false;setTimeout(()=>$('#toast').hidden=true,3500);}
function delta(value){if(value==null)return '<span class="delta neutral">—</span>';return `<span class="delta ${value<0?'negative':''}">${value>0?'+':''}${number(value)}%</span>`;}
function showView(view,{smooth=false,updateHash=true}={}) {
  document.querySelectorAll('.view').forEach(el=>el.hidden=el.id!==`view-${view}`);
  document.querySelectorAll('[data-view]').forEach(el=>{const selected=el.dataset.view===view;el.classList.toggle('active',selected);if(selected)el.setAttribute('aria-current','page');else el.removeAttribute('aria-current');});
  $('#breadcrumb').textContent=view==='digest'?'Push Digest':'Pull Deep Dive';
  if(updateHash&&location.hash!==`#${view}`)history.pushState(null,'',`#${view}`);
  window.scrollTo({top:0,behavior:smooth&&!matchMedia('(prefers-reduced-motion: reduce)').matches?'smooth':'instant'});
  if(view==='research'&&!state.company)loadCompany(state.ticker);
}
function resetHome(event) {
  if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  event.preventDefault();
  state.resetVersion++;state.requestId++;state.filter='all';state.ticker='INFY';state.company=null;
  $('#window-select').value='24';
  document.querySelectorAll('[data-filter]').forEach(el=>el.classList.toggle('active',el.dataset.filter==='all'));
  document.querySelectorAll('details[open]').forEach(el=>el.open=false);
  if($('#evidence-dialog').open)$('#evidence-dialog').close();
  if($('#preferences-dialog').open)$('#preferences-dialog').close();
  $('#research-content').replaceChildren();$('#research-status').textContent='';$('#toast').hidden=true;
  tickerSearch.reset();analysisProgress.clearSelection();showView('digest',{smooth:true});loadDigest();
}
document.querySelectorAll('[data-home]').forEach(el=>el.addEventListener('click',resetHome));
document.querySelectorAll('[data-view]').forEach(el=>el.onclick=()=>showView(el.dataset.view));
window.addEventListener('hashchange',()=>{if(['digest','research'].includes(location.hash.slice(1)))showView(location.hash.slice(1),{updateHash:false});});
function resultTable(snapshot){if(!snapshot?.metrics)return '<p class="muted">Headline extraction is queued. Values appear when supported by the filing or saved financial table.</p>';return `<table class="results-table"><thead><tr><th>₹ crore · ${esc(snapshot.latest_period)}</th><th>Actual</th><th>QoQ</th><th>YoY</th></tr></thead><tbody>${snapshot.metrics.map(m=>`<tr><td>${esc(m.label)}${m.derived?' *':m.source_type==='standardized_table'?' †':''}</td><td>${number(m.value)}</td><td>${delta(m.qoq)}</td><td>${delta(m.yoy)}</td></tr>`).join('')}</tbody></table>${snapshot.metrics.some(m=>m.derived)?'<p class="muted">* Derived EBITDA; see the company snapshot for method.</p>':''}${snapshot.source_type==='mixed'?'<p class="muted">† Standardized table. Other values verified against the filing.</p>':''}`;}
function conciseFiling(item) {
  let text=String(item.reason||'').replace(/^.*?has (?:informed|submitted to) the Exchange(?: about| regarding)?\s*/i,'').replace(/^.*?has submitted.*?Exchange\s*[:,.-]?\s*/i,'').trim();
  if(!text||text.toLowerCase()===item.title.toLowerCase()||/^(change in management|potentially material disclosure)/i.test(text))return '';
  return text.length>180?`${text.slice(0,177)}…`:text;
}
const compactNumber=value=>Number(value).toLocaleString('en-US',{notation:'compact',maximumFractionDigits:2});
function signalBody(item) {
  if(item.category==='results')return `<h3>${esc(resultHeadline(item,number))}</h3>${resultTable(item.financials)}${item.financials?.source_type==='standardized_table'?'<span class="filing-data-source">Standardized financial table</span>':''}`;
  if(item.category==='management_change') {
    const m=item.management;
    return m?`<dl class="management-fields"><div><dt>Person</dt><dd>${esc(m.person)}</dd></div><div><dt>Executive role</dt><dd>${esc(m.role)}</dd></div><div><dt>Action</dt><dd>${esc(m.action)}</dd></div></dl>`:`<h3>${esc(conciseFiling(item)||'Executive & Key Managerial Personnel change filed')}</h3>`;
  }
  const m=item.market;
  if(item.category==='volume'&&m)return `<h3>Volume ${Number(m.multiple).toFixed(2)}× of 20-day avg</h3><p class="market-detail">Traded: <strong>${compactNumber(m.volume)}</strong> vs Avg: <strong>${compactNumber(m.average_volume)}</strong></p>`;
  if(item.category==='price'&&m)return `<h3>Close ${m.change_percent>0?'+':''}${Number(m.change_percent).toFixed(2)}%</h3><p class="market-detail">₹${number(m.close)} vs ₹${number(m.previous_close)} previous close</p>`;
  const summary=conciseFiling(item);
  const generic=/^(general updates?|updates?|announcement|press release)$/i.test(item.title.trim());
  return generic&&summary?`<h3>${esc(summary)}</h3>`:`<h3>${esc(item.title)}</h3>${summary?`<p>${esc(summary)}</p>`:''}`;
}
function badgeTone(item){return item.category==='volume'?'badge-amber':item.category==='results'?'badge-blue':item.category==='management_change'?'badge-purple':item.category==='price'?((item.market?.change_percent??0)<0?'badge-crimson':'badge-emerald'):'badge-neutral';}
function card(item){return `<article class="signal-card"><div class="card-inner"><div class="card-meta signal-header"><div class="company-label"><span class="ticker-badge">${esc(item.ticker)}</span><span class="pill ${badgeTone(item)}">${esc(labels[item.category]||item.category||'Signal')}</span></div><button class="deep-dive-button" data-ticker="${esc(item.ticker)}" aria-label="Deep dive into ${esc(item.ticker)}">Deep dive →</button></div><div class="signal-provenance"><time datetime="${esc(item.occurred_at)}">${date(item.occurred_at)}</time>${item.source_url?`<a href="${safeUrl(item.source_url)}" target="_blank" rel="noopener noreferrer" aria-label="Open ${esc(item.ticker)} source">Source ${icon('link')}</a>`:''}${item.related_sources?.length>1?`<span>· ${item.related_sources.length} filings</span>`:''}</div>${signalBody(item)}</div></article>`;}

function openCompany(ticker){loadCompany(ticker,false,true);showView('research');}
function bindTickers(){document.querySelectorAll('[data-ticker]').forEach(el=>{el.onclick=()=>openCompany(el.dataset.ticker);if(el.getAttribute('role')==='button')el.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();openCompany(el.dataset.ticker);}};});}
function renderDigest(){const d=state.digest;if(!d)return;$('#portfolio-size').textContent=d.portfolio.length;$('#portfolio-count').textContent=d.portfolio.length;const signals=d.items.filter(i=>state.filter==='all'||(state.filter==='market'?['price','volume'].includes(i.category):i.category===state.filter));$('#signal-count').textContent=d.items.length;$('#overview').innerHTML=`<span><strong>${d.material_count}</strong> Material Alerts</span><span><strong>${d.items.filter(i=>['price','volume'].includes(i.category)).length}</strong> Market Moves</span><span><strong>${d.routine.length}</strong> Routine Filtered</span>`;$('#feed').innerHTML=signals.length?signals.map(card).join(''):`<div class="empty-state"><span class="empty-icon">${icon('check')}</span><h3>${state.filter==='all'?'Nothing new needs your attention.':'No matching signals in this window.'}</h3><p>${d.covered_count?'The feed stays quiet when saved data contains no matching triggers. Explore a longer window or research a company.':'Refresh your portfolio to begin tracking exchange filings and EOD moves.'}</p><button class="button secondary" id="longer-window">Explore last 7 days ${icon('arrow')}</button></div>`;$('#routine-count').textContent=d.routine.length;$('#routine-list').innerHTML=d.routine.length?d.routine.map(i=>`<div class="routine-row"><div><strong>${esc(i.ticker)} · ${esc(labels[i.category]||i.category.replaceAll('_',' '))}</strong>${esc(i.title)}</div><a href="${safeUrl(i.source_url)}" target="_blank" rel="noopener noreferrer">${icon('link')}</a></div>`).join(''):'<p class="muted">No lower-priority filings in this window.</p>';$('#watchlist').innerHTML=d.portfolio.map(c=>`<div class="watch-row" role="button" tabindex="0" data-ticker="${esc(c.ticker)}"><div><strong>${esc(c.ticker)}</strong><span class="watch-sector">${esc(c.sector)}</span></div><div class="watch-price">${number(c.close)}<span class="watch-change ${c.change<0?'negative':'positive'}">${c.change==null?'Not refreshed':`${c.change>0?'+':''}${number(c.change)}%`}</span></div></div>`).join('');$('#longer-window')?.addEventListener('click',()=>{$('#window-select').value='168';loadDigest();});const warnings=d.warnings.length?` · ${d.warnings.length} source gaps`:'';status('#digest-status',`Latest refresh ${d.refreshed_at?date(d.refreshed_at):'pending'} · ${d.covered_count}/${d.portfolio.length} portfolio companies covered${warnings}`);$('#price-threshold').value=d.settings.price_percent;$('#volume-threshold').value=d.settings.volume_multiple;bindTickers();}
async function loadDigest(){const id=++state.digestRequest;try{const digest=await api(`/api/digest?hours=${$('#window-select').value}`);if(id!==state.digestRequest)return;state.digest=digest;renderDigest();}catch(e){if(id===state.digestRequest)status('#digest-status',e.message,true);}}
$('#window-select').onchange=loadDigest;
$('#digest-filters').onclick=e=>{const button=e.target.closest('[data-filter]');if(!button)return;state.filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(el=>el.classList.toggle('active',el===button));renderDigest();};
$('#preferences-button').onclick=()=>{
  if(state.digest){$('#price-threshold').value=state.digest.settings.price_percent;$('#volume-threshold').value=state.digest.settings.volume_multiple;}
  $('#settings-status').textContent='Applied to saved market bars.';
  $('#preferences-dialog').showModal();
};
$('#close-preferences').onclick=()=>$('#preferences-dialog').close();
$('#preferences-dialog').addEventListener('click',event=>{
  if(event.target!==event.currentTarget)return;
  const bounds=event.currentTarget.getBoundingClientRect();
  if(event.clientX<bounds.left||event.clientX>bounds.right||event.clientY<bounds.top||event.clientY>bounds.bottom)event.currentTarget.close();
});
$('#settings-form').onsubmit=async e=>{e.preventDefault();try{await api('/api/preferences',{method:'PUT',body:JSON.stringify({price_percent:Number($('#price-threshold').value),volume_multiple:Number($('#volume-threshold').value)})});$('#settings-status').textContent='Saved. Applied immediately to cached EOD bars.';await loadDigest();$('#preferences-dialog').close();toast('Alert preferences saved');}catch(err){$('#settings-status').textContent=err.message;}};
$('#refresh-button').onclick=async()=>{const b=$('#refresh-button');b.disabled=true;b.innerHTML=`${icon('refresh')} Refreshing`;try{const job=await api('/api/refresh',{method:'POST',body:'{}'});status('#digest-status','Refreshing exchange filings and market data in the background…');await pollJob(job.id,()=>loadDigest());await loadDigest();toast('Portfolio refresh complete');}catch(e){status('#digest-status',e.message,true);}finally{b.disabled=false;b.innerHTML=`${icon('refresh')} Refresh`;}};
function snapshotHtml(snapshot){if(!snapshot)return `<div class="panel snapshot-panel"><h2>Financial snapshot</h2><p class="muted" role="status">Loading financial tables…</p><div class="section-skeleton" aria-hidden="true"></div></div>`;return `<div class="panel snapshot-panel"><div class="section-heading"><h2>Financial snapshot</h2><span class="pill results">${esc(snapshot.basis)}</span></div><p class="muted">${esc(snapshot.latest_period)} · ₹ crore · Standardized financials</p>${resultTable(snapshot)}<div class="snapshot-note"><details><summary class="source-button">Source & methodology</summary><p>${esc(snapshot.note)}</p></details><a class="text-button" href="${safeUrl(snapshot.source_url)}" target="_blank" rel="noopener noreferrer">Open financial table ${icon('link')}</a></div>${snapshot.history?.length?`<details class="source-list"><summary class="text-button">Last four quarters</summary><table class="snapshot-table"><thead><tr><th>Quarter</th><th>Revenue</th><th>PAT</th></tr></thead><tbody>${snapshot.history.slice(-4).map(q=>`<tr><td>${esc(q.label)}</td><td>${number(q.revenue)}</td><td>${number(q.pat)}</td></tr>`).join('')}</tbody></table></details>`:''}</div>`;}
function citeButton(citation){const id=state.citations.push(citation)-1;return `<button class="source-button" data-cite="${id}">${citation.source_type==='standardized_table'?'Financial table':`Transcript · page ${citation.page??'—'}`} ${icon('link')}</button>`;}
function financialUnit(unit) {
  return unit==='percent'?'%':unit==='unknown'?'':` ${unit.replaceAll('_',' ')}`;
}
function targetText(n) {
  const target=n.lower!=null&&n.upper!=null?(n.lower===n.upper?number(n.lower):`${number(n.lower)}–${number(n.upper)}`):n.lower!=null?`≥ ${number(n.lower)}`:n.upper!=null?`≤ ${number(n.upper)}`:'Qualitative';
  return `${target}${target==='Qualitative'?'':financialUnit(n.unit)}`;
}
function revisionHtml(items=[]) {
  return items.length?`<details class="guidance-revisions"><summary>Earlier guidance · ${items.length} ${items.length===1?'update':'updates'}</summary>${items.map(n=>`<div class="revision-row"><span>${date(n.stated_on)}</span><strong>${targetText(n)}</strong>${citeButton(n.citation)}</div>`).join('')}</details>`:'';
}
function heroTarget(n) {
  if(n.unit==='percent'&&n.lower!=null&&n.upper!=null&&n.lower!==n.upper){
    const value=v=>Number(v).toLocaleString('en-IN',{minimumFractionDigits:1,maximumFractionDigits:1});
    return `${value(n.lower)}% – ${value(n.upper)}%`;
  }
  return targetText(n);
}
function comparisonHtml(c) {
  const n=c.narrative,actual=c.actual;
  const factors={INR_crore:1,INR_lakh:.01,INR_million:.1,INR_billion:100};
  const converted=actual&&factors[n.unit]&&factors[actual.unit]?actual.value*factors[actual.unit]/factors[n.unit]:actual?.value;
  const suffix=financialUnit(n.unit);
  const metric=(labels[n.metric]||n.metric).replace(' · YoY','').replace(' · QoQ','');
  const fiscalYear=n.period_end?`FY${n.period_end.slice(0,4)}`:'';
  const basis=n.currency_basis==='constant_currency'?' (constant currency)':'';
  const met=c.status==='Met';
  return `<article class="comparison-card verified-comparison"><header class="comparison-hero-heading"><span class="pill ${met?'badge-emerald':'badge-crimson'}">${esc(c.status.toUpperCase())}</span><h3>${esc(fiscalYear)} ${esc(metric)}${esc(basis)}</h3></header><p class="comparison-date">${date(n.stated_on)} → ${period(n.period_end)}</p><div class="comparison-panels"><section class="comparison-panel"><div class="comparison-label">MANAGEMENT GUIDANCE</div><div class="target-number">${heroTarget(n)}</div><blockquote class="evidence-inset guidance-quote">“${esc(n.citation.quote)}”</blockquote>${citeButton(n.citation)}</section><section class="comparison-panel delivery-panel ${met?'delivery-met':'delivery-missed'}"><div class="comparison-label">ACTUAL DELIVERY</div><div class="target-number">${number(converted)}${suffix}</div><blockquote class="evidence-inset delivery-quote">“${esc(actual?.citation.quote)}”</blockquote>${actual?citeButton(actual.citation):''}</section></div><div class="comparison-explanation">${esc(c.explanation)}</div>${revisionHtml(c.prior_guidance)}</article>`;
}
function activeGuidanceHtml(c) {
  const n=c.narrative;
  return `<article class="active-guidance-card"><header class="comparison-hero-heading"><span class="pill badge-blue">ACTIVE</span><h3>${esc(labels[n.metric]||n.metric)}</h3></header><p class="comparison-date">Target period ends ${date(n.period_end)}${n.currency_basis==='constant_currency'?' · constant currency':''}</p><section class="comparison-panel"><div class="comparison-label">MANAGEMENT GUIDANCE</div><div class="target-number">${heroTarget(n)}</div><blockquote class="evidence-inset guidance-quote">“${esc(n.citation.quote)}”</blockquote>${citeButton(n.citation)}</section>${revisionHtml(c.prior_guidance)}</article>`;
}

function guidanceHtml(r) {
  const review=r?.guidance_review;
  const completed=review?.completed||[],active=review?.active||[],context=review?.context||[];
  const label=review?.period?.label||'Previous financial year';
  const window=review?`${date(review.period.start)} – ${date(review.period.end)}`:'Historical guidance will be matched against the completed financial year.';
  const commentary=!completed.length?context.filter(c=>c.narrative.citation?.quote).slice(0,3):[];
  const notes=context.filter(c=>!commentary.includes(c));
  const commentaryCard=commentary.length?`<section class="management-commentary"><h2>Management Commentary</h2><p class="muted">Sourced statements · qualitative context, not performance verdicts</p>${commentary.map(c=>`<article><div class="card-meta"><span>${date(c.narrative.stated_on)}</span><span>${esc(labels[c.narrative.metric]||c.narrative.metric)}</span></div><blockquote>“${esc(c.narrative.citation.quote)}”</blockquote>${citeButton(c.narrative.citation)}</article>`).join('')}</section>`:'';
  const delivery=completed.length?`<section class="guidance-review"><div class="section-heading"><h2>${esc(label)} delivery</h2><span class="count">${completed.length}</span></div><p class="review-subtitle">${esc(window)}</p><div class="review-score"><span>${review.met} Met</span><span>${review.missed} Missed</span></div>${completed.map(comparisonHtml).join('')}</section>`:commentaryCard||`<div class="research-prompt"><span>${r?'No source-matched historical comparison saved.':'Management research available on demand.'}</span><button class="text-button" id="start-research">${r?'Review sources':'Analyze management narrative'} ${icon('arrow')}</button></div>`;
  return `${delivery}${active.length?`<section class="active-guidance"><div class="section-heading"><h2>Active Guidance</h2><span class="count">${active.length}</span></div>${active.map(activeGuidanceHtml).join('')}</section>`:''}${r?`<details class="routine-panel guidance-context"><summary><span>Additional statements & context <span class="count">${notes.length}</span></span>${icon('chevron')}</summary>${notes.map(c=>`<article class="guidance-context-item"><div class="card-meta"><span>${date(c.narrative.stated_on)}</span><span>${esc(c.context_reason)}</span></div><p class="quote">“${esc(c.narrative.citation.quote)}”</p>${citeButton(c.narrative.citation)}</article>`).join('')}<p class="muted">${r.coverage==='partial'?'Focused review; some source sections remain unreviewed.':'Selected source sections reviewed.'} Only supported comparisons are graded.</p></details>`:''}`;
}

function renderCompany(data) {
  state.company=data;state.citations=[];
  const r=data.research;
  $('#research-content').innerHTML=`<div class="company-heading"><div class="company-identity"><div class="company-status-row"><span class="ticker-badge">${esc(data.ticker)}.NS</span><span class="analysis-status-badge ${r?'analysed':'unanalysed'}">${r?`Last analysed: ${date(r.generated_at)}`:'Not yet analysed'}</span><button class="button ${r?'secondary':'primary'} company-analysis-action" id="rerun-research">${r?`${icon('refresh')} Update analysis`:'Analyse now'}</button></div><h2>${esc(data.name||data.ticker)}</h2><p class="subtitle">${esc(data.sector==='NSE-listed company'?'Listed company':data.sector||'Listed company')} · NSE</p></div></div><div class="research-stack">${businessHtml(data.business,{esc,date,citeButton})}${snapshotHtml(data.snapshot)}${trajectoryHtml(data.trajectory,{esc,number})|| (data.context_pending?'<section class="panel trajectory-panel"><h2>5-year trajectory</h2><p class="muted" role="status">Calculating annual financial trajectory…</p><div class="section-skeleton" aria-hidden="true"></div></section>':'')}<section class="narrative-section"><div class="section-heading"><h2>Narrative vs. Numbers</h2></div><div id="narrative-progress-slot">${!r&&!data.research_availability?'<p class="narrative-awaiting" id="narrative-awaiting" role="status">Preparing primary-source analysis…</p>':''}</div>${r?guidanceHtml(r):data.research_availability?'<p class="quiet-empty">Primary transcripts are not available in the published source archive.</p>':''}</section>${r?.documents?.length?`<details class="panel source-list"><summary class="text-button">Source library · ${r.documents.length} documents</summary>${r.documents.map(d=>`<a href="${safeUrl(d.url)}" target="_blank" rel="noopener noreferrer">${esc(d.kind.replaceAll('_',' '))} · ${esc(d.title.replace(/AI Summary|PPT|REC|from bse/g,'').trim().slice(0,55))} ${icon('link')}</a>`).join('')}</details>`:''}</div>`;
  analysisProgress.mount($('#narrative-progress-slot'));
  $('#start-research')?.addEventListener('click',()=>startResearch(data.ticker));
  $('#rerun-research').onclick=()=>startResearch(data.ticker);
  $('#refresh-business')?.addEventListener('click',()=>ensureBusiness(data.ticker,true));
  document.querySelectorAll('[data-cite]').forEach(b=>b.onclick=()=>showEvidence(state.citations[Number(b.dataset.cite)]));
  analysisProgress.select(data.ticker);analysisProgress.track(data.analysis_job);analysisProgress.syncButtons();
}
const businessLoads=new Set();
async function ensureBusiness(ticker,refresh=false) {
  if(businessLoads.has(ticker))return;
  businessLoads.add(ticker);
  const previousSaved=refresh&&state.company?.ticker===ticker?state.company.business?.generated_at:null;
  const button=$('#refresh-business');if(button&&state.ticker===ticker){button.disabled=true;button.textContent='Refreshing company profile…';}
  try {
    await api(`/api/company/${encodeURIComponent(ticker)}/business${refresh?'?refresh=true':''}`,{method:'POST',body:'{}'});
    for(let attempt=0;attempt<50;attempt++) {
      const data=await api(`/api/company/${encodeURIComponent(ticker)}`);
      if(data.business&&(!previousSaved||data.business.generated_at!==previousSaved)){if(state.ticker===ticker)renderCompany(data);break;}
      await new Promise(resolve=>setTimeout(resolve,1000));
    }
  } catch {
    if(state.ticker===ticker){const note=$('#business-progress');if(note)note.innerHTML=`<a class="source-button" href="https://www.screener.in/company/${encodeURIComponent(ticker)}/" target="_blank" rel="noopener noreferrer">View company profile ↗</a>`;}
  } finally {businessLoads.delete(ticker);if(button?.isConnected){button.disabled=false;button.textContent='Refresh company profile';}}
}
async function loadCompany(ticker,_autoStart=false,recordSearch=false){ticker=ticker.trim().toUpperCase().replace(/\.NS$/,'');if(!/^[A-Z0-9][A-Z0-9&-]{0,24}$/.test(ticker)){status('#research-status','Enter an NSE symbol, for example INFY or DIXON.NS.',true);return;}tickerSearch.close();state.ticker=ticker;analysisProgress.select(ticker);$('#ticker-input').value=ticker;const id=++state.requestId;status('#research-status',`Loading saved ${ticker} intelligence…`);try{const data=await api(`/api/company/${encodeURIComponent(ticker)}?opened=true`);if(id!==state.requestId)return;renderCompany(data);ensureComplete(data);if(recordSearch)tickerSearch.remember(data);status('#research-status','');}catch(e){if(id===state.requestId)status('#research-status',e.message,true);}}
$('#research-form').onsubmit=e=>{e.preventDefault();loadCompany(tickerSearch.resolve(),true,true);};
async function pollJob(id,onProgress){if(state.polling.has(id))return;state.polling.add(id);try{for(let attempt=0;attempt<240;attempt++){const job=await api(`/api/jobs/${id}`);await onProgress?.(job);if(job.status==='completed')return job;if(job.status==='failed')throw new Error(job.error||'Source processing failed. Saved results are preserved.');await new Promise(resolve=>setTimeout(resolve,1500));}throw new Error('Analysis is still running. You can return to the saved view.');}finally{state.polling.delete(id);}}
async function startResearch(ticker) {
  if(state.startingAnalysis.has(ticker)||analysisProgress.isActive(ticker)){analysisProgress.select(ticker);return;}
  state.startingAnalysis.add(ticker);
  for(const id of ['start-research','rerun-research']){const button=document.getElementById(id);if(button){button.disabled=true;button.textContent='Starting analysis…';}}
  try {
    const job=await api('/api/research',{method:'POST',body:JSON.stringify({ticker,max_documents:6,max_calls:6})});
    analysisProgress.select(ticker);analysisProgress.track(job);
    if(state.ticker===ticker)status('#research-status','Analysis is running in the background. Your financial snapshot remains available.');
  } catch(error) {
    if(state.ticker===ticker)status('#research-status',error.message,true);
    analysisProgress.syncButtons();
  } finally {state.startingAnalysis.delete(ticker);}
}
async function showEvidence(c){$('#evidence-content').innerHTML=`<blockquote>${esc(c.quote)}</blockquote><p class="muted">${c.source_type==='standardized_table'?'Standardized financial table':'Original document'}${c.page?` · PDF page ${c.page}`:''}</p><a class="button secondary" href="${safeUrl(c.url)}" target="_blank" rel="noopener noreferrer">Open source ${icon('link')}</a><div id="page-context"></div>`;$('#evidence-dialog').showModal();if(c.page&&c.document_id&&!c.document_id.startsWith('table:')){try{const d=await api(`/api/evidence/${c.document_id}?page=${c.page}`);$('#page-context').innerHTML=`<details><summary class="source-button">Show full page context</summary><pre>${esc(d.page.text)}</pre></details>`;}catch{/* The original source remains available. */}}}
$('#close-evidence').onclick=()=>$('#evidence-dialog').close();$('#evidence-dialog').onclick=e=>{if(e.target===$('#evidence-dialog'))$('#evidence-dialog').close();};
$('#briefing-date').textContent=new Date().toLocaleDateString('en-IN',{weekday:'long',day:'numeric',month:'long',year:'numeric',timeZone:'Asia/Kolkata'}).toUpperCase();
const tickerSearch=createTickerSearch({api,onChoose:ticker=>{showView('research');loadCompany(ticker,true,true);}});
const analysisProgress=createAnalysisProgress({
  api,
  onSnapshot:async ticker=>{
    if(state.ticker!==ticker||$('#view-research').hidden)return;
    try{const data=await api(`/api/company/${encodeURIComponent(ticker)}`);if(state.ticker===ticker&&!$('#view-research').hidden){renderCompany(data);if(data.snapshot||data.research)tickerSearch.remember(data);}}catch{/* The progress card reconnects independently of the saved view. */}
  },
  onOpen:ticker=>{showView('research');loadCompany(ticker,false,true);},
  onRetry:ticker=>startResearch(ticker)
});
const ensureComplete=createCompanyCompletion({
  api,
  onJob:job=>analysisProgress.track(job),
  onData:renderCompany,
  isCurrent:ticker=>state.ticker===ticker&&!$('#view-research').hidden,
  onNotice:()=>status('#research-status','Saved sections remain available. Reopen the company to reconnect to missing sections.')
});
analysisProgress.restore();
bindTickers();loadDigest();if(location.hash==='#research')showView('research');
