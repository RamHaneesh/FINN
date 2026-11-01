"""Verify first deployment using a fresh volume with all source requests forbidden."""
import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from finn.api.app import app
from finn.config import ROOT, Settings


async def verify(root):
    settings = Settings(_env_file=None, finn_data_dir=root, finn_embedded_worker=False)
    with patch('finn.api.app.get_settings', return_value=settings), patch(
        'finn.sources.http.PublicHTTP.fetch', side_effect=AssertionError('Source network access forbidden')
    ):
        async with app.router.lifespan_context(app):
            counts = dict(profiles=0, financials=0, trajectories=0, research=0, availability=0)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                for company in json.loads((ROOT / 'config/portfolio.json').read_text())['companies']:
                    response = await client.get('/api/company/' + company['ticker'])
                    response.raise_for_status()
                    data = response.json()
                    counts['profiles'] += bool(data['business'] and data['business']['status'] == 'ready')
                    counts['financials'] += bool(data['snapshot'])
                    counts['trajectories'] += len((data['trajectory'] or {}).get('rows', [])) == 5
                    counts['research'] += bool(data['research'])
                    counts['availability'] += bool(data['research_availability'])
            assert counts['profiles'] == counts['financials'] == counts['trajectories'] == 35, counts
            assert counts['research'] + counts['availability'] == 35, counts
            print('Fresh deployment; source network blocked:', json.dumps(counts))


if __name__ == '__main__':
    with TemporaryDirectory() as directory:
        asyncio.run(verify(Path(directory)))
