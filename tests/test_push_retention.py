from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from finn.services.portfolio import PortfolioService
from finn.storage.store import Store


class PushRetentionTests(unittest.TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.store = Store(Path(self.folder.name))
        self.now = datetime.now(timezone.utc)

    def event(self, days):
        return {'event_id':str(days), 'ticker':'INFY', 'subject':'Compliance certificate',
                'description':'Routine filing', 'published_at':(self.now-timedelta(days=days)).isoformat(),
                'source_url':'https://www.nseindia.com/filing.pdf'}

    def test_archive_survives_source_overwrite_and_digest_stops_at_30(self):
        self.store.put('announcements-v1','INFY:90',[self.event(20), self.event(45)])
        self.store.put('announcements-v1','INFY:90',[self.event(1)])
        self.assertEqual({row['event_id'] for row in self.store.push_alerts('filing',90)}, {'1','20','45'})
        digest = PortfolioService(SimpleNamespace(store=self.store)).digest(2160)
        self.assertEqual(digest['hours'],720)
        self.assertEqual({row['item_id'] for row in digest['routine']},{'1','20'})

    def test_expired_push_only_is_deleted_and_research_unchanged(self):
        self.store.put('announcements-v1','INFY:90',[self.event(89)])
        market = {'item_id':'market','ticker':'INFY','occurred_at':self.event(89)['published_at']}
        self.store.save_push_alerts([market])
        protected = {'financials-v1':{'annual':[{'year':2010}]},
                     'research-v1':{'narratives':[{'quote':'historical guidance'}]},
                     'discovery-v1':[{'url':'transcript.pdf'}]}
        for namespace,payload in protected.items():
            self.store.put(namespace,'INFY',payload)
        self.store.put('document-url-v1','primary-transcript',{'document_id':'saved'})
        self.store.prune_push_alerts(self.now+timedelta(days=2))
        with self.store.connection() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM push_alerts').fetchone()[0],0)
        self.assertEqual(self.store.get('announcements-v1','INFY:90'),[])
        self.assertEqual(self.store.get_push('announcements-v1','INFY:90'),[])
        for namespace,payload in protected.items():
            self.assertEqual(self.store.get(namespace,'INFY'),payload)
        self.assertEqual(self.store.get('document-url-v1','primary-transcript'),{'document_id':'saved'})

    def test_expired_input_cannot_reenter_archive(self):
        self.store.put('announcements-v1','INFY:90',[self.event(91),self.event(89)])
        self.assertEqual([row['event_id'] for row in self.store.push_alerts('filing',90)],['89'])
