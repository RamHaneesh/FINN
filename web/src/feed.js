// Titles are deterministic views of the saved filing metrics, never generated claims.
export function resultHeadline(item,number) {
  const revenue=item.financials?.metrics?.find(metric=>metric.metric==='revenue');
  if(!revenue||!Number.isFinite(revenue.value))return item.title;
  const period=item.fiscal_quarter?`Q${item.fiscal_quarter}`:item.financials.latest_period;
  const company=`${item.ticker}${period?` ${period}`:''}`;
  if(!Number.isFinite(revenue.yoy))return `${company}: Revenue ₹${number(revenue.value)} Cr`;
  return `${company}: Revenue ${revenue.yoy>0?'+':''}${number(revenue.yoy)}% YoY (₹${number(revenue.value)} Cr)`;
}
