from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx

from finn.domain import Announcement, fingerprint, normalize_ticker
from finn.sources.http import SourceError
from finn.storage import Store
from finn.sources.universe import source_symbol


class NSESource:
    def __init__(self, store: Store, timeout=30):
        self.store, self.timeout = store, timeout

    def fetch(self, ticker: str, days=30, refresh=False) -> list[Announcement]:
        ticker = normalize_ticker(ticker)
        key = f"{ticker}:{days}"
        cached = None if refresh else self.store.get("announcements-v1", key, max_age=900)
        if cached is not None:
            return [Announcement.model_validate(row) for row in cached]
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        with httpx.Client(timeout=self.timeout, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"}) as client:
            client.get("https://www.nseindia.com/")
            response = client.get("https://www.nseindia.com/api/corporate-announcements", params={"index": "equities", "symbol": source_symbol(ticker), "from_date": (today - timedelta(days=days)).strftime("%d-%m-%Y"), "to_date": today.strftime("%d-%m-%Y")})
        if response.status_code != 200:
            raise SourceError(f"NSE returned HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError("NSE returned non-JSON content") from exc
        if not isinstance(payload, list):
            raise SourceError("NSE announcement schema changed")
        events = []
        for row in payload:
            if row.get("symbol", "").upper() != source_symbol(ticker):
                continue
            raw_date = row.get("an_dt") or row.get("sort_date")
            parsed = None
            for fmt in ["%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S"]:
                try:
                    parsed = datetime.strptime(raw_date, fmt).replace(tzinfo=ZoneInfo("Asia/Kolkata"))
                    break
                except (ValueError, TypeError):
                    pass
            if parsed is None:
                raise SourceError("Unrecognized NSE timestamp; refusing to drop an undated filing")
            url = row.get("attchmntFile") or None
            event = Announcement(event_id=fingerprint([ticker, url or row, raw_date]), ticker=ticker, subject=row.get("desc", ""), description=row.get("attchmntText", "") or "", published_at=parsed, source_url=url)
            events.append(event)
        self.store.put("announcements-v1", key, [item.model_dump(mode="json") for item in events])
        return events
