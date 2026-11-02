"""Exercise a real 51st ticker on a SQLite backup, preserving the warm demo cache."""
import json
from pathlib import Path
import sqlite3
from contextlib import closing

from finn.config import ROOT, Settings, get_settings
from finn.domain import utc_now
from finn.pipeline import Pipeline
from finn.services.completion import fill_context
from finn.services.portfolio import PortfolioService


def main():
    settings = get_settings()
    root = ROOT / 'tmp' / ('lru-check-' + utc_now().replace(':', '-'))
    root.mkdir(parents=True)
    with closing(sqlite3.connect(settings.finn_data_dir / 'finn.sqlite3')) as source:
        with closing(sqlite3.connect(root / 'finn.sqlite3')) as target:
            source.backup(target)
    pipeline = Pipeline(Settings(finn_data_dir=root))
    store = pipeline.store
    before = store.research_slots()
    assert len(before) == 50, len(before)
    assert 'CLEAN' not in {row['ticker'] for row in before}
    victim = before[0]['ticker']
    digest_before = PortfolioService(pipeline).digest()
    store.touch_company('CLEAN')
    fill_context(pipeline, 'CLEAN')
    clean = PortfolioService(pipeline).company('CLEAN')
    assert clean['business'] and clean['business']['status'] == 'ready'
    assert clean['snapshot'] and clean['snapshot']['history']
    assert clean['trajectory'] and clean['trajectory']['rows']
    after = store.research_slots()
    assert len(after) == 50
    assert {r['ticker'] for r in after} == ({r['ticker'] for r in before} - {victim}) | {'CLEAN'}
    with store.connection() as db:
        assert not db.execute('SELECT 1 FROM research_cache WHERE key=?',(victim,)).fetchone()
        assert db.execute('SELECT COUNT(DISTINCT key) FROM research_cache').fetchone()[0] == 50
    assert PortfolioService(pipeline).digest() == digest_before
    assert len(store.push_portfolio()) == 18
    # Reopen/migration must not re-pin or resurrect a configured warm-up ticker.
    reopened = Pipeline(Settings(finn_data_dir=root))
    assert {r['ticker'] for r in reopened.store.research_slots()} == {r['ticker'] for r in after}
    result = {'checked_at':utc_now(), 'before':50, 'after':50, 'added':'CLEAN', 'evicted':victim,
              'push_count':18, 'push_unchanged':True, 'restart_preserved_lru':True,
              'clean_profile':True, 'clean_financials':True, 'clean_trajectory_years':len(clean['trajectory']['rows']),
              'method':'Real source fetching in a SQLite backup; original 50-company demo cache preserved.'}
    (ROOT / 'tmp/research-lru-verification.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    main()
