"""Resume-safe coverage warming; queue primary research only where transcripts exist."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

from finn.config import get_settings
from finn.domain import utc_now
from finn.pipeline import Pipeline
from finn.services.completion import fill_context
from finn.services.portfolio import PortfolioService


def audit(pipeline):
    rows=[]
    for company in PortfolioService(pipeline).companies:
        ticker=company['ticker']
        data=PortfolioService(pipeline).company(ticker)
        report=data['research']
        unavailable=pipeline.store.get('research-availability-v1',ticker)
        rows.append({'ticker':ticker,'profile':bool(data['business'] and data['business'].get('status')=='ready'),
                     'financials':bool(data['snapshot'] and data['snapshot'].get('history')),
                     'trajectory_years':len((data['trajectory'] or {}).get('rows',[])),
                     'research':bool(report),'narratives':len(report.get('narratives',[])) if report else 0,
                     'availability':unavailable,'jobs':[{k:j[k] for k in ['id','status','stage','error']} for j in pipeline.store.recent_jobs(ticker,limit=1)]})
    result={'generated_at':utc_now(),'profiles':sum(r['profile'] for r in rows),'financials':sum(r['financials'] for r in rows),
            'research_reports':sum(r['research'] for r in rows),'total':len(rows),'companies':rows}
    output=Path('tmp/coverage-audit.json');output.parent.mkdir(exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--max-calls',type=int,default=6)
    parser.add_argument('--wait',action='store_true')
    parser.add_argument('--audit-only',action='store_true')
    args=parser.parse_args()
    pipeline=Pipeline(get_settings())
    companies=PortfolioService(pipeline).companies
    if not args.audit_only:
        def context(company):
            ticker=company['ticker'];pipeline.store.touch_company(ticker)
            fill_context(pipeline,ticker)
            print(json.dumps({'ticker':ticker,'context_warmed':True}),flush=True)
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(context,companies))
        # Prioritize the ten additions; then finish partial existing caches as well.
        additions=['APOLLOHOSP','BSE','COFORGE','HAL','HAVELLS','KAYNES','SRF','TATAMOTORS','VBL','ZOMATO']
        ordered=additions+[c['ticker'] for c in companies if c['ticker'] not in additions]
        for ticker in ordered:
            if pipeline.store.get('research-v1',ticker):
                continue
            try:
                links=pipeline.discover(ticker)
                if not any(link.kind.value=='transcript' for link in links):
                    pipeline.store.put('research-availability-v1',ticker,{'status':'unavailable','checked_at':utc_now(),'reason':'No primary transcript links in the published source archive.'})
                    print(json.dumps({'ticker':ticker,'research':'no_primary_transcripts'}),flush=True)
                    continue
                job=pipeline.store.enqueue(ticker,{'max_documents':6,'max_calls':min(args.max_calls,pipeline.settings.finn_max_model_calls),'refresh':False})
                print(json.dumps({'ticker':ticker,'job':job['id'],'status':job['status']}),flush=True)
            except Exception as exc:
                print(json.dumps({'ticker':ticker,'discovery_error':type(exc).__name__}),flush=True)
    if args.wait:
        universe={c['ticker'] for c in companies};previous=None
        while True:
            jobs=[j for j in pipeline.store.recent_jobs(limit=300) if j['ticker'] in universe and j['status'] in {'queued','running'}]
            state=[(j['ticker'],j['status'],j['stage']) for j in jobs]
            if state!=previous:
                print(json.dumps({'pending':len(state),'running':[(ticker,stage) for ticker,status,stage in state if status=='running']}),flush=True);previous=state
            if not jobs:break
            time.sleep(3)
    result=audit(pipeline)
    print(json.dumps({key:value for key,value in result.items() if key!='companies'}),flush=True)


if __name__=='__main__':main()
