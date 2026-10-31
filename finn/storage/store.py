"""SQLite metadata/cache and content-addressed raw files on the same local volume."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from finn.domain import fingerprint, utc_now


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.blobs = self.root / "documents"
        self.blobs.mkdir(exist_ok=True)
        self.database = self.root / "finn.sqlite3"
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS cache (
                    namespace TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
                    created REAL NOT NULL, PRIMARY KEY(namespace, key)
                );
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, request_key TEXT NOT NULL, ticker TEXT NOT NULL,
                    payload TEXT NOT NULL, status TEXT NOT NULL, stage TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    result TEXT, error TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_job ON jobs(request_key)
                    WHERE status IN ('queued', 'running');
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.database, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def get(self, namespace: str, key: str, max_age: int | None = None):
        with self.connection() as db:
            row = db.execute("SELECT payload,created FROM cache WHERE namespace=? AND key=?", (namespace, key)).fetchone()
        if row is None or (max_age is not None and time.time() - row["created"] > max_age):
            return None
        return json.loads(row["payload"])

    def put(self, namespace: str, key: str, payload):
        with self.connection() as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)", (namespace, key, json.dumps(payload, default=str), time.time()))

    def values(self, namespace: str):
        with self.connection() as db:
            rows = db.execute("SELECT payload FROM cache WHERE namespace=? ORDER BY created DESC", (namespace,)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def enqueue(self, ticker: str, payload: dict) -> dict:
        key = fingerprint({"ticker": ticker, **payload})
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM jobs WHERE request_key=? AND status IN ('queued','running')", (key,)).fetchone()
            if existing:
                return self._job(existing)
            job_id, now = uuid4().hex, utc_now()
            db.execute("INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?)", (job_id, key, ticker, json.dumps(payload), "queued", "queued", now, now, None, None))
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._job(row)

    def claim(self) -> dict | None:
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            # Single-worker deployment. A crashed/stale job becomes retryable.
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
            db.execute("UPDATE jobs SET status='queued',stage='recovering' WHERE status='running' AND updated_at<?", (cutoff,))
            row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created_at LIMIT 1").fetchone()
            if not row:
                return None
            db.execute("UPDATE jobs SET status='running',stage='starting',updated_at=? WHERE id=?", (utc_now(), row["id"]))
            row = db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
        return self._job(row)

    def update_job(self, job_id: str, stage: str, status: str = "running", result=None, error=None):
        with self.connection() as db:
            db.execute("UPDATE jobs SET stage=?,status=?,updated_at=?,result=?,error=? WHERE id=?", (stage, status, utc_now(), json.dumps(result) if result is not None else None, error, job_id))

    def job(self, job_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._job(row) if row else None

    @staticmethod
    def _job(row) -> dict:
        data = dict(row)
        data.pop("request_key", None)
        for field in ["payload", "result"]:
            if data[field] is not None:
                data[field] = json.loads(data[field])
        return data
