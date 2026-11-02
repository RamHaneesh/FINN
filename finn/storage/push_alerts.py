"""Ninety-day Push-only event archive; never touches research evidence."""
from datetime import datetime, timezone
import json

RETENTION_DAYS = 90


def stamp(value):
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone.utc).timestamp() if parsed.tzinfo is None else parsed.timestamp()


def save(db, kind, items, now=None):
    cutoff = (now or datetime.now(timezone.utc)).timestamp() - RETENTION_DAYS * 86400
    for item in items:
        occurred = stamp(item['published_at'] if kind == 'filing' else item['occurred_at'])
        if occurred >= cutoff:
            key = item['event_id'] if kind == 'filing' else item['item_id']
            db.execute('INSERT OR REPLACE INTO push_alerts VALUES(?,?,?,?,?)',
                       (key, item['ticker'], kind, occurred, json.dumps(item)))


def prune(db, now=None):
    cutoff = (now or datetime.now(timezone.utc)).timestamp() - RETENTION_DAYS * 86400
    portfolio = {row[0] for row in db.execute('SELECT ticker FROM push_portfolio')}
    db.execute('DELETE FROM push_alerts WHERE occurred<?', (cutoff,))
    # Remove duplicate expired alert payloads from source/attention snapshots too.
    # Financials, prices, documents, extraction results and research are untouched.
    for table in ('cache', 'push_cache'):
        rows = db.execute(f"SELECT namespace,key,payload FROM {table} WHERE namespace IN ('announcements-v1','attention-v1')").fetchall()
        for row in rows:
            payload = json.loads(row['payload'])
            items = payload if isinstance(payload, list) else payload.get('items', [])
            kept = [item for item in items if item.get('ticker') not in portfolio or stamp(item.get('published_at') or item['occurred_at']) >= cutoff]
            if len(kept) != len(items):
                if isinstance(payload, list):
                    payload = kept
                else:
                    payload['items'] = kept
                db.execute(f'UPDATE {table} SET payload=? WHERE namespace=? AND key=?',
                           (json.dumps(payload), row['namespace'], row['key']))
