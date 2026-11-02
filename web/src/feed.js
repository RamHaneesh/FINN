// Titles are deterministic views of the saved filing metrics, never generated claims.
export const isMarketMove = item => ['price','volume'].includes(item.category);

// Visibility follows the current window; importance is never inferred from frequency.
export const EVENT_FILTERS = [
  {key:'all',label:'All events'},
  {key:'results',label:'Results'},
  {key:'management_change',label:'Management'},
  {key:'fund_raise',label:'Capital raises'},
  {key:'mergers',label:'M&A'},
  {key:'risk',label:'Legal & risk'},
  {key:'capex',label:'Capex'},
  {key:'other',label:'Other'},
];

export function eventBucket(item) {
  if(['results','management_change','fund_raise','capex'].includes(item.category))return item.category;
  if(item.category==='M&A')return 'mergers';
  if(['litigation','pledging','insider_trading','credit_rating'].includes(item.category))return 'risk';
  return 'other';
}

export function eventFilterOptions(items,selected='all') {
  const events=items.filter(item=>!isMarketMove(item));
  return EVENT_FILTERS.map(option=>({...option,count:option.key==='all'?events.length:events.filter(item=>eventBucket(item)===option.key).length}))
    .filter(option=>option.key==='all'||option.count>0||option.key===selected);
}

export function digestSections(items, filter='all', eventFilter='all') {
  const events=items.filter(item=>!isMarketMove(item)).filter(item=>filter!=='events'||eventFilter==='all'||
    eventBucket(item)===eventFilter);
  return {events:filter==='market'?[]:events,market:filter==='events'?[]:items.filter(isMarketMove)};
}

export function sourceDescriptor(value) {
  try {
    const url=new URL(value);
    if(!['https:','http:'].includes(url.protocol))return null;
    const host=url.hostname.toLowerCase();
    const domain=name=>host===name||host.endsWith('.'+name);
    const label=domain('nseindia.com')?'NSE filing':domain('bseindia.com')?'BSE filing':
      host==='finance.yahoo.com'?'Yahoo EOD data':domain('screener.in')?'Screener financials':'Source document';
    return {url:url.href,label};
  } catch {return null;}
}

export function resultHeadline(item,number) {
  const revenue=item.financials?.metrics?.find(metric=>metric.metric==='revenue');
  if(!revenue||!Number.isFinite(revenue.value))return item.title;
  const period=item.fiscal_quarter?`Q${item.fiscal_quarter}`:item.financials.latest_period;
  const company=`${item.ticker}${period?` ${period}`:''}`;
  if(!Number.isFinite(revenue.yoy))return `${company}: Revenue ₹${number(revenue.value)} Cr`;
  return `${company}: Revenue ${revenue.yoy>0?'+':''}${number(revenue.yoy)}% YoY (₹${number(revenue.value)} Cr)`;
}
