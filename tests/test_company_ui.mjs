import {resultHeadline} from '../web/src/feed.js';
import assert from 'node:assert/strict';
import {businessHtml,trajectoryHtml} from '../web/src/company.js';

const helpers={esc:value=>String(value??''),date:value=>String(value??''),number:value=>value==null?'—':String(value)};
const profile={source_type:'company_profile',source_url:'https://www.screener.in/company/TEST/',description:'Test manufactures pumps. It serves industrial customers.'};
assert.match(businessHtml(profile,helpers),/Test manufactures pumps/);
assert.doesNotThrow(()=>businessHtml({...profile,description:{text:'Old transcript cache'}},helpers));
assert.doesNotMatch(businessHtml({...profile,description:{text:'Old transcript cache'}},helpers),/\[object Object\]|Old transcript cache/);
for(const input of [undefined,null,{}, {periods:undefined}, {periods:[]}, {rows:[]}, {rows:[null]}]) {
  assert.equal(trajectoryHtml(input,helpers),'');
}
const table=trajectoryHtml({basis:'consolidated',source_url:'https://www.screener.in/company/TEST/',rows:[{year:'FY2025',period:'Mar 2025',revenue:100,revenue_yoy:10,ebitda_margin:20,pat:10},{year:'FY2026',period:'Mar 2026',revenue:110,revenue_yoy:10,ebitda_margin:21,pat:12}],summary:{revenue:{cagr:10,years:5,start:'Mar 2021',end:'Mar 2026'},pat:{cagr:12,years:5}}},helpers);
assert.match(table,/5-year trajectory/);
assert.match(table,/<table/);
assert.match(table,/FY2026/);
assert.match(table,/Rev. YoY/);
assert.match(table,/Revenue CAGR · 5Y/);
assert.doesNotMatch(table,/<svg|<polyline|NaN|undefined/);
console.log('Company UI regression cases passed: profiles and compact financial trajectory tables.');

const format=value=>Number(value).toLocaleString('en-IN',{maximumFractionDigits:1});
const filing={ticker:'NTPC',fiscal_quarter:2,title:'Sep 2026 results filed',financials:{latest_period:'Sep 2026',metrics:[{metric:'revenue',value:54270,yoy:21.2}]}};
assert.equal(resultHeadline(filing,format),'NTPC Q2: Revenue +21.2% YoY (₹54,270 Cr)');
assert.equal(resultHeadline({...filing,financials:{metrics:[]}},format),filing.title);
assert.doesNotMatch(resultHeadline({...filing,financials:{metrics:[{metric:'revenue',value:54270,yoy:null}]}},format),/YoY|null/);
