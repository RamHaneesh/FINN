"""Verify first deployment using a fresh volume with all source requests forbidden."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from finn.api.app import app
from finn.config import ROOT, Settings
from finn.sources.universe import COMPANIES


async def verify(root):
    settings = Settings(_env_file=None, finn_data_dir=root, finn_embedded_worker=False)
    with patch('finn.api.app.get_settings', return_value=settings), patch(
        'finn.sources.http.PublicHTTP.fetch', side_effect=AssertionError('Source network access forbidden')
    ):
        async with app.router.lifespan_context(app):
            counts = dict(profiles=0, financials=0, trajectories=0, research=0, availability=0)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                portfolio=(await client.get('/api/portfolio')).json()['companies']
                assert len(portfolio)==18, portfolio
                digest=(await client.get('/api/digest')).json()
                assert len(digest['portfolio'])==digest['covered_count']==18, digest['covered_count']
                assert all(item['ticker'] in {c['ticker'] for c in portfolio} for item in digest['items']+digest['routine'])
                for company in json.loads((ROOT / 'config/pull_universe.json').read_text())['companies']:
                    response = await client.get('/api/company/' + company['ticker'])
                    response.raise_for_status()
                    data = response.json()
                    counts['profiles'] += bool(data['business'] and data['business']['status'] == 'ready')
                    counts['financials'] += bool(data['snapshot'])
                    counts['trajectories'] += bool((data['trajectory'] or {}).get('rows'))
                    counts['research'] += bool(data['research'])
                    counts['availability'] += bool(data['research_availability'])
            assert counts['profiles'] == counts['financials'] == counts['trajectories'] == len(COMPANIES), counts
            assert counts['research'] + counts['availability'] == len(COMPANIES), counts
            print('Fresh deployment; source network blocked:', json.dumps(counts))


if __name__ == '__main__':
    with TemporaryDirectory() as directory:
        asyncio.run(verify(Path(directory)))
