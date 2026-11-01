"""Ticker/date snapshots, pinned portfolio retention and a 50-company ad-hoc LRU."""
from datetime import datetime
import json
import time
from zoneinfo import ZoneInfo

from finn.config import ROOT

SECTIONS = {'financials-v1', 'research-v1', 'business-profile-v2', 'trajectory-v1'}
TICKER_CACHES = SECTIONS | {'discovery-v1', 'business-v1', 'completion-context-v1', 'research-availability-v1', 'company-view-v1'}
PINNED = {item['ticker'] for item in json.loads((ROOT/'config/portfolio.json').read_text())['companies']}


def dated(payload, created):
    value = (payload.get('fetched_at') or payload.get('generated_at')) if isinstance(payload, dict) else None
    try:
        stamp = datetime.fromisoformat(value) if value else datetime.fromtimestamp(created, ZoneInfo('Asia/Kolkata'))
        return stamp.astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()
    except (ValueError, TypeError):
        return datetime.fromtimestamp(created, ZoneInfo('Asia/Kolkata')).date().isoformat()


def schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS company_access(ticker TEXT PRIMARY KEY,last_opened REAL NOT NULL,pinned INTEGER NOT NULL,retained INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS dated_cache(namespace TEXT NOT NULL,ticker TEXT NOT NULL,as_of TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(namespace,ticker,as_of));
        CREATE TABLE IF NOT EXISTS cache_owners(namespace TEXT NOT NULL,key TEXT NOT NULL,ticker TEXT NOT NULL,PRIMARY KEY(namespace,key,ticker));
    ''')
    # Migrate existing results without dropping their saved dates or changing recency on restart.
    rows = db.execute('SELECT c.* FROM cache c LEFT JOIN cache_owners o ON c.namespace=o.namespace AND c.key=o.key WHERE o.key IS NULL').fetchall()
    for row in rows:
        payload = json.loads(row['payload'])
        ticker = row['key'] if row['namespace'] in TICKER_CACHES else (payload.get('source', {}).get('ticker') if row['namespace'].startswith('pypdf-pages-') and isinstance(payload, dict) else None)
        if not ticker:
            continue
        register(db, ticker, row['created'])
        db.execute('INSERT OR IGNORE INTO cache_owners VALUES(?,?,?)', (row['namespace'], row['key'], ticker))
        if row['namespace'] in SECTIONS:
            db.execute('INSERT OR IGNORE INTO dated_cache VALUES(?,?,?,?,?)', (row['namespace'], ticker, dated(payload,row['created']), row['payload'], row['created']))
    for ticker in PINNED:
        db.execute('UPDATE company_access SET pinned=1,retained=1 WHERE ticker=?', (ticker,))
    prune(db)


def register(db, ticker, stamp=None, opened=False):
    stamp = time.time() if stamp is None else stamp
    db.execute('INSERT OR IGNORE INTO company_access VALUES(?,?,?,1)', (ticker, stamp, int(ticker in PINNED)))
    if opened:
        db.execute('UPDATE company_access SET last_opened=?,retained=1 WHERE ticker=?', (stamp,ticker))
    return bool(db.execute('SELECT retained FROM company_access WHERE ticker=?',(ticker,)).fetchone()[0])


def prune(db):
    evicted = db.execute('SELECT ticker FROM company_access WHERE pinned=0 AND retained=1 ORDER BY last_opened DESC,ticker LIMIT -1 OFFSET 50').fetchall()
    for row in evicted:
        ticker = row[0]
        owned = db.execute('SELECT namespace,key FROM cache_owners WHERE ticker=?', (ticker,)).fetchall()
        db.execute('DELETE FROM cache_owners WHERE ticker=?',(ticker,))
        for namespace,key in owned:
            if not db.execute('SELECT 1 FROM cache_owners WHERE namespace=? AND key=?',(namespace,key)).fetchone():
                db.execute('DELETE FROM cache WHERE namespace=? AND key=?',(namespace,key))
        db.execute('DELETE FROM dated_cache WHERE ticker=?',(ticker,))
        db.execute("UPDATE jobs SET result=NULL WHERE ticker=? AND status NOT IN ('queued','running')",(ticker,))
        db.execute('UPDATE company_access SET retained=0 WHERE ticker=?',(ticker,))
