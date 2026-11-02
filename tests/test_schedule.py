import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from finn.jobs.schedule import queue_daily_refresh
from finn.storage.store import Store


class DailyRefreshTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.store = Store(Path(self.directory.name))

    def at(self, day, hour, minute):
        return datetime(2026, 11, day, hour, minute, tzinfo=timezone.utc)

    def test_ist_boundary_and_restart(self):
        self.assertIsNone(queue_daily_refresh(self.store, self.at(3, 12, 59)))
        job = queue_daily_refresh(self.store, self.at(3, 13, 0))
        self.assertEqual(job['ticker'], 'PORTFOLIO')
        self.store.update_job(job['id'], 'complete', 'completed', {})
        restarted = Store(Path(self.directory.name))
        self.assertIsNone(queue_daily_refresh(restarted, self.at(3, 17, 0)))
        # 00:30 IST on Nov 4 must not launch a new day's refresh before 18:30.
        self.assertIsNone(queue_daily_refresh(restarted, self.at(3, 19, 0)))
        following = queue_daily_refresh(restarted, self.at(4, 13, 0))
        self.assertNotEqual(following['id'], job['id'])

    def test_late_start_and_concurrent_checks(self):
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: queue_daily_refresh(self.store, self.at(3, 16, 0)), range(3)))
        self.assertEqual(sum(result is not None for result in results), 1)

    def test_manual_refresh_is_shared_and_remains_available(self):
        manual = self.store.enqueue('PORTFOLIO', {'_kind': 'refresh'})
        scheduled = queue_daily_refresh(self.store, self.at(3, 13, 0))
        self.assertEqual(scheduled['id'], manual['id'])
        self.store.update_job(manual['id'], 'complete', 'completed', {})
        again = self.store.enqueue('PORTFOLIO', {'_kind': 'refresh'})
        self.assertNotEqual(again['id'], manual['id'])
