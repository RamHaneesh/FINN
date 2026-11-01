import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from finn.config import ROOT
from finn.services.portfolio import PortfolioService
from finn.sources.universe import source_symbol
from finn.storage import Store


class CoverageUniverse(unittest.TestCase):
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
        actual=[c['ticker'] for c in json.loads((ROOT/'config/portfolio.json').read_text())['companies']]
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
