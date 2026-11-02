import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from datetime import date, datetime, timedelta, timezone

from finn.config import ROOT
from finn.services.portfolio import PortfolioService
from finn.sources.universe import source_symbol
from finn.storage import Store
from finn.sources.universe import COMPANIES, PUSH_COMPANIES


class CoverageUniverse(unittest.TestCase):
    def test_push_membership_is_separate_from_dynamic_research(self):
        expected='RELIANCE TCS HDFCBANK INFY DIXON CAMS NTPC DMART TRENT LT BHARTIARTL MARUTI HAL ZOMATO SUNPHARMA BAJFINANCE TATAMOTORS SIEMENS'.split()
        self.assertEqual([c['ticker'] for c in PUSH_COMPANIES],expected)
        with TemporaryDirectory() as tmp:
            store=Store(Path(tmp))
            self.assertEqual([c['ticker'] for c in store.push_portfolio()],expected)
            bars=[{'date':str(date.today()-timedelta(days=21-i)), 'close':100 if i<20 else 110,'volume':100 if i<20 else 500} for i in range(21)]
            for ticker in expected+['KAYNES','CLEAN']:
                store.put('prices-v1',ticker,bars)
            store.touch_company('CLEAN')
            store.put('business-profile-v2','CLEAN',{'status':'ready','description':'Outside portfolio'})
            store.put('announcements-v1','mixed',[{'event_id':ticker,'ticker':ticker,'subject':'Appointment of CFO','description':'Management change','published_at':datetime.now(timezone.utc).isoformat(),'source_url':'https://example.com/filing'} for ticker in ['INFY','KAYNES','CLEAN']])
            service=PortfolioService(SimpleNamespace(store=store))
            digest=service.digest()
            self.assertEqual(digest['covered_count'],18)
            self.assertEqual([c['ticker'] for c in digest['portfolio']],expected)
            self.assertTrue(digest['items'])
            self.assertTrue(all(item['ticker'] in expected for item in digest['items']+digest['routine']))
            self.assertEqual(service.company('KAYNES')['sector'],'Electronics manufacturing')
            self.assertEqual(service.company('CLEAN')['business']['status'],'ready')
            self.assertEqual(store.push_portfolio(),Store(Path(tmp)).push_portfolio())
            # Old filings for the other 17 cached companies must not queue Push work.
            from finn.services.results import enqueue_results
            store.put('announcements-v1','mixed-results',[{'event_id':'results-'+ticker,'ticker':ticker,'subject':'Financial results','description':'Quarterly results','published_at':datetime.now(timezone.utc).isoformat(),'source_url':'https://example.com/results'} for ticker in ['INFY','KAYNES','CLEAN']])
            queued=enqueue_results(SimpleNamespace(store=store),limit=10)
            self.assertEqual([job['ticker'] for job in queued],['INFY'])
            with store.connection() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM push_portfolio').fetchone()[0],18)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM company_access WHERE pinned=1').fetchone()[0],0)

    def test_latest_research_status_ignores_other_jobs_and_large_results(self):
        with TemporaryDirectory() as tmp:
            store=Store(Path(tmp))
            old=store.enqueue('INFY',{'max_calls':0})
            store.update_job(old['id'],'complete','completed',{'large':'x'*100000})
            store.enqueue('INFY',{'_kind':'business'})
            self.assertEqual(store.latest_research_job('INFY')['id'],old['id'])
            self.assertIsNone(store.latest_research_job('INFY')['result'])
            active=store.enqueue('INFY',{'max_calls':1})
            self.assertEqual(store.latest_research_job('INFY')['id'],active['id'])

    def test_exact_final_universe_and_explicit_legacy_sources(self):
        expected='20MICRONS APOLLOHOSP ASIANPAINT BAJFINANCE BHARTIARTL BSE CAMS COFORGE DIXON DMART HAL HAVELLS HDFCBANK HINDUNILVR ICICIBANK INFY KAYNES LT MARUTI NTPC PERSISTENT POLYCAB RELIANCE SEDEMAC SIEMENS SRF SUNPHARMA TATACAP TATAMOTORS TCS TITAN TRENT ULTRACEMCO VBL ZOMATO'.split()
        expected += 'AXISBANK BEL CHOLAFIN CIPLA EICHERMOT HCLTECH ITC JIOFIN KOTAKBANK M&M NESTLEIND POWERGRID SBIN TATASTEEL WIPRO'.split()
        actual=[c['ticker'] for c in json.loads((ROOT/'config/pull_universe.json').read_text())['companies']]
        self.assertEqual(actual,expected)
        self.assertEqual(source_symbol('ZOMATO'),'ETERNAL')
        self.assertEqual(source_symbol('TATAMOTORS'),'TMPV')
        self.assertEqual(source_symbol('INFY'),'INFY')

    def test_cached_view_invalidates_when_source_section_changes(self):
        with TemporaryDirectory() as tmp:
            store=Store(Path(tmp))
            service=PortfolioService(SimpleNamespace(store=store))
            store.put('business-profile-v2','INFY',{'status':'ready','name':'Infosys','description':'Old profile'})
            first=service.company('INFY')
            self.assertEqual(service.company('INFY'),first)
            store.put('business-profile-v2','INFY',{'status':'ready','name':'Infosys','description':'Updated profile'})
            self.assertEqual(service.company('INFY')['business']['description'],'Updated profile')


if __name__=='__main__':unittest.main()
