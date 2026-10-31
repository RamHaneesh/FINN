from contextlib import asynccontextmanager
import json

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from finn.config import ROOT, get_settings
from finn.domain import normalize_ticker
from finn.documents.parser import PARSER_VERSION
from finn.pipeline import Pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pipeline = Pipeline(get_settings())
    yield


app = FastAPI(title="FINN", version="0.1.0", lifespan=lifespan)


class ResearchRequest(BaseModel):
    ticker: str
    max_documents: int = Field(default=6, ge=1, le=6)
    max_calls: int = Field(default=6, ge=0, le=20)
    refresh: bool = False

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, value):
        return normalize_ticker(value)


@app.get("/api/health")
def health(request: Request):
    return {"status": "ok", "model": request.app.state.pipeline.settings.gemini_model, "worker_required": True}


@app.get("/api/portfolio")
def portfolio():
    return json.loads((ROOT / "config" / "portfolio.json").read_text())


@app.post("/api/research", status_code=202)
def start_research(body: ResearchRequest, request: Request):
    payload = body.model_dump(exclude={"ticker"})
    payload["max_calls"] = min(payload["max_calls"], request.app.state.pipeline.settings.finn_max_model_calls)
    return request.app.state.pipeline.store.enqueue(body.ticker, payload)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str, request: Request):
    job = request.app.state.pipeline.store.job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@app.get("/api/companies/{ticker}/research")
def research(ticker: str, request: Request):
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    report = request.app.state.pipeline.store.get("research-v1", ticker)
    if report is None:
        raise HTTPException(404, "No saved research; submit a research job first")
    return report


@app.get("/api/attention")
def attention(request: Request):
    records = request.app.state.pipeline.store.values("attention-v1")
    return {"companies": records, "status": "saved snapshots; refresh with the CLI"}


@app.get("/api/companies/{ticker}/filings")
def filings(ticker: str, request: Request, days: int = Query(default=7, ge=1, le=90)):
    try:
        ticker = normalize_ticker(ticker)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    records = request.app.state.pipeline.store.get("announcements-v1", f"{ticker}:{days}")
    if records is None:
        raise HTTPException(404, "No saved filing window; run the refresh script with this window first")
    return {"ticker": ticker, "window_days": days, "filings": records, "status": "source date-window archive, including routine filings"}


@app.get("/api/evidence/{document_id}")
def evidence(document_id: str, request: Request, page: int = Query(ge=1)):
    document = request.app.state.pipeline.store.get(PARSER_VERSION, document_id)
    if document is None:
        raise HTTPException(404, "Document not found")
    selected = next((item for item in document["pages"] if item["number"] == page), None)
    if selected is None:
        raise HTTPException(404, "PDF page not found")
    return {"document_id": document_id, "source": document["source"], "page": selected}
