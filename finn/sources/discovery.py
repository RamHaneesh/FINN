from urllib.parse import urljoin

from bs4 import BeautifulSoup

from finn.domain import DocumentKind, DocumentLink, normalize_ticker
from finn.sources.http import PublicHTTP, SourceError, public_url
from finn.storage import Store


class ScreenerDiscovery:
    def __init__(self, store: Store, http: PublicHTTP):
        self.store, self.http = store, http

    def discover(self, ticker: str, refresh=False) -> list[DocumentLink]:
        ticker = normalize_ticker(ticker)
        cached = None if refresh else self.store.get("discovery-v1", ticker, max_age=6 * 3600)
        if cached is not None:
            return [DocumentLink.model_validate(item) for item in cached]
        for suffix in ["consolidated/", ""]:
            url = f"https://www.screener.in/company/{ticker}/{suffix}"
            try:
                html = self.http.fetch(url, max_bytes=3_000_000)
            except SourceError:
                if suffix:
                    continue
                raise
            links = self.parse(ticker, url, html)
            if links:
                self.store.put("discovery-v1", ticker, [link.model_dump(mode="json") for link in links])
                return links
        raise SourceError("No primary annual reports/transcripts found for this NSE symbol")

    @staticmethod
    def parse(ticker: str, page_url: str, html: bytes) -> list[DocumentLink]:
        soup = BeautifulSoup(html, "html.parser")
        result, seen = [], set()
        for selector, kind in [(".annual-reports a[href]", DocumentKind.ANNUAL_REPORT), (".concalls a[href]", DocumentKind.TRANSCRIPT)]:
            for anchor in soup.select(selector):
                text = anchor.get_text(" ", strip=True)
                if kind == DocumentKind.TRANSCRIPT and text.lower() != "transcript":
                    continue
                if kind == DocumentKind.ANNUAL_REPORT and "annual report" not in text.lower():
                    continue
                url = urljoin(page_url, anchor["href"])
                if "screener.in" in url.split("/")[2] or url in seen:
                    continue  # Never use Screener's AI summaries as evidence.
                try:
                    public_url(url)
                except SourceError:
                    continue
                seen.add(url)
                row = anchor.find_parent("li")
                label = row.get_text(" ", strip=True) if row else text
                result.append(DocumentLink(ticker=ticker, url=url, kind=kind, title=label[:180], discovery_url=page_url))
        # Preserve source ordering (newest first) within each document type.
        return result
