"""SQLite metadata/cache and content-addressed raw files on the same local volume."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import time
from uuid import uuid4

from finn.domain import fingerprint, utc_now
from finn.storage import retention


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
                CREATE INDEX IF NOT EXISTS jobs_by_ticker ON jobs(ticker,created_at DESC);
                CREATE TABLE IF NOT EXISTS job_tracking (
                    job_id TEXT PRIMARY KEY, started_at TEXT NOT NULL,
                    phase_started_at TEXT NOT NULL, timings TEXT NOT NULL
                );
            """)
            retention.schema(db)

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
            row = db.execute(f"SELECT payload,created FROM {retention.table(namespace)} WHERE namespace=? AND key=?", (namespace, key)).fetchone()
        if row is None or (max_age is not None and time.time() - row["created"] > max_age):
            return None
        return json.loads(row["payload"])

    def put(self, namespace: str, key: str, payload, ticker=None):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            created, encoded = time.time(), json.dumps(payload, default=str)
            retention.mirror_push(db, namespace, key, payload, created)
            owner = ticker or (key if namespace in retention.TICKER_CACHES else None)
            if owner and not retention.register(db, owner):
                return  # A background job must not resurrect an evicted ad-hoc company.
            db.execute(f"INSERT OR REPLACE INTO {retention.table(namespace)} VALUES (?,?,?,?)", (namespace, key, encoded, created))
            if owner:
                if namespace in retention.SECTIONS or namespace == 'research-availability-v1':
                    db.execute("DELETE FROM research_cache WHERE namespace='company-view-v1' AND key=?",(owner,))
                db.execute('INSERT OR IGNORE INTO cache_owners VALUES(?,?,?)',(namespace,key,owner))
                if namespace in retention.SECTIONS:
                    db.execute('INSERT OR REPLACE INTO dated_cache VALUES(?,?,?,?,?)',(namespace,owner,retention.dated(payload,created),encoded,created))
                retention.prune(db)

    def touch_company(self, ticker):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            retention.register(db,ticker,opened=True)
            retention.prune(db)

    def push_portfolio(self):
        """Read fixed Push membership independently of company_access and cache."""
        with self.connection() as db:
            rows = db.execute('SELECT ticker,sector,source_ticker FROM push_portfolio ORDER BY position').fetchall()
        return [dict(row) for row in rows]

    def get_push(self, namespace, key):
        with self.connection() as db:
            row = db.execute('SELECT payload FROM push_cache WHERE namespace=? AND key=?',(namespace,key)).fetchone()
        return json.loads(row[0]) if row else None

    def push_values(self, namespace):
        with self.connection() as db:
            rows = db.execute('SELECT payload FROM push_cache WHERE namespace=? ORDER BY created DESC',(namespace,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def research_slots(self):
        with self.connection() as db:
            rows = db.execute('SELECT ticker,last_opened FROM company_access WHERE retained=1 ORDER BY last_opened,ticker').fetchall()
        return [dict(row) for row in rows]

    def get_dated(self, namespace, ticker, as_of):
        with self.connection() as db:
            row=db.execute('SELECT payload FROM dated_cache WHERE namespace=? AND ticker=? AND as_of=?',(namespace,ticker,as_of)).fetchone()
        return json.loads(row[0]) if row else None

    def values(self, namespace: str):
        with self.connection() as db:
            rows = db.execute(f"SELECT payload FROM {retention.table(namespace)} WHERE namespace=? ORDER BY created DESC", (namespace,)).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def enqueue(self, ticker: str, payload: dict) -> dict:
        key = fingerprint({"ticker": ticker, **payload})
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if payload.get("_kind", "research") == "research":
                active = db.execute("SELECT * FROM jobs WHERE ticker=? AND status IN ('queued','running') ORDER BY created_at", (ticker,)).fetchall()
                for row in active:
                    if json.loads(row["payload"]).get("_kind", "research") == "research":
                        return self._job(row)
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
            now = utc_now()
            db.execute("INSERT OR REPLACE INTO job_tracking VALUES (?,?,?,?)", (row["id"], now, now, "{}"))
            row = db.execute("SELECT * FROM jobs WHERE id=?", (row["id"],)).fetchone()
        return self._job(row)

    def update_job(self, job_id: str, stage: str, status: str = "running", result=None, error=None):
        with self.connection() as db:
            now = utc_now()
            previous = db.execute("SELECT stage FROM jobs WHERE id=?", (job_id,)).fetchone()
            tracking = db.execute("SELECT * FROM job_tracking WHERE job_id=?", (job_id,)).fetchone()
            if tracking and previous and previous["stage"].split(":")[0] != stage.split(":")[0]:
                timings = json.loads(tracking["timings"])
                elapsed = (datetime.fromisoformat(now) - datetime.fromisoformat(tracking["phase_started_at"])).total_seconds()
                phase = previous["stage"].split(":")[0]
                timings[phase] = round(timings.get(phase, 0) + elapsed, 2)
                db.execute("UPDATE job_tracking SET phase_started_at=?,timings=? WHERE job_id=?", (now, json.dumps(timings), job_id))
            if result is not None:
                job_ticker = db.execute('SELECT ticker FROM jobs WHERE id=?',(job_id,)).fetchone()
                retained = db.execute('SELECT retained FROM company_access WHERE ticker=?',(job_ticker[0],)).fetchone() if job_ticker else None
                if retained and not retained[0]:
                    result = None
            db.execute("UPDATE jobs SET stage=?,status=?,updated_at=?,result=?,error=? WHERE id=?", (stage, status, now, json.dumps(result) if result is not None else None, error, job_id))

    def job(self, job_id: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            tracking = db.execute("SELECT * FROM job_tracking WHERE job_id=?", (job_id,)).fetchone()
        if row is None:
            return None
        job = self._job(row)
        if tracking:
            job.update(started_at=tracking["started_at"], phase_started_at=tracking["phase_started_at"], stage_timings=json.loads(tracking["timings"]))
        return job

    def recent_jobs(self, ticker=None, limit=40):
        with self.connection() as db:
            rows = db.execute("SELECT id FROM jobs " + ("WHERE ticker=? " if ticker else "") + "ORDER BY created_at DESC LIMIT ?", (ticker, limit) if ticker else (limit,)).fetchall()
        return [self.job(row["id"]) for row in rows]

    def latest_research_job(self, ticker):
        """Status-only lookup; never deserialize historical research result payloads."""
        with self.connection() as db:
            row=db.execute('''SELECT j.id,j.ticker,j.payload,j.status,j.stage,j.created_at,j.updated_at,
                NULL AS result,j.error,t.started_at,t.phase_started_at,t.timings
                FROM jobs j LEFT JOIN job_tracking t ON t.job_id=j.id
                WHERE j.ticker=? AND COALESCE(json_extract(j.payload,'$._kind'),'research')='research'
                ORDER BY (j.status IN ('queued','running')) DESC,j.created_at DESC LIMIT 1''',(ticker,)).fetchone()
        if row is None:
            return None
        data=self._job(row)
        timings=data.pop('timings')
        data['stage_timings']=json.loads(timings) if timings else {}
        for key in ['started_at','phase_started_at']:
            if data.get(key) is None:
                data.pop(key,None)
        return data

    @staticmethod
    def _job(row) -> dict:
        data = dict(row)
        data.pop("request_key", None)
        for field in ["payload", "result"]:
            if data[field] is not None:
                data[field] = json.loads(data[field])
        return data
