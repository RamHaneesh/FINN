from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from finn.storage import Store


class CacheRetention(unittest.TestCase):
    def test_dated_pull_versions_evict_without_losing_push_snapshot(self):
        with TemporaryDirectory() as tmp:
            store=Store(Path(tmp))
            for day,value in [('2026-10-30',100),('2026-10-31',110)]:
                store.put('financials-v1','INFY',{'fetched_at':day+'T10:00:00+00:00','value':value})
            self.assertEqual(store.get_dated('financials-v1','INFY','2026-10-30')['value'],100)
            self.assertEqual(store.get('financials-v1','INFY')['value'],110)
            for index in range(55):
                ticker=f'TEST{index:02}'
                store.touch_company(ticker)
                store.put('financials-v1',ticker,{'value':index})
            reopened=Store(Path(tmp))
            self.assertIsNone(reopened.get_dated('financials-v1','INFY','2026-10-30'))
            self.assertIsNone(reopened.get('financials-v1','INFY'))
            self.assertEqual(reopened.get_push('financials-v1','INFY')['value'],110)
            self.assertEqual(len(reopened.push_portfolio()),18)

    def test_ad_hoc_lru_evicts_dates_owned_results_and_late_writes(self):
        with TemporaryDirectory() as tmp:
            store=Store(Path(tmp))
            store.touch_company('OLD')
            store.put('financials-v1','OLD',{'value':1})
            # Initial warm-up companies have no protected Pull slots.
            store.put('financials-v1','KAYNES',{'fetched_at':'2026-10-30T10:00:00+00:00','value':99})
            store.put('model-json-v1','old-model',{'value':1},ticker='OLD')
            job=store.enqueue('OLD',{'max_calls':0})
            for index in range(50):
                ticker=f'TEST{index:02}'
                store.touch_company(ticker)
                store.put('financials-v1',ticker,{'value':index})
            self.assertIsNone(store.get('financials-v1','OLD'))
            self.assertIsNone(store.get('model-json-v1','old-model'))
            store.put('research-v1','OLD',{'late':'result'})
            store.update_job(job['id'],'complete','completed',{'late':'result'})
            self.assertIsNone(store.get('research-v1','OLD'))
            self.assertIsNone(store.job(job['id'])['result'])
            # An explicit revisit promotes the company; polling/cache writes do not.
            store.touch_company('TEST00')
            store.touch_company('OLD')
            store.put('financials-v1','OLD',{'value':2})
            self.assertIsNotNone(store.get('financials-v1','TEST00'))
            self.assertIsNone(store.get('financials-v1','TEST01'))
            self.assertEqual(store.get('financials-v1','OLD')['value'],2)
            with store.connection() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM company_access WHERE retained=1 AND pinned=0').fetchone()[0],50)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM company_access WHERE retained=1 AND pinned=1').fetchone()[0],0)
                self.assertIsNone(db.execute("SELECT 1 FROM push_portfolio WHERE ticker='KAYNES'").fetchone())
            self.assertIsNone(Store(Path(tmp)).get_dated('financials-v1','KAYNES','2026-10-30'))

    def test_cache_date_uses_indian_timezone(self):
        with TemporaryDirectory() as tmp:
            store=Store(Path(tmp))
            store.put('research-v1','INFY',{'generated_at':'2026-10-31T20:00:00+00:00'})
            self.assertIsNotNone(store.get_dated('research-v1','INFY','2026-11-01'))

    def test_legacy_pins_migrate_to_fifty_dynamic_slots_and_protected_push_data(self):
        import json
        with TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            with store.connection() as db:
                # Simulate the old shared table with a pinned core company and 50 others.
                for index,ticker in enumerate(['INFY'] + [f'LEGACY{i:02}' for i in range(50)]):
                    db.execute('INSERT INTO company_access VALUES(?,?,1,1)',(ticker,index))
                    db.execute('INSERT INTO cache VALUES(?,?,?,?)',('financials-v1',ticker,json.dumps({'value':index}),index))
            reopened = Store(Path(tmp))
            self.assertEqual(len(reopened.research_slots()),50)
            self.assertIsNone(reopened.get('financials-v1','INFY'))
            self.assertEqual(reopened.get_push('financials-v1','INFY')['value'],0)
            self.assertEqual(len(reopened.push_portfolio()),18)
            with reopened.connection() as db:
                self.assertEqual(db.execute('SELECT COUNT(*) FROM company_access WHERE pinned=1').fetchone()[0],0)
                self.assertEqual(db.execute('SELECT COUNT(DISTINCT key) FROM research_cache').fetchone()[0],50)
                self.assertEqual(db.execute("SELECT COUNT(*) FROM cache WHERE namespace='financials-v1'").fetchone()[0],0)


if __name__=='__main__':
    unittest.main()
