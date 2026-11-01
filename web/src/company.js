export function businessHtml(business,{esc,date}) {
  const heading='<div class="section-heading"><h2>Business snapshot</h2><span class="section-kicker">COMPANY PROFILE</span></div>';
  if(!business||(business.description&&typeof business.description!=='string'))return `<section class="panel business-panel" aria-live="polite">${heading}<p class="muted" id="business-progress">Loading company profile…</p></section>`;
  const source=`<a class="source-button" href="${esc(business.source_url)}" target="_blank" rel="noopener noreferrer">Screener company profile ↗</a>`;
  if(!business.description)return `<section class="panel business-panel">${heading}<p class="muted">Explore the company’s business and products in its published profile.</p>${source}<button class="text-button" id="refresh-business">Refresh company profile</button></section>`;
  const list=items=>`<ul class="profile-facts">${items.map(text=>`<li>${esc(text)}</li>`).join('')}</ul>`;
  return `<section class="panel business-panel">${heading}<p class="profile-description">${esc(business.description)}</p>${business.products?.length?`<div class="business-detail"><h3>Products & brands</h3>${list(business.products)}</div>`:''}${business.segments?.length?`<div class="business-detail"><h3>Business segments</h3>${list(business.segments)}</div>`:''}${business.revenue_mix?.length?`<div class="business-detail"><h3>Revenue segments · as reported</h3>${list(business.revenue_mix)}</div>`:''}<div class="profile-source">${source}<span>Saved ${date(business.generated_at)}</span></div><details class="business-method"><summary>Profile coverage</summary><p>${esc(business.note)} Only publicly disclosed profile details are shown.</p><button class="text-button" id="refresh-business">Refresh company profile</button></details></section>`;
}

export function trajectoryHtml(trajectory,{esc,number}) {
  const rows=Array.isArray(trajectory?.rows)?trajectory.rows.filter(row=>row&&typeof row==='object').slice(-5):[];
  if(!rows.length)return '';
  const derived=rows.some(row=>row.ebitda_derived);
  const percent=value=>value==null?'—':`${value>0?'+':''}${number(value)}%`;
  const cagr=metric=>{
    const item=trajectory.summary?.[metric];
    const years=item?.years;
    return `<div><span>${metric==='revenue'?'Revenue':'PAT'} CAGR${years?` · ${number(years)}Y`:''}</span><strong class="${item?.cagr==null?'':item.cagr<0?'negative':'positive'}">${percent(item?.cagr)}</strong></div>`;
  };
  return `<section class="panel trajectory-panel"><div class="section-heading"><h2>5-year trajectory</h2><span class="section-kicker">ANNUAL · ₹ CR</span></div><p class="muted">${esc(trajectory.basis)} · ${rows.length} completed financial years · Standardized financials</p><table class="trajectory-financial-table"><caption class="sr-only">Annual revenue, year-on-year revenue growth, EBITDA margin and net profit</caption><thead><tr><th scope="col">Year</th><th scope="col">Revenue<br><span>₹ cr</span></th><th scope="col">Rev. YoY<br><span>%</span></th><th scope="col">EBITDA<br><span>margin %${derived?' *':''}</span></th><th scope="col">PAT<br><span>₹ cr</span></th></tr></thead><tbody>${rows.map(row=>`<tr><th scope="row" title="Year ended ${esc(row.period)}">${esc(row.year)}</th><td>${number(row.revenue)}</td><td class="${row.revenue_yoy==null?'':row.revenue_yoy<0?'negative':'positive'}">${percent(row.revenue_yoy)}</td><td>${row.ebitda_margin==null?'—':`${number(row.ebitda_margin)}%`}</td><td>${number(row.pat)}</td></tr>`).join('')}</tbody></table><div class="trajectory-summary">${cagr('revenue')}${cagr('pat')}</div>${derived?'<p class="trajectory-footnote">* Derived EBITDA proxy, consistent with the financial snapshot.</p>':''}<div class="trajectory-sources"><details class="trajectory-data"><summary>Source & calculation</summary><p>${esc(trajectory.note)}</p>${trajectory.summary?.revenue?`<p>CAGR period: ${esc(trajectory.summary.revenue.start)} – ${esc(trajectory.summary.revenue.end)}.</p>`:''}<a class="source-button" href="${esc(trajectory.source_url)}" target="_blank" rel="noopener noreferrer">Annual financial table ↗</a></details></div></section>`;
}
