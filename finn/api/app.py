from contextlib import asynccontextmanager
import json
import threading

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field, field_validator

from finn.config import ROOT, get_settings
from finn.domain import normalize_ticker
from finn.documents.parser import PARSER_VERSION
from finn.pipeline import Pipeline
from finn.services.portfolio import PortfolioService


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.pipeline = Pipeline(get_settings())
    stop = threading.Event()
    if app.state.pipeline.settings.finn_embedded_worker:
        from finn.jobs.worker import run_once
        def worker_loop():
            while not stop.is_set():
                if not run_once(app.state.pipeline):
                    stop.wait(.5)
        threading.Thread(target=worker_loop, daemon=True, name="finn-worker").start()
    yield
    stop.set()


app = FastAPI(title="FINN", version="0.1.0", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.mount("/assets", StaticFiles(directory=ROOT / "web/src"), name="assets")


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT / "web/index.html", headers={"Cache-Control": "no-cache"})


@app.get("/api/digest")
def digest(request: Request, hours: int = Query(default=24, ge=1, le=720)):
    return PortfolioService(request.app.state.pipeline).digest(hours)


@app.get("/api/company/{ticker}")
def company_view(ticker: str, request: Request):
    try:
        data = PortfolioService(request.app.state.pipeline).company(ticker)
        # Send the mobile view only what it renders; full evidence remains in SQLite/API.
        if data["research"]:
            data["research"].pop("facts", None)
            data["research"].pop("narratives", None)
        if data["snapshot"]:
            data["snapshot"].pop("annual", None)
            data["snapshot"]["history"] = data["snapshot"]["history"][-4:]
        return data
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None


class Preferences(BaseModel):
    price_percent: float = Field(default=3, gt=0, le=50)
    volume_multiple: float = Field(default=2, ge=1, le=20)


@app.put("/api/preferences")
def preferences(body: Preferences, request: Request):
    request.app.state.pipeline.store.put("preferences-v1", "default", body.model_dump())
    return body


@app.post("/api/refresh", status_code=202)
def refresh_portfolio(request: Request):
    return request.app.state.pipeline.store.enqueue("PORTFOLIO", {"_kind": "refresh"})


class ResearchRequest(BaseModel):
    ticker: str
    max_documents: int = Field(default=5, ge=1, le=6)
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
    report = PortfolioService(request.app.state.pipeline).company(ticker)["research"]
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
