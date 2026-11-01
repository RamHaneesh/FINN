import hashlib
from io import BytesIO
import os
from pathlib import Path
from uuid import uuid4

from pypdf import PdfReader

from finn.domain import DocumentLink, Page, ParsedDocument, fingerprint, utc_now
from finn.sources.http import PublicHTTP, SourceError
from finn.storage import Store

PARSER_VERSION = "pypdf-pages-v1"


class DocumentService:
    def __init__(self, store: Store, http: PublicHTTP, max_mb=30):
        self.store, self.http, self.max_mb = store, http, max_mb

    def ingest(self, link: DocumentLink, refresh=False) -> ParsedDocument:
        key = fingerprint([link.ticker, link.url])
        cached = None if refresh else self.store.get("document-url-v1", key, max_age=24 * 3600)
        if cached:
            parsed = self.store.get(PARSER_VERSION, cached["document_id"])
            if parsed:
                return ParsedDocument.model_validate(parsed)
        raw = self.http.fetch(link.url, max_bytes=self.max_mb * 1024 * 1024)
        if not raw.lstrip().startswith(b"%PDF-"):
            raise SourceError("Source did not return a PDF; HTML/scanned document support is not available yet")
        content_hash = hashlib.sha256(raw).hexdigest()
        document_id = fingerprint([link.ticker, link.url, content_hash])
        path = self.store.blobs / f"{content_hash}.pdf"
        if not path.exists():
            temporary = path.with_suffix(f".{uuid4().hex}.tmp")
            temporary.write_bytes(raw)
            os.replace(temporary, path)
        cached_parsed = self.store.get(PARSER_VERSION, document_id)
        if cached_parsed:
            document = ParsedDocument.model_validate(cached_parsed)
        else:
            document = self.parse(raw, link, document_id, content_hash)
            self.store.put(PARSER_VERSION, document_id, document.model_dump(mode="json"), ticker=link.ticker)
        self.store.put("document-url-v1", key, {"document_id": document_id}, ticker=link.ticker)
        return document

    @staticmethod
    def parse(raw: bytes, link: DocumentLink, document_id: str, content_hash: str) -> ParsedDocument:
        try:
            reader = PdfReader(BytesIO(raw))
            if len(reader.pages) > 800:
                raise SourceError("PDF exceeds the prototype's 800-page parsing limit")
            pages = [Page(number=i + 1, text=page.extract_text() or "") for i, page in enumerate(reader.pages)]
        except SourceError:
            raise
        except Exception as exc:
            raise SourceError("PDF parsing failed; document retained for inspection") from exc
        if sum(len(page.text.strip()) for page in pages) < 100:
            raise SourceError("Insufficient PDF text; this document may require OCR")
        return ParsedDocument(document_id=document_id, content_hash=content_hash, source=link, pages=pages, fetched_at=utc_now())


def chunks(document: ParsedDocument, max_chars: int) -> list[list[Page]]:
    """Keep page citations, split oversized pages, and expose complete chunk counts."""
    result, current, size = [], [], 0
    for page in document.pages:
        for start in range(0, len(page.text), max_chars):
            piece = Page(number=page.number, text=page.text[start:start + max_chars])
            if size + len(piece.text) > max_chars and current:
                result.append(current)
                current, size = [], 0
            current.append(piece)
            size += len(piece.text)
    if current:
        result.append(current)
    return result
