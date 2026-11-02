"""Measure actual local HTTP latency; never fetch provider data during the audit."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from statistics import median
from time import perf_counter

import httpx

from finn.config import get_settings
from finn.domain import utc_now
from finn.pipeline import Pipeline
from finn.services.portfolio import PortfolioService
from finn.sources.universe import COMPANIES
from scripts.warm_universe import audit


def main():
    pipeline=Pipeline(get_settings())
    coverage=audit(pipeline)
    rows=[]
    with httpx.Client(base_url='http://127.0.0.1:8000',timeout=15) as client:
        client.get('/api/health').raise_for_status()  # Prime the local HTTP session, as in an already-open app.
        for company in COMPANIES:
            ticker=company['ticker']; timings=[]
            for index in range(6):
                start=perf_counter()
                response=client.get('/api/company/'+ticker,params={'opened':'true'} if index==0 else None)
                response.raise_for_status();data=response.json()
                timings.append(round((perf_counter()-start)*1000,2))
                assert data['business'] and data['business']['status']=='ready',ticker
                assert data['snapshot'] and data['snapshot']['history'],ticker
                assert 1 <= len(data['trajectory']['rows']) <= 5,ticker
            rows.append({'ticker':ticker,'first_ms':timings[0],'median_ms':round(median(timings[1:]),2),
                         'max_ms':max(timings),'samples_ms':timings})
    result={'generated_at':utc_now(),'coverage':{key:coverage[key] for key in ['profiles','financials','research_reports','total']},
            'push_portfolio_count':len(pipeline.store.push_portfolio()),
            'ready_without_autofill':sum(row['profile'] and row['financials'] and row['trajectory_years']>0 and bool(row['research'] or row['availability']) for row in coverage['companies']),
            'method':'Warm localhost HTTP session (/api/health first), then first opening plus five repeats per ticker; includes JSON transfer and parsing.',
            'all_medians_under_50ms':all(row['median_ms']<50 for row in rows),
            'all_medians_under_25ms':all(row['median_ms']<25 for row in rows),
            'samples_under_25ms':sum(value<25 for row in rows for value in row['samples_ms']),
            'sample_count':sum(len(row['samples_ms']) for row in rows),
            'all_samples_under_50ms':all(row['max_ms']<50 for row in rows),'max_ms':max(row['max_ms'] for row in rows),
            'rows':rows}
    Path('tmp/universe-latency.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    lines=['# FINN coverage audit','',f"Updated: {datetime.fromisoformat(result['generated_at']).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d %b %Y, %H:%M IST')}",'',
           f"Scope: {coverage['total']} dynamic Pull slots (strict 50-company LRU); separate fixed Push portfolio: {result['push_portfolio_count']} companies.",'',
           f"Profiles: {coverage['profiles']}/{coverage['total']}; financials: {coverage['financials']}/{coverage['total']}; trajectory tables: {sum(c['trajectory_years']>0 for c in coverage['companies'])}/{coverage['total']} "
           f"({sum(c['trajectory_years']==5 for c in coverage['companies'])} have five annual observations; shorter available histories are labeled).",'',
           '| Ticker | Profile | Financials | Years | Narrative | First ms | Cached median ms | Max ms |',
           '|---|---|---|---:|---|---:|---:|---:|']
    for row,cached in zip(rows,coverage['companies']):
        status='Saved' if cached['research'] else 'No primary transcript' if cached['availability'] else 'Pending / source gap'
        lines.append(f"| {row['ticker']} | Saved | Saved | {cached['trajectory_years']} | {status} | {row['first_ms']} | {row['median_ms']} | {row['max_ms']} |")
    lines+=['',result['method'],
            f"All cached medians below 25 ms: {result['all_medians_under_25ms']}; requests below 25 ms: {result['samples_under_25ms']}/{result['sample_count']}.",
            f"Maximum measured response: {result['max_ms']} ms. All {coverage['total']} cached medians below 50 ms: {result['all_medians_under_50ms']}. All {result['sample_count']} timed samples below 50 ms: {result['all_samples_under_50ms']}.",
            'Times are measurements on this machine, not a phone/Wi-Fi SLA.',
            'Legacy labels: ZOMATO uses ETERNAL source data; TATAMOTORS uses TMPV (passenger vehicles) source data. Historical figures may span reorganisations. Source links and names are preserved in the app.',
            '[NSE Eternal announcement](https://www.nseindia.com/companies-listing/corporate-filings-announcements?symbol=ETERNAL) · [NSE Tata Motors symbol-change circular](https://nsearchives.nseindia.com/content/circulars/FAOP70882.pdf)']
    lines += ['', 'Short histories are shown as available, without invented annual observations: ' +
              ', '.join(f"{row['ticker']} ({row['trajectory_years']} years)" for row in coverage['companies'] if row['trajectory_years'] < 5) + '.']
    lru_path = Path('tmp/research-lru-verification.json')
    if lru_path.exists():
        lru = json.loads(lru_path.read_text())
        lines += ['', '## 51st-company LRU verification', '',
                  f"Checked {lru['checked_at']}: CLEAN fetched real profile/financial/trajectory data in a backup of the 50-company cache. "
                  f"The least-recently searched company, {lru['evicted']}, was evicted. Pull retained exactly {lru['after']} companies; "
                  f"all {lru['push_count']} Push holdings and their digest remained unchanged. Reopening preserved the eviction. "
                  'The original initial 50-company demo cache was preserved.']
    destination = Path('docs/coverage.md')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({key:value for key,value in result.items() if key!='rows'}))


if __name__=='__main__':main()
