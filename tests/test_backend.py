from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from finn.analysis import compare
from finn.config import Settings
from finn.domain import Announcement, Citation, DocumentKind, DocumentLink, FinancialFact, Narrative, Page, ParsedDocument, PriceBar
from finn.extraction.extractor import Extraction, validate_evidence
from finn.jobs.worker import run_once
from finn.models import BudgetExceeded, Gemini
from finn.pipeline import Pipeline
from finn.signals import announcement_attention, market_attention
from finn.sources.discovery import ScreenerDiscovery
from finn.storage import Store


def statement(**changes):
    values = dict(metric="revenue_growth_yoy", period_start=date(2025, 4, 1), period_end=date(2026, 3, 31), basis="consolidated", scope="company", currency_basis="reported", unit="percent", narrative_type="guidance", stated_on=date(2025, 5, 1), lower=15, upper=18, citation=Citation(document_id="old", url="https://company.example/old.pdf", page=1, quote="We expect growth of 15 to 18 percent."))
    values.update(changes)
    return Narrative(**values)


def actual(**changes):
    values = dict(metric="revenue_growth_yoy", period_start=date(2025, 4, 1), period_end=date(2026, 3, 31), basis="consolidated", scope="company", currency_basis="reported", unit="percent", value=12, reported_on=date(2026, 4, 20), citation=Citation(document_id="new", url="https://company.example/new.pdf", page=1, quote="Revenue growth for the year was 12 percent."))
    values.update(changes)
    return FinancialFact(**values)


class FilingDisplay(unittest.TestCase):
    def test_management_fields_require_named_action_and_role(self):
        from finn.services.filing_display import management_fields
        self.assertEqual(management_fields('Appointment', 'Appointment of Mr. Rajesh Kumar as Chief Financial Officer'),
                         {'person': 'Rajesh Kumar', 'role': 'Chief Financial Officer', 'action': 'Joined'})
        self.assertEqual(management_fields('Resignation', 'Resignation of Ms. Anita Rao as Company Secretary')['action'], 'Resigned')
        self.assertIsNone(management_fields('Change in Management', 'Company has informed the Exchange about change in Management'))


class Comparisons(unittest.TestCase):
    as_of = date(2026, 10, 31)

    def test_missed_guidance_uses_percentage_points(self):
        result = compare(statement(), [actual()], self.as_of)
        self.assertEqual(result.status, "Missed")
        self.assertEqual(result.difference, -3)
        self.assertIn("percentage points", result.explanation)

    def test_above_guidance_preserves_relationship(self):
        result = compare(statement(), [actual(value=20)], self.as_of)
        self.assertEqual((result.status, result.relationship), ("Met", "above"))

    def test_period_basis_and_currency_mismatch_never_get_verdict(self):
        for changes in [{"period_start": date(2026, 1, 1)}, {"basis": "standalone"}, {"currency_basis": "constant_currency"}, {"scope": "retail"}]:
            with self.subTest(changes=changes):
                self.assertEqual(compare(statement(), [actual(**changes)], self.as_of).status, "Cannot compare")

    def test_no_using_actuals_that_predate_guidance(self):
        self.assertEqual(compare(statement(), [actual(reported_on=date(2025, 4, 20))], self.as_of).status, "Cannot compare")

    def test_future_guidance_pending_and_aspiration_context_only(self):
        self.assertEqual(compare(statement(period_end=date(2027, 3, 31)), [], self.as_of).status, "Pending")
        self.assertEqual(compare(statement(narrative_type="aspiration"), [actual()], self.as_of).status, "Cannot compare")

    def test_conflicting_actuals_require_review(self):
        self.assertEqual(compare(statement(), [actual(value=12), actual(value=16)], self.as_of).status, "Cannot compare")

    def test_prior_year_active_and_context_are_separated(self):
        from finn.analysis.guidance import guidance_review
        future = statement(period_start=date(2026,4,1), period_end=date(2027,3,31), stated_on=date(2026,4,20))
        vague = statement(narrative_type="aspiration")
        review = guidance_review([statement(), future, vague], [actual()], self.as_of)
        self.assertEqual(review["period"]["label"], "FY2026")
        self.assertEqual([item["status"] for item in review["completed"]], ["Missed"])
        self.assertEqual(len(review["active"]), 1)
        self.assertEqual(len(review["context"]), 1)

    def test_revised_historical_targets_keep_both_verdicts(self):
        from finn.analysis.guidance import guidance_review
        revised = statement(lower=12, upper=14, stated_on=date(2026,1,15))
        review = guidance_review([statement(), revised], [actual()], self.as_of)
        self.assertEqual({item["status"] for item in review["completed"]}, {"Met", "Missed"})

    def test_source_selection_reaches_previous_year_and_outcome_call(self):
        from finn.analysis.guidance import review_period, select_transcripts
        links = [DocumentLink(ticker="INFY", kind="transcript", url=f"https://example.com/{index}.pdf", title=title, discovery_url="https://www.screener.in/company/INFY/") for index,title in enumerate(["Oct 2026 Transcript", "Jul 2026 Transcript", "Apr 2026 Transcript", "Feb 2026 Transcript", "Jan 2026 Transcript", "Oct 2025 Transcript", "Jul 2025 Transcript", "Apr 2025 Transcript"])]
        selected = select_transcripts(links, review_period(self.as_of), self.as_of, 6)
        titles = [item.title for item in selected]
        self.assertIn("Jan 2026 Transcript", titles)
        self.assertIn("Apr 2025 Transcript", titles)
        self.assertIn("Apr 2026 Transcript", titles)
        self.assertIn("Oct 2026 Transcript", titles)
        self.assertNotIn("Feb 2026 Transcript", titles)

    def test_inr_normalization(self):
        result = compare(statement(metric="revenue", unit="INR_crore", lower=100, upper=110), [actual(metric="revenue", unit="INR_million", value=1050)], self.as_of)
        self.assertEqual(result.relationship, "within")


class SourcesAndSignals(unittest.TestCase):
    def test_discovery_does_not_ingest_ai_summary_or_recording(self):
        html = b'''<div class="annual-reports"><a href="https://company.example/ar.pdf">Annual Report 2026</a></div>
        <div class="concalls"><li>Oct 2026<a href="https://company.example/call.pdf">Transcript</a>
        <a href="https://www.screener.in/summary/1/">AI Summary</a><a href="https://company.example/audio.mp3">REC</a></li></div>'''
        links = ScreenerDiscovery.parse("INFY", "https://www.screener.in/company/INFY/", html)
        self.assertEqual(len(links), 2)
        self.assertEqual({item.kind for item in links}, {DocumentKind.ANNUAL_REPORT, DocumentKind.TRANSCRIPT})

    def test_fabricated_quote_is_rejected(self):
        source = DocumentLink(ticker="INFY", url="https://company.example/old.pdf", kind="transcript", title="Call", discovery_url="https://www.screener.in/company/INFY/")
        document = ParsedDocument(document_id="old", content_hash="hash", source=source, pages=[Page(number=1, text="We expect growth of 15 to 18 percent.")], fetched_at="now")
        accepted, warnings = validate_evidence(Extraction(narratives=[statement(), statement(citation=Citation(document_id="old", url=source.url, page=1, quote="We guarantee 80 percent growth."))]), document, document.pages)
        self.assertEqual(len(accepted.narratives), 1)
        self.assertEqual(len(warnings), 1)

    def test_operating_margin_is_never_accepted_as_ebitda(self):
        source = DocumentLink(ticker="INFY", url="https://company.example/new.pdf", kind="transcript", title="Call", discovery_url="https://www.screener.in/company/INFY/")
        quote = "Operating margin was stable at 21%."
        document = ParsedDocument(document_id="new", content_hash="hash", source=source, pages=[Page(number=1, text=quote)], fetched_at="now")
        fact = actual(metric="ebitda_margin", value=21, citation=Citation(document_id="new", url=source.url, page=1, quote=quote))
        accepted, warnings = validate_evidence(Extraction(facts=[fact]), document, document.pages)
        self.assertEqual(accepted.facts, [])
        self.assertIn("EBITDA", warnings[0])

    def test_volume_baseline_excludes_current_session(self):
        bars = [PriceBar(date=date(2026, 9, 1) + timedelta(days=i), close=100, volume=100) for i in range(20)]
        bars.append(PriceBar(date=date(2026, 10, 1), close=100, volume=210))
        result = market_attention("INFY", bars)
        self.assertEqual(len(result), 1)
        self.assertIn("2.10x", result[0].title)

    def test_split_does_not_trigger_price_alert(self):
        bars = [PriceBar(date=date(2026, 9, 1) + timedelta(days=i), close=100, volume=100) for i in range(20)]
        bars.append(PriceBar(date=date(2026, 10, 1), close=50, volume=100, split=2))
        self.assertEqual(market_attention("INFY", bars), [])

    def test_routine_notice_hidden_but_material_language_retained(self):
        base = dict(event_id="1", ticker="INFY", published_at=datetime.now(timezone.utc), source_url="https://nse.example/filing.pdf")
        self.assertIsNone(announcement_attention(Announcement(**base, subject="Newspaper publication", description="Results published")))
        self.assertIsNotNone(announcement_attention(Announcement(**base, subject="Newspaper publication", description="Regulatory order and penalty disclosure")))


class PersistenceAndModel(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Store(self.root)

    def test_active_jobs_deduplicate_and_finished_jobs_can_restart(self):
        first = self.store.enqueue("INFY", {"max_calls": 1})
        self.assertEqual(first["id"], self.store.enqueue("INFY", {"max_calls": 1})["id"])
        self.assertEqual(self.store.claim()["id"], first["id"])
        self.assertIsNone(self.store.claim())
        self.store.update_job(first["id"], "complete", "completed", {"ok": True})
        self.assertNotEqual(first["id"], self.store.enqueue("INFY", {"max_calls": 1})["id"])

    def test_stale_running_job_is_recovered(self):
        job = self.store.enqueue("INFY", {})
        self.store.claim()
        with self.store.connection() as db:
            db.execute("UPDATE jobs SET updated_at=? WHERE id=?", ((datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), job["id"]))
        self.assertEqual(self.store.claim()["id"], job["id"])

    def test_progress_survives_reopen_and_duplicate_options(self):
        from finn.jobs.progress import JobProgress
        job = self.store.enqueue("INFY", {"max_calls": 2})
        same = self.store.enqueue("INFY", {"max_calls": 6})
        self.assertEqual(job["id"], same["id"])
        self.store.claim()
        self.store.update_job(job["id"], "parsing:2:5")
        reopened = Store(self.root)
        saved = reopened.job(job["id"])
        self.assertIn("started_at", saved)
        progress = JobProgress(reopened).present(saved)["progress"]
        self.assertEqual(progress["step"], 3)
        self.assertIn("2 of 5", progress["detail"])
        self.assertNotIn("estimated_total_seconds", progress)

    def test_research_progress_excludes_headline_jobs(self):
        from finn.jobs.progress import JobProgress
        research = self.store.enqueue("INFY", {"max_calls": 1})
        self.store.enqueue("INFY", {"_kind": "headlines", "event": {}})
        self.assertEqual(JobProgress(self.store).latest("INFY")["id"], research["id"])

    def test_cached_extraction_makes_no_second_provider_call(self):
        settings = Settings(_env_file=None, gemini_api_key="test-only", finn_data_dir=self.root)
        client = MagicMock()
        client.__enter__.return_value = client
        client.models.generate_content.return_value = SimpleNamespace(text='{"narratives":[],"facts":[]}', usage_metadata=None)
        with patch("finn.models.gemini.genai.Client", return_value=client):
            first = Gemini(settings, self.store, max_calls=1)
            first.structured("same prompt", Extraction)
            second = Gemini(settings, self.store, max_calls=0)
            second.structured("same prompt", Extraction)
            self.assertEqual(client.models.generate_content.call_count, 1)
            self.assertEqual(second.cache_hits, 1)
            with self.assertRaises(BudgetExceeded):
                second.structured("changed source", Extraction)

    def test_worker_records_failure_without_leaking_provider_details(self):
        pipeline = Pipeline(Settings(_env_file=None, finn_data_dir=self.root))
        job = pipeline.store.enqueue("INFY", {})
        with patch.object(pipeline, "research", side_effect=RuntimeError("sensitive-provider-detail")):
            self.assertTrue(run_once(pipeline))
        saved = pipeline.store.job(job["id"])
        self.assertEqual(saved["status"], "failed")
        self.assertNotIn("sensitive-provider-detail", saved["error"])

    def test_api_queue_worker_and_saved_result(self):
        import asyncio
        import httpx
        from finn.api.app import app
        settings = Settings(_env_file=None, finn_data_dir=self.root)

        async def exercise():
            with patch("finn.api.app.get_settings", return_value=settings):
                async with app.router.lifespan_context(app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                        self.assertEqual((await client.get("/api/health")).status_code, 200)
                        self.assertEqual((await client.post("/api/research", json={"ticker": "../.env"})).status_code, 422)
                        one = (await client.post("/api/research", json={"ticker": "INFY.NS", "max_calls": 0})).json()
                        two = (await client.post("/api/research", json={"ticker": "INFY", "max_calls": 0})).json()
                        self.assertEqual(one["id"], two["id"])
                        result = {"ticker": "INFY", "coverage": "partial"}
                        with patch.object(app.state.pipeline, "research", return_value=SimpleNamespace(model_dump=lambda **kwargs: result)):
                            self.assertTrue(run_once(app.state.pipeline))
                        saved = (await client.get(f"/api/jobs/{one['id']}")).json()
                        self.assertEqual(saved["status"], "completed")
                        self.assertEqual(saved["result"], result)
                        self.assertEqual((await client.get("/api/jobs/missing")).status_code, 404)
                        self.assertEqual((await client.get("/api/companies/INFY/research")).status_code, 404)

        asyncio.run(exercise())


if __name__ == "__main__":
    unittest.main()
