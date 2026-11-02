"""Fixed Push storage and a strict, fully dynamic 50-company Pull LRU."""
from datetime import datetime
import json
import time
from zoneinfo import ZoneInfo

from finn.sources.universe import PUSH_COMPANIES
from finn.storage import push_alerts

SECTIONS = {'financials-v1', 'research-v1', 'business-profile-v2', 'trajectory-v1'}
TICKER_CACHES = SECTIONS | {'discovery-v1', 'business-v1', 'completion-context-v1', 'research-availability-v1', 'company-view-v1'}
PUSH = {item['ticker'] for item in PUSH_COMPANIES}
CAPACITY = 50


def table(namespace):
    return 'research_cache' if namespace in TICKER_CACHES else 'cache'


def mirror_push(db, namespace, key, payload, created):
    """Protect Push inputs independently of whether its ticker has a Pull slot."""
    if namespace in {'prices-v1', 'attention-v1', 'financials-v1'} and key in PUSH:
        pass
    elif namespace == 'announcements-v1' and isinstance(payload, list):
        payload = [event for event in payload if event.get('ticker') in PUSH]
        push_alerts.save(db, 'filing', payload)
        if not payload:
            return
    elif namespace == 'results-headlines-v1':
        # Results are queued only for fixed portfolio members.
        pass
    else:
        return
    db.execute('INSERT OR REPLACE INTO push_cache VALUES(?,?,?,?)',
               (namespace, key, json.dumps(payload, default=str), created))


def dated(payload, created):
    value = (payload.get('fetched_at') or payload.get('generated_at')) if isinstance(payload, dict) else None
    try:
        stamp = datetime.fromisoformat(value) if value else datetime.fromtimestamp(created, ZoneInfo('Asia/Kolkata'))
        return stamp.astimezone(ZoneInfo('Asia/Kolkata')).date().isoformat()
    except (ValueError, TypeError):
        return datetime.fromtimestamp(created, ZoneInfo('Asia/Kolkata')).date().isoformat()


def schema(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS push_portfolio(ticker TEXT PRIMARY KEY,position INTEGER NOT NULL,sector TEXT NOT NULL,source_ticker TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS push_cache(namespace TEXT NOT NULL,key TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(namespace,key));
        CREATE TABLE IF NOT EXISTS push_alerts(item_id TEXT PRIMARY KEY,ticker TEXT NOT NULL,kind TEXT NOT NULL,occurred REAL NOT NULL,payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS push_alerts_by_date ON push_alerts(occurred);
        CREATE TABLE IF NOT EXISTS research_cache(namespace TEXT NOT NULL,key TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(namespace,key));
        CREATE TABLE IF NOT EXISTS company_access(ticker TEXT PRIMARY KEY,last_opened REAL NOT NULL,pinned INTEGER NOT NULL,retained INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS dated_cache(namespace TEXT NOT NULL,ticker TEXT NOT NULL,as_of TEXT NOT NULL,payload TEXT NOT NULL,created REAL NOT NULL,PRIMARY KEY(namespace,ticker,as_of));
        CREATE TABLE IF NOT EXISTS cache_owners(namespace TEXT NOT NULL,key TEXT NOT NULL,ticker TEXT NOT NULL,PRIMARY KEY(namespace,key,ticker));
        CREATE INDEX IF NOT EXISTS cache_owners_by_ticker ON cache_owners(ticker);
    ''')
    # Only startup configuration changes Push membership, never a research/cache write.
    db.execute('DELETE FROM push_portfolio')
    db.executemany('INSERT INTO push_portfolio VALUES(?,?,?,?)', [
        (item['ticker'], index, item['sector'], item.get('source_ticker',item['ticker']))
        for index,item in enumerate(PUSH_COMPANIES)
    ])
    # Copy protected Push inputs before migration/LRU can remove Pull financials.
    for row in db.execute('''SELECT * FROM cache WHERE namespace IN
            ('prices-v1','attention-v1','financials-v1','announcements-v1','results-headlines-v1')
            UNION ALL SELECT * FROM research_cache WHERE namespace='financials-v1' ''').fetchall():
        mirror_push(db, row['namespace'], row['key'], json.loads(row['payload']), row['created'])
    for namespace in TICKER_CACHES:
        db.execute('INSERT OR IGNORE INTO research_cache SELECT * FROM cache WHERE namespace=?',(namespace,))
        db.execute('DELETE FROM cache WHERE namespace=?',(namespace,))
    # Migrate saved research without changing recency or resurrecting evicted slots.
    rows = db.execute('''SELECT c.* FROM (SELECT * FROM cache UNION ALL SELECT * FROM research_cache) c
        LEFT JOIN cache_owners o ON c.namespace=o.namespace AND c.key=o.key WHERE o.key IS NULL''').fetchall()
    for row in rows:
        payload = json.loads(row['payload'])
        ticker = row['key'] if row['namespace'] in TICKER_CACHES else (payload.get('source', {}).get('ticker') if row['namespace'].startswith('pypdf-pages-') and isinstance(payload, dict) else None)
        if not ticker:
            continue
        register(db, ticker, row['created'])
        db.execute('INSERT OR IGNORE INTO cache_owners VALUES(?,?,?)', (row['namespace'], row['key'], ticker))
        if row['namespace'] in SECTIONS:
            db.execute('INSERT OR IGNORE INTO dated_cache VALUES(?,?,?,?,?)', (row['namespace'], ticker, dated(payload,row['created']), row['payload'], row['created']))
    db.execute('UPDATE company_access SET pinned=0')
    prune(db)
    push_alerts.prune(db)


def register(db, ticker, stamp=None, opened=False):
    stamp = time.time() if stamp is None else stamp
    db.execute('INSERT OR IGNORE INTO company_access VALUES(?,?,0,1)', (ticker, stamp))
    if opened:
        db.execute('UPDATE company_access SET last_opened=?,retained=1 WHERE ticker=?', (stamp,ticker))
    return bool(db.execute('SELECT retained FROM company_access WHERE ticker=?',(ticker,)).fetchone()[0])


def prune(db):
    evicted = db.execute('SELECT ticker FROM company_access WHERE retained=1 ORDER BY last_opened DESC,ticker LIMIT -1 OFFSET ?', (CAPACITY,)).fetchall()
    for row in evicted:
        ticker = row[0]
        owned = db.execute('SELECT namespace,key FROM cache_owners WHERE ticker=?', (ticker,)).fetchall()
        db.execute('DELETE FROM cache_owners WHERE ticker=?',(ticker,))
        for namespace,key in owned:
            if not db.execute('SELECT 1 FROM cache_owners WHERE namespace=? AND key=?',(namespace,key)).fetchone():
                db.execute(f'DELETE FROM {table(namespace)} WHERE namespace=? AND key=?',(namespace,key))
        db.execute('DELETE FROM dated_cache WHERE ticker=?',(ticker,))
        db.execute("UPDATE jobs SET result=NULL WHERE ticker=? AND status NOT IN ('queued','running')",(ticker,))
        db.execute('UPDATE company_access SET retained=0 WHERE ticker=?',(ticker,))
