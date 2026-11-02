from datetime import datetime, time
from zoneinfo import ZoneInfo

import yfinance as yf

from finn.domain import PriceBar, normalize_ticker
from finn.sources.http import SourceError
from finn.storage import Store
from finn.sources.universe import source_symbol


class MarketSource:
    def __init__(self, store: Store):
        self.store = store

    def fetch(self, ticker: str, refresh=False) -> list[PriceBar]:
        ticker = normalize_ticker(ticker)
        cached = None if refresh else self.store.get("prices-v1", ticker, max_age=3600)
        if cached is not None:
            return [PriceBar.model_validate(row) for row in cached]
        # Include the 20-session baseline preceding the full 90-day alert archive.
        frame = yf.Ticker(source_symbol(ticker) + ".NS").history(period="6mo", auto_adjust=False, timeout=25)
        if frame.empty:
            raise SourceError("No EOD market data available for this NSE symbol")
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        bars = []
        for index, row in frame.iterrows():
            day = index.date()
            if day == now.date() and now.time() < time(16, 0):
                continue  # Do not present an intraday bar as completed EOD.
            if row[["Close", "Volume"]].isna().any():
                continue
            bars.append(PriceBar(date=day, close=float(row["Close"]), volume=int(row["Volume"]), split=float(row.get("Stock Splits", 0))))
        self.store.put("prices-v1", ticker, [bar.model_dump(mode="json") for bar in bars])
        return bars
