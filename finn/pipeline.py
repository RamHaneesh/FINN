"""Application workflows shared by the CLI and worker; never fetch broker/news research."""
from datetime import datetime, timedelta
from itertools import zip_longest
from zoneinfo import ZoneInfo

from finn.analysis import compare
from finn.config import Settings
from finn.documents import DocumentService, chunks
from finn.domain import DocumentKind, DocumentLink, ResearchReport, fingerprint, normalize_ticker, utc_now
from finn.extraction import Extractor
from finn.models import BudgetExceeded, Gemini, ModelError
from finn.signals import announcement_attention, market_attention
from finn.sources.discovery import ScreenerDiscovery
from finn.sources.exchange import NSESource
from finn.sources.http import PublicHTTP, SourceError
from finn.sources.market import MarketSource
from finn.sources.financials import FinancialSource
from finn.storage import Store


class Pipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = Store(settings.finn_data_dir)
        self.http = PublicHTTP(settings.finn_http_timeout)
        self.discovery = ScreenerDiscovery(self.store, self.http)
        self.documents = DocumentService(self.store, self.http, settings.finn_max_pdf_mb)

    def discover(self, ticker: str, refresh=False):
        return self.discovery.discover(ticker, refresh=refresh)

    def research(self, ticker: str, max_documents=6, max_calls: int | None = None, refresh=False, progress=None) -> ResearchReport:
        ticker = normalize_ticker(ticker)
        progress = progress or (lambda stage: None)
        progress("financial_tables")
        snapshot = None
        try:
            snapshot = FinancialSource(self.store, self.http).fetch(ticker, refresh=refresh)
        except Exception:
            pass  # Transcript research can still proceed; the missing snapshot stays visible.
        progress("discovering_transcripts")
        links = self.discover(ticker, refresh=refresh)
        # A fifth call allows one off-cycle transcript without losing the prior-year target.
        selected = [link for link in links if link.kind == DocumentKind.TRANSCRIPT][:5]
        warnings = ["Transcript analysis is primary-source grounded. Financial snapshot/derived actuals use separately labeled standardized Screener tables; they are not direct filing extraction. Annual reports remain linked in the source library and are not parsed on the interactive path."]
        selected = selected[:max_documents]
        progress("parsing")
        parsed = []
        for link in selected:
            try:
                parsed.append(self.documents.ingest(link, refresh=refresh))
            except Exception as exc:
                warnings.append(f"Could not parse {link.kind.value}: {type(exc).__name__}; source {link.url}")
        if not parsed:
            raise SourceError("No usable primary PDFs were retrieved; inspect discovery links or source access")
        model = Gemini(self.settings, self.store, min(max_calls if max_calls is not None else self.settings.finn_max_model_calls, self.settings.finn_max_model_calls))
        extractor = Extractor(model)
        narratives = {}
        facts = {fingerprint(fact.model_dump(mode="json")): fact for fact in FinancialSource.facts(snapshot)} if snapshot else {}
        batches = [chunks(document, self.settings.finn_chunk_chars) for document in parsed]
        # Annual reports are large: prioritize sections likely to hold audited context,
        # while preserving the full chunk count and explicit partial-coverage warning.
        for document, parts in zip(parsed, batches):
            if document.source.kind == DocumentKind.ANNUAL_REPORT:
                parts.sort(key=lambda part: -sum(page.text.lower().count(term) for page in part for term in ["consolidated", "revenue", "cash flow", "financial statements"]))
        processed, total = 0, sum(len(parts) for parts in batches)
        progress("extracting")
        # Round robin avoids spending the whole budget on the first document.
        for round_parts in zip_longest(*batches):
            for document, pages in zip(parsed, round_parts):
                if pages is None:
                    continue
                try:
                    extraction, rejected = extractor.extract(document, pages)
                    warnings.extend(rejected)
                    processed += 1
                    for statement in extraction.narratives:
                        narratives[fingerprint(statement.model_dump(mode="json"))] = statement
                    for fact in extraction.facts:
                        facts[fingerprint(fact.model_dump(mode="json"))] = fact
                except BudgetExceeded:
                    continue  # Cached later chunks can still be reused for free.
                except ModelError as exc:
                    warnings.append(str(exc))
                    # Avoid repeated quota/auth/schema failures within the same run.
                    break
            else:
                continue
            break
        if processed < total:
            warnings.append(f"Partial extraction: processed {processed} of {total} chunks within model-call budget. Missing findings are not evidence of absence.")
        if processed == 0 and model.calls > 0:
            raise ModelError("No extraction completed successfully; the prior saved research was preserved. Check model access/schema/quota.")
        if not facts:
            warnings.append("No validated actual financial facts extracted; comparisons may be unavailable.")
        progress("comparing")
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        facts = list(facts.values())
        narratives = list(narratives.values())
        report = ResearchReport(ticker=ticker, generated_at=utc_now(), model=self.settings.gemini_model, documents=[document.source for document in parsed] + [link for link in links if link.kind == DocumentKind.ANNUAL_REPORT][:1], narratives=narratives, facts=facts, comparisons=[compare(statement, facts, today) for statement in narratives], warnings=list(dict.fromkeys(warnings)), model_calls=model.calls, cache_hits=model.cache_hits, chunks_total=total, chunks_processed=processed, coverage="processed" if processed == total and len(parsed) == len(selected) else "partial")
        self.store.put("research-v1", ticker, report.model_dump(mode="json"))
        progress("complete")
        return report

    def refresh(self, ticker: str, days=1, price_threshold=3., volume_multiple=2., categories=None, force=False):
        ticker = normalize_ticker(ticker)
        items, warnings, bars, events = [], [], [], []
        try:
            bars = MarketSource(self.store).fetch(ticker, refresh=force)
            items.extend(market_attention(ticker, bars, price_threshold, volume_multiple))
            if len(bars) < 21:
                warnings.append("Insufficient market history for a 20-session volume baseline.")
        except Exception as exc:
            warnings.append(f"EOD data unavailable: {type(exc).__name__}")
        try:
            events = NSESource(self.store, self.settings.finn_http_timeout).fetch(ticker, days=days, refresh=force)
            now = datetime.now(ZoneInfo("Asia/Kolkata"))
            cutoff = now - timedelta(days=days)
            events = [event for event in events if cutoff <= event.published_at <= now]
            for event in events:
                item = announcement_attention(event, set(categories) if categories is not None else None)
                if item:
                    items.append(item)
        except Exception as exc:
            warnings.append(f"Exchange filings unavailable: {type(exc).__name__}")
        data = {"ticker": ticker, "refreshed_at": utc_now(), "window_days": days, "thresholds": {"price_percent": price_threshold, "volume_multiple": volume_multiple}, "categories": categories, "items": [item.model_dump(mode="json") for item in sorted(items, key=lambda item: item.occurred_at, reverse=True)], "filing_count": len(events), "price_bar_count": len(bars), "warnings": warnings}
        self.store.put("attention-v1", ticker, data)
        return data
