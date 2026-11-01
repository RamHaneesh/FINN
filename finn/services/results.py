"""Primary results extraction runs only in the worker, never in a page request."""
from datetime import date

from finn.documents import chunks
from finn.domain import Announcement, DocumentLink
from finn.extraction import Extractor
from finn.models import Gemini
from finn.sources.financials import FinancialSource
from finn.sources.http import SourceError

TO_CRORE = {"INR_crore": 1., "INR_lakh": .01, "INR_million": .1, "INR_billion": 100.}


def extract_headlines(pipeline, event_data):
    event = Announcement.model_validate(event_data)
    saved = pipeline.store.get("results-headlines-v1", event.event_id)
    if saved:
        return saved
    if not event.source_url:
        raise SourceError("No original results attachment available")
    link = DocumentLink(ticker=event.ticker, url=event.source_url, kind="results", title=event.subject, discovery_url="https://www.nseindia.com/companies-listing/corporate-filings-announcements", published_on=event.published_at.date())
    document = pipeline.documents.ingest(link)
    sections = chunks(document, pipeline.settings.finn_chunk_chars)
    sections.sort(key=lambda pages: -sum(page.text.lower().count(term) for page in pages for term in ["revenue from", "profit before tax", "profit after tax", "ebitda", "quarter ended"]))
    model = Gemini(pipeline.settings, pipeline.store, max_calls=min(2, pipeline.settings.finn_max_model_calls))
    facts, warnings = [], []
    for pages in sections[:2]:
        extraction, issues = Extractor(model).extract(document, pages)
        facts.extend(extraction.facts)
        warnings.extend(issues)
    basis = "consolidated" if any(fact.basis == "consolidated" for fact in facts) else "standalone"
    periods = {}
    for fact in facts:
        if fact.metric not in {"revenue", "ebitda", "pbt", "pat"} or not fact.period_start or not fact.period_end or fact.basis != basis or fact.unit not in TO_CRORE or not 70 <= (fact.period_end - fact.period_start).days <= 100:
            continue
        key = str(fact.period_end)
        row = periods.setdefault(key, {"label": fact.period_end.strftime("%b %Y"), "end": key, "start": str(fact.period_start)})
        value = fact.value * TO_CRORE[fact.unit]
        if fact.metric in row and row[fact.metric] != value:
            row[fact.metric] = None  # Conflicting disclosed values require review.
        elif fact.metric not in row:
            row[fact.metric] = value
    if not periods:
        raise SourceError("No verified comparable quarter values extracted from this filing")
    snapshot = {"history": [periods[key] for key in sorted(periods)], "source_url": event.source_url}
    result = FinancialSource.headlines(snapshot, event.published_at.date())
    result.update(source_type="primary_filing", basis=basis, document_id=document.document_id, warnings=warnings, model_calls=model.calls)
    pipeline.store.put("results-headlines-v1", event.event_id, result)
    return result


def enqueue_results(pipeline, limit=2):
    from finn.signals.classifier import classify
    candidates = {}
    for records in pipeline.store.values("announcements-v1"):
        for event in records:
            category = classify(event["subject"], event["description"])
            if category["category"] == "results" and category["priority"] == "high" and event.get("source_url") and not pipeline.store.get("results-headlines-v1", event["event_id"]):
                candidates[event["event_id"]] = event
    latest = sorted(candidates.values(), key=lambda event: event["published_at"], reverse=True)[:limit]
    return [pipeline.store.enqueue(event["ticker"], {"_kind": "headlines", "event": event}) for event in latest]
