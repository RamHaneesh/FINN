"""Cached official NSE company directory for typeahead; no financial/model requests."""
import csv
from io import StringIO
import json

from finn.config import ROOT
from finn.domain import normalize_ticker, utc_now
from finn.sources.http import SourceError

DIRECTORY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"


class SymbolDirectory:
    def __init__(self, store, http):
        self.store, self.http = store, http

    def listing(self):
        cached = self.store.get("symbols-v1", "NSE")
        if cached:
            # Preserve explicitly configured legacy watchlist labels in search as well.
            from finn.sources.universe import COMPANIES
            known={item['ticker'] for item in cached['symbols']}
            for company in COMPANIES:
                if company['ticker'] in known:
                    continue
                snapshot=self.store.get('financials-v1',company['ticker']) or {}
                cached['symbols'].append({'ticker':company['ticker'],'name':snapshot.get('name',company['ticker']),
                                          'source_ticker':company.get('source_ticker',company['ticker'])})
            return cached
        companies = json.loads((ROOT / "config/portfolio.json").read_text())["companies"]
        items = []
        for company in companies:
            snapshot = self.store.get("financials-v1", company["ticker"]) or {}
            items.append({"ticker": company["ticker"], "name": snapshot.get("name", company["ticker"])})
        return {"symbols": items, "complete": False, "source": DIRECTORY_URL, "updated_at": None}

    def warm(self):
        if self.store.get("symbols-v1", "NSE", max_age=7 * 24 * 3600):
            return
        raw = self.http.fetch(DIRECTORY_URL, max_bytes=3_000_000)
        result = self.parse(raw)
        self.store.put("symbols-v1", "NSE", {"symbols": result, "complete": True, "source": DIRECTORY_URL, "updated_at": utc_now()})

    @staticmethod
    def parse(raw):
        reader = csv.DictReader(StringIO(raw.decode("utf-8-sig")))
        if not reader.fieldnames or "SYMBOL" not in reader.fieldnames:
            raise SourceError("NSE directory schema not recognized")
        symbols = {}
        for row in reader:
            row = {key.strip(): value.strip() for key, value in row.items() if key and value is not None}
            if row.get("SERIES") != "EQ":
                continue
            try:
                ticker = normalize_ticker(row["SYMBOL"])
            except (ValueError, KeyError):
                continue
            symbols[ticker] = {"ticker": ticker, "name": row.get("NAME OF COMPANY") or ticker}
        if not symbols:
            raise SourceError("NSE directory contains no usable equity symbols")
        return sorted(symbols.values(), key=lambda item: item["ticker"])
