from statistics import mean

from finn.domain import Announcement, AttentionItem, PriceBar, fingerprint


def market_attention(ticker: str, bars: list[PriceBar], price_threshold=5., volume_multiple=2., lookback=20) -> list[AttentionItem]:
    if len(bars) < lookback + 1:
        return []  # Caller separately reports inadequate coverage.
    bars = sorted(bars, key=lambda bar: bar.date)
    latest, previous = bars[-1], bars[-2]
    baseline = mean(bar.volume for bar in bars[-lookback - 1:-1])
    result = []
    change = (latest.close / previous.close - 1) * 100
    if not latest.split and abs(change) >= price_threshold:
        result.append(AttentionItem(item_id=fingerprint([ticker, str(latest.date), "price"]), ticker=ticker, kind="price", title=f"Daily close moved {change:+.2f}%", reason=f"Exceeded your {price_threshold:g}% threshold; unadjusted close, review corporate actions.", occurred_at=str(latest.date), source_url=f"https://finance.yahoo.com/quote/{ticker}.NS/history/"))
    if baseline > 0 and latest.volume / baseline >= volume_multiple:
        multiple = latest.volume / baseline
        result.append(AttentionItem(item_id=fingerprint([ticker, str(latest.date), "volume"]), ticker=ticker, kind="volume", title=f"Volume {multiple:.2f}x its prior {lookback}-session average", reason=f"Exceeded your {volume_multiple:g}x threshold; the current session is excluded from the baseline.", occurred_at=str(latest.date), source_url=f"https://finance.yahoo.com/quote/{ticker}.NS/history/"))
    return result


def announcement_attention(event: Announcement, categories: set[str] | None = None) -> AttentionItem | None:
    """Initial triage, not deep filing analysis; uncertain material filings explicitly need review."""
    text = f"{event.subject} {event.description}".lower()
    material = {
        "management_change": ["resignation of chief", "resignation of cfo", "resignation of ceo", "change in management", "change in director", "appointment of chief"],
        "M&A": ["acquisition", "merger", "demerger", "joint venture"],
        "litigation": ["regulatory order", "penalty", "insolvency", "fraud", "default"],
        "credit_rating": ["downgrade"],
    }
    category = next((category for category, terms in material.items() if any(term in text for term in terms)), None)
    # Material language takes precedence over a routine-looking title.
    if category is None and any(term in text for term in ["newspaper", "trading window", "compliance certificate", "meeting intimation", "board meeting intimation", "investor meet", "earnings call", "transcript", "recording"]):
        return None
    if category is None and any(term in text for term in ["financial result", "quarterly result"]):
        category = "results"
    if category is None:
        return None  # Remains in the complete filing archive, not assumed unimportant.
    if categories is not None and category not in categories:
        return None
    return AttentionItem(item_id=event.event_id, ticker=event.ticker, kind=category, title=event.subject, reason=f"Potentially material {category} disclosure. Review the original filing; content-level materiality is not yet verified.", occurred_at=event.published_at.isoformat(), source_url=event.source_url, review_required=True)
