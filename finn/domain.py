"""Shared contracts; missing values never become financial zeroes."""
from datetime import date, datetime, timezone
from enum import StrEnum
import hashlib
import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fingerprint(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper().removesuffix(".NS")
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9&-]{0,24}", ticker):
        raise ValueError("Use an NSE symbol such as INFY or RELIANCE.NS")
    return ticker


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class DocumentKind(StrEnum):
    TRANSCRIPT = "transcript"
    ANNUAL_REPORT = "annual_report"
    RESULTS = "results"


class DocumentLink(Contract):
    ticker: str
    url: str
    kind: DocumentKind
    title: str
    discovery_url: str
    published_on: date | None = None


class Page(Contract):
    number: int = Field(ge=1)
    text: str


class ParsedDocument(Contract):
    document_id: str
    content_hash: str
    source: DocumentLink
    pages: list[Page]
    fetched_at: str


class Citation(Contract):
    document_id: str
    url: str
    page: int = Field(ge=1)
    quote: str = Field(min_length=8)


Metric = Literal["revenue_growth_yoy", "revenue_growth_qoq", "ebitda_margin", "revenue", "ebitda", "pbt", "pat"]
Unit = Literal["percent", "INR_crore", "INR_lakh", "INR_million", "INR_billion", "USD_million", "unknown"]


class FinancialContext(Contract):
    metric: Metric
    period_start: date | None = None
    period_end: date | None = None
    basis: Literal["consolidated", "standalone", "unknown"] = "unknown"
    scope: str = "unknown"
    currency_basis: Literal["reported", "constant_currency", "not_applicable", "unknown"] = "unknown"
    unit: Unit = "unknown"

    @model_validator(mode="after")
    def ordered_period(self):
        if self.period_start and self.period_end and self.period_start > self.period_end:
            raise ValueError("Period start must precede period end")
        return self


class Narrative(FinancialContext):
    narrative_type: Literal["guidance", "directional", "aspiration", "unclear"]
    stated_on: date | None = None
    lower: float | None = None
    upper: float | None = None
    direction: Literal["increase", "decrease", "stable"] | None = None
    citation: Citation

    @model_validator(mode="after")
    def ordered_target(self):
        if self.lower is not None and self.upper is not None and self.lower > self.upper:
            raise ValueError("Target bounds reversed")
        return self


class FinancialFact(FinancialContext):
    value: float
    reported_on: date | None = None
    citation: Citation


class Comparison(Contract):
    narrative: Narrative
    actual: FinancialFact | None = None
    status: Literal["Met", "Missed", "Pending", "Cannot compare"]
    relationship: Literal["within", "above", "below", "unavailable"] = "unavailable"
    explanation: str
    difference: float | None = None


class PriceBar(Contract):
    date: date
    close: float = Field(gt=0)
    volume: int = Field(ge=0)
    split: float = 0


class Announcement(Contract):
    event_id: str
    ticker: str
    subject: str
    description: str
    published_at: datetime
    source_url: str | None = None


class AttentionItem(Contract):
    item_id: str
    ticker: str
    kind: str
    title: str
    reason: str
    occurred_at: str
    source_url: str | None = None
    review_required: bool = False


class ResearchReport(Contract):
    ticker: str
    generated_at: str
    model: str
    documents: list[DocumentLink]
    narratives: list[Narrative]
    facts: list[FinancialFact]
    comparisons: list[Comparison]
    warnings: list[str]
    model_calls: int
    cache_hits: int
    chunks_total: int
    chunks_processed: int
    coverage: Literal["partial", "processed"]
