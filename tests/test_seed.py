from pathlib import Path
from contextlib import closing
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from finn.storage.seed import bootstrap_seed


class SeedBootstrap(unittest.TestCase):
    def test_empty_volume_gets_committed_wal_data_and_evidence_once(self):
        with TemporaryDirectory() as tmp:
            source, target = Path(tmp) / 'bundle', Path(tmp) / 'volume'
            source.mkdir()
            (source / 'documents').mkdir()
            (source / 'documents' / 'source.pdf').write_bytes(b'cached evidence')
            with closing(sqlite3.connect(source / 'finn.sqlite3')) as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('CREATE TABLE cache(value TEXT)')
                db.execute("INSERT INTO cache VALUES ('saved profile')")
                db.commit()
                self.assertTrue(bootstrap_seed(target, source))
            with closing(sqlite3.connect(target / 'finn.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT value FROM cache').fetchone()[0], 'saved profile')
                db.execute("UPDATE cache SET value='newer deployment data'")
                db.commit()
            self.assertEqual((target / 'documents' / 'source.pdf').read_bytes(), b'cached evidence')
            self.assertFalse(bootstrap_seed(target, source))
            with closing(sqlite3.connect(target / 'finn.sqlite3')) as db:
                self.assertEqual(db.execute('SELECT value FROM cache').fetchone()[0], 'newer deployment data')
            self.assertFalse(bootstrap_seed(source, source))
