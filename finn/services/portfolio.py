from datetime import date, datetime, time, timedelta
import json
from zoneinfo import ZoneInfo

from finn.config import ROOT
from finn.domain import Announcement, PriceBar, normalize_ticker
from finn.domain import Narrative, FinancialFact
from finn.analysis import compare
from finn.analysis.guidance import guidance_review
from finn.extraction.extractor import qualify_narrative
from finn.signals.classifier import CATEGORIES, classify
from finn.signals.rules import market_attention
from finn.sources.financials import FinancialSource
from finn.services.filing_display import management_fields
from finn.services.trajectory import cached_trajectory
from finn.sources.profile import CACHE as PROFILE_CACHE


class PortfolioService:
    def __init__(self, pipeline):
        self.pipeline, self.store = pipeline, pipeline.store
        self.companies = json.loads((ROOT / "config/portfolio.json").read_text())["companies"]

    def preferences(self):
        return self.store.get("preferences-v1", "default") or {"price_percent": 3., "volume_multiple": 2.}

    def company(self, ticker):
        ticker = normalize_ticker(ticker)
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        portfolio = next((company for company in self.companies if company["ticker"] == ticker), {})
        saved = self.store.get('company-view-v1',ticker)
        if saved and saved.get('as_of') == str(today) and saved.get('sector') == portfolio.get('sector'):
            return saved['data']
        snapshot = self.store.get("financials-v1", ticker)
        business = self.store.get(PROFILE_CACHE, ticker)
        research = self.store.get("research-v1", ticker)
        if research:
            statements = [qualify_narrative(Narrative.model_validate(item)) for item in research["narratives"]]
            facts = [FinancialFact.model_validate(item) for item in research["facts"]]
            research["narratives"] = [item.model_dump(mode="json") for item in statements]
            research["comparisons"] = [compare(item, facts, datetime.now(ZoneInfo("Asia/Kolkata")).date()).model_dump(mode="json") for item in statements]
            research["guidance_review"] = guidance_review(statements, facts, datetime.now(ZoneInfo("Asia/Kolkata")).date(), snapshot)
        portfolio = next((company for company in self.companies if company["ticker"] == ticker), {})
        result = {"ticker": ticker, "name": snapshot.get("name", ticker) if snapshot else (business or {}).get("name", ticker), "sector": portfolio.get("sector", "NSE-listed company"), "snapshot": snapshot, "research": research,
                "trajectory": cached_trajectory(self.store, ticker, snapshot), "business": business,
                "research_availability": self.store.get('research-availability-v1',ticker)}
        self.store.put('company-view-v1',ticker,{'as_of':str(today),'sector':portfolio.get('sector'),'data':result})
        return result

    def digest(self, hours=24):
        settings = self.preferences()
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        cutoff = now - timedelta(hours=hours)
        items, routine, warnings, portfolio, refreshed = [], [], [], [], []
        events = {}
        portfolio_symbols = {company["ticker"] for company in self.companies}
        for window in self.store.values("announcements-v1"):
            for event in window:
                if event["ticker"] in portfolio_symbols:
                    events[event["event_id"]] = event
        for company in self.companies:
            ticker = company["ticker"]
            raw_bars = self.store.get("prices-v1", ticker) or []
            bars = [PriceBar.model_validate(bar) for bar in raw_bars]
            last, previous = (bars[-1] if bars else None), (bars[-2] if len(bars) > 1 else None)
            portfolio.append({**company, "close": last.close if last else None, "change": round((last.close / previous.close - 1) * 100, 2) if last and previous else None, "date": str(last.date) if last else None})
            saved = self.store.get("attention-v1", ticker)
            if saved:
                refreshed.append(saved["refreshed_at"])
                warnings.extend(f"{ticker}: {warning}" for warning in saved.get("warnings", []))
            if bars:
                for item in market_attention(ticker, bars, settings["price_percent"], settings["volume_multiple"]):
                    data = item.model_dump(mode="json")
                    data.update(category=item.kind, priority="high", occurred_at=datetime.combine(last.date, time(16), tzinfo=ZoneInfo("Asia/Kolkata")).isoformat())
                    baseline = sum(bar.volume for bar in bars[-21:-1]) / 20
                    data["market"] = {"volume": last.volume, "average_volume": baseline,
                                      "multiple": last.volume / baseline if baseline else None,
                                      "close": last.close, "previous_close": previous.close,
                                      "change_percent": (last.close / previous.close - 1) * 100}
                    # Latest EOD signals remain active until the next saved session.
                    data["reason"] += " Active for the latest saved trading session."
                    items.append(data)
        for raw in events.values():
            event = Announcement.model_validate(raw)
            if not cutoff <= event.published_at <= now:
                continue
            classification = classify(event.subject, event.description)
            item = {**classification, "item_id": event.event_id, "ticker": event.ticker, "title": event.subject, "reason": event.description or classification["reason"], "occurred_at": event.published_at.isoformat(), "source_url": event.source_url}
            if classification["category"] == "management_change":
                item["management"] = management_fields(event.subject, event.description)
            if classification["category"] == "results" and classification["priority"] == "high":
                primary = self.store.get("results-headlines-v1", event.event_id)
                snapshot = self.store.get("financials-v1", event.ticker)
                standardized = FinancialSource.headlines(snapshot, event.published_at.date()) if snapshot else None
                if primary:
                    primary = dict(primary)
                    primary["metrics"] = [dict(metric, source_type="primary_filing") for metric in primary["metrics"]]
                    if standardized and standardized["latest_period"] == primary["latest_period"] and snapshot["basis"] == primary["basis"]:
                        for index, metric in enumerate(primary["metrics"]):
                            if metric["value"] is None:
                                primary["metrics"][index] = dict(standardized["metrics"][index], source_type="standardized_table")
                        primary["source_type"] = "mixed" if any(metric["source_type"] == "standardized_table" for metric in primary["metrics"]) else "primary_filing"
                item["financials"] = primary or standardized
                annual = (snapshot or {}).get("annual", [])
                if item["financials"] and annual:
                    try:
                        month = datetime.strptime(item["financials"]["latest_period"], "%b %Y").month
                        year_end_month = date.fromisoformat(annual[-1]["end"]).month
                        item["fiscal_quarter"] = ((month-year_end_month-1) % 12)//3+1
                    except (ValueError, KeyError):
                        pass
                if item["financials"]:
                    item["title"] = f"{item['financials']['latest_period']} results filed"
                origin = " Headline values combine filing extraction with marked standardized values." if primary and primary["source_type"] == "mixed" else " Headline values from the original filing." if primary else " Headline values use the saved standardized table; open the filing for primary evidence."
                item["reason"] = (event.description or "Results filed with the exchange.") + origin
            (items if classification["priority"] == "high" else routine).append(item)
        # Group the results release and its exchange attachment into one economic event.
        grouped = {}
        for item in items:
            key = (item["ticker"], "results", item["financials"]["latest_period"]) if item["category"] == "results" and item.get("financials") else item["item_id"]
            if key in grouped:
                previous = grouped[key]
                sources = previous.get("related_sources", [previous["source_url"]]) + [item["source_url"]]
                if item.get("financials", {}).get("source_type") in {"primary_filing", "mixed"}:
                    grouped[key] = item
                grouped[key]["related_sources"] = list(dict.fromkeys(sources))
            else:
                grouped[key] = item
        items = list(grouped.values())
        items.sort(key=lambda item: (item["priority"] != "high", -datetime.fromisoformat(item["occurred_at"]).timestamp()))
        routine.sort(key=lambda item: item["occurred_at"], reverse=True)
        return {"hours": hours, "items": items, "routine": routine, "portfolio": portfolio, "covered_count": sum(company["close"] is not None for company in portfolio), "material_count": sum(item["category"] not in {"price", "volume"} for item in items), "refreshed_at": max(refreshed) if refreshed else None, "warnings": warnings, "settings": settings, "categories": CATEGORIES}

    def refresh(self, progress=lambda stage: None):
        settings = self.preferences()
        failures = []
        for index, company in enumerate(self.companies):
            ticker = company["ticker"]
            progress(f"refreshing_{ticker}_{index + 1}_of_{len(self.companies)}")
            result = self.pipeline.refresh(ticker, days=30, price_threshold=settings["price_percent"], volume_multiple=settings["volume_multiple"])
            failures.extend(result["warnings"])
            try:
                FinancialSource(self.store, self.pipeline.http).fetch(ticker)
            except Exception:
                failures.append(f"{ticker}: financial table unavailable")
        from finn.services.results import enqueue_results
        jobs = enqueue_results(self.pipeline, limit=2)
        return {"companies": len(self.companies), "warnings": failures, "results_jobs": [job["id"] for job in jobs]}
