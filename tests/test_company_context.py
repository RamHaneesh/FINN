from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from finn.sources.profile import CACHE, ProfileSource
from finn.services.trajectory import cached_trajectory, calculate
from finn.storage import Store


def snapshot():
    return {'basis': 'consolidated', 'source_url': 'https://www.screener.in/company/TEST/#quarters', 'annual': [
        {'label': 'Mar 2024', 'start': '2023-04-01', 'end': '2024-03-31', 'revenue': 100, 'pat': -10, 'ebitda': 20, 'ebitda_derived': True},
        {'label': 'Mar 2025', 'start': '2024-04-01', 'end': '2025-03-31', 'revenue': 110, 'pat': None, 'ebitda': None},
        {'label': 'Mar 2026', 'start': '2025-04-01', 'end': '2026-03-31', 'revenue': 121, 'pat': 5, 'ebitda': 30.25}]}


class CompanyContext(unittest.TestCase):
    def test_table_uses_preceding_year_for_first_yoy_and_true_five_year_cagr(self):
        data = snapshot()
        data['annual'] = [{'label': f'Mar {year}', 'start': f'{year-1}-04-01', 'end': f'{year}-03-31',
                           'revenue': 100*1.1**(year-2021), 'pat': 10*1.1**(year-2021), 'ebitda': 20*1.1**(year-2021)} for year in range(2021, 2027)]
        result = calculate(data)
        self.assertEqual(len(result['rows']), 5)
        self.assertEqual(result['rows'][0]['year'], 'FY2022')
        self.assertEqual(result['rows'][0]['revenue_yoy'], 10)
        self.assertEqual(result['summary']['revenue']['years'], 5)
        self.assertAlmostEqual(result['summary']['revenue']['cagr'], 10, places=1)
        self.assertEqual(result['summary']['revenue']['start'], 'Mar 2021')

    def test_annual_cagr_margin_and_missing_loss_values(self):
        result = calculate(snapshot())
        revenue, pat, margin = result['series']
        self.assertAlmostEqual(revenue['cagr'], 10, places=1)
        self.assertIsNone(pat['cagr'])  # Loss-to-profit is not a valid CAGR.
        self.assertIsNone(pat['points'][1]['y'])
        self.assertEqual(margin['points'][-1]['value'], 25)
        self.assertEqual(margin['change'], 5)
        self.assertTrue(margin['derived'])

    def test_cache_reused_and_invalidated_by_new_financial_values(self):
        with TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            data = snapshot()
            first = cached_trajectory(store, 'TEST', data)
            self.assertEqual(first, cached_trajectory(store, 'TEST', data))
            data['annual'][-1]['revenue'] = 150
            self.assertNotEqual(first['input_key'], cached_trajectory(store, 'TEST', data)['input_key'])

    def test_profile_copies_description_and_dated_mix_not_market_share(self):
        html = b'''<h1>Example Manufacturing Ltd</h1><div class="company-profile">
        <div class="about"><p>Example Ltd. manufactures electronic products.<sup>[1]</sup> It sells the Alpha brand. A third sentence.</p></div>
        <div class="commentary"><p><strong>Business Segments:</strong><br>
        <strong>a) Mobile (80% in FY26 vs 70% in FY25)</strong><br>
        <strong>b) Lighting (20% in FY26 vs 30% in FY25)</strong><br>
        <strong>35% market share in FY26</strong></p></div></div>'''
        profile = ProfileSource.parse('TEST', 'https://www.screener.in/company/TEST/', html)
        self.assertEqual(profile['description'], 'Example Ltd. manufactures electronic products. It sells the Alpha brand.')
        self.assertEqual(profile['revenue_mix'], ['Mobile (80% in FY26 vs 70% in FY25)', 'Lighting (20% in FY26 vs 30% in FY25)'])
        self.assertEqual(profile['source_type'], 'company_profile')

    def test_profile_cache_never_uses_transcripts_or_model(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        from finn.services.business import build_business
        with TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            saved = {'status': 'ready', 'description': 'Saved public company profile.'}
            store.put(CACHE, 'TEST', saved)
            pipeline = SimpleNamespace(store=store, http=Mock(), discover=Mock(), documents=Mock())
            with patch('finn.models.Gemini') as model:
                self.assertEqual(build_business(pipeline, 'TEST'), saved)
                model.assert_not_called()
            pipeline.http.fetch.assert_not_called()
            pipeline.discover.assert_not_called()
            pipeline.documents.ingest.assert_not_called()

    def test_old_transcript_business_cache_is_ignored(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from finn.services.business import build_business
        with TemporaryDirectory() as tmp:
            store = Store(Path(tmp))
            store.put('business-v1', 'TEST', {'status': 'ready', 'description': 'Old transcript quote'})
            http = Mock()
            http.fetch.return_value = b'<h1>Test</h1><div class="company-profile"><div class="about">Test manufactures pumps. It serves industrial clients.</div></div>'
            result = build_business(SimpleNamespace(store=store, http=http), 'TEST')
            self.assertEqual(result['description'], 'Test manufactures pumps. It serves industrial clients.')
            self.assertEqual(http.fetch.call_count, 1)

    def test_profile_load_does_not_wait_for_queued_narrative_job(self):
        import asyncio
        import httpx
        from unittest.mock import patch
        from finn.api.app import app
        from finn.config import Settings

        async def exercise(root):
            with patch('finn.api.app.get_settings', return_value=Settings(_env_file=None, finn_data_dir=root)):
                async with app.router.lifespan_context(app):
                    job = app.state.pipeline.store.enqueue('TEST', {'max_calls': 0})
                    html = b'<h1>Test Ltd</h1><div class="company-profile"><div class="about">Test manufactures pumps. It serves industrial clients.</div></div>'
                    with patch.object(app.state.pipeline.http, 'fetch', return_value=html), patch.object(app.state.pipeline, 'discover') as discover:
                        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
                            response = await client.post('/api/company/TEST/business')
                            self.assertEqual(response.status_code, 202)
                            data = (await client.get('/api/company/TEST')).json()
                            self.assertEqual(data['business']['status'], 'ready')
                            self.assertEqual(data['name'], 'Test Ltd')
                            self.assertEqual(app.state.pipeline.store.job(job['id'])['status'], 'queued')
                            self.assertEqual((await client.post('/api/company/TEST/business')).json()['status'], 'cached')
                    discover.assert_not_called()
        with TemporaryDirectory() as tmp:
            asyncio.run(exercise(Path(tmp)))


class AutomaticCompletion(unittest.TestCase):
    def test_missing_sections_are_filled_independently_and_jobs_are_deduplicated(self):
        import asyncio
        import httpx
        from unittest.mock import patch
        from finn.api.app import app
        from finn.config import Settings
        from finn.domain import utc_now

        async def exercise(root):
            settings=Settings(_env_file=None, finn_data_dir=root, finn_max_model_calls=0)
            with patch('finn.api.app.get_settings', return_value=settings):
                async with app.router.lifespan_context(app):
                    store=app.state.pipeline.store
                    def financial(ticker, **kwargs):
                        data=dict(snapshot(), ticker=ticker, name=ticker, history=[{'label':'Mar 2026','end':'2026-03-31'}], fetched_at=utc_now(), metrics=[])
                        store.put('financials-v1', ticker, data)
                        return data
                    def profile(ticker, **kwargs):
                        data={'status':'ready','name':ticker,'description':'The company manufactures pumps. It serves industrial clients.','generated_at':utc_now()}
                        store.put(CACHE,ticker,data)
                        return data
                    def research(ticker):
                        store.put('research-v1',ticker,{'narratives':[],'facts':[],'documents':[],'coverage':'processed'})
                    with patch('finn.sources.profile.ProfileSource.fetch',side_effect=profile) as profiles, patch('finn.sources.financials.FinancialSource.fetch',side_effect=financial) as financials, patch('finn.models.Gemini') as model, patch.object(app.state.pipeline,'discover') as discover:
                        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
                            portfolio_before=(await client.get('/api/portfolio')).json()['companies']
                            self.assertEqual(len(portfolio_before),18)
                            await client.get('/api/company/CLEAN?opened=true')
                            first=(await client.post('/api/company/CLEAN/complete')).json()
                            second=(await client.post('/api/company/CLEAN/complete')).json()
                            self.assertEqual(first['research_job']['id'],second['research_job']['id'])
                            self.assertEqual(profiles.call_count,1)
                            self.assertEqual(financials.call_count,1)
                            saved=(await client.get('/api/company/CLEAN')).json()
                            self.assertTrue(saved['trajectory']['rows'])
                            self.assertFalse(saved['context_pending'])
                            self.assertEqual(saved['business']['status'],'ready')
                            self.assertEqual((await client.get('/api/portfolio')).json()['companies'],portfolio_before)
                            self.assertNotIn('CLEAN',{c['ticker'] for c in (await client.get('/api/digest')).json()['portfolio']})
                            financial('FINONLY'); profile('FINONLY')
                            result=(await client.post('/api/company/FINONLY/complete')).json()
                            self.assertFalse(result['context_pending'])
                            self.assertIsNotNone(result['research_job'])
                            profile('FINMISS'); research('FINMISS')
                            result=(await client.post('/api/company/FINMISS/complete')).json()
                            self.assertTrue(result['context_pending'])
                            self.assertIsNone(result['research_job'])
                            self.assertIsNotNone(store.get('financials-v1','FINMISS'))
                            financial('PROFILEMISS'); research('PROFILEMISS')
                            result=(await client.post('/api/company/PROFILEMISS/complete')).json()
                            self.assertIsNone(result['research_job'])
                            self.assertIsNotNone(store.get(CACHE,'PROFILEMISS'))
                            financial('TRJMISS'); profile('TRJMISS'); research('TRJMISS')
                            incomplete=store.get('financials-v1','TRJMISS'); incomplete['annual']=[]
                            store.put('financials-v1','TRJMISS',incomplete)
                            result=(await client.post('/api/company/TRJMISS/complete')).json()
                            self.assertTrue(result['context_pending'])
                            self.assertIsNone(result['research_job'])
                            self.assertTrue(store.get('financials-v1','TRJMISS')['annual'])
                            research('FINONLY')
                            # A valid empty research report must not trigger new analysis.
                            store.update_job(store.recent_jobs('FINONLY')[0]['id'],'complete','completed',{})
                            result=(await client.post('/api/company/FINONLY/complete')).json()
                            self.assertFalse(any(result['missing'].values()))
                            self.assertIsNone(result['research_job'])
                            financial('FAILED'); profile('FAILED')
                            job=store.enqueue('FAILED',{'max_calls':0})
                            store.update_job(job['id'],'failed','failed',error='Quota unavailable')
                            result=(await client.post('/api/company/FAILED/complete')).json()
                            self.assertIsNone(result['research_job'])
                            self.assertEqual(len(store.recent_jobs('FAILED')),1)
                    model.assert_not_called()
                    discover.assert_not_called()
        with TemporaryDirectory() as tmp:
            asyncio.run(exercise(Path(tmp)))


if __name__ == '__main__':
    unittest.main()
