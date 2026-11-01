# FINN

Financial Investment Agent for the ENAM Holdings build challenge. A mobile-first interface is served directly by FastAPI, with cached portfolio intelligence and background transcript analysis.

The focus is management narrative versus actual performance, with source evidence and a selective portfolio attention feed.

## Setup

Use Python 3.12 and the existing isolated environment. For a fresh checkout:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set `GEMINI_API_KEY` in `.env`; the initial model is `gemini-3.5-flash-lite`. See [ENVIRONMENT.md](ENVIRONMENT.md) for authentication and live checks. There is no OpenAI dependency or automatic model fallback.

## Start the mobile app

```powershell
.\.venv\Scripts\python -m scripts.serve --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000/`. This starts the UI, API and one embedded background worker. No frontend build or CDN is required. See [MOBILE_TESTING.md](MOBILE_TESTING.md) for phone testing.

To prepare real data on a fresh checkout:

```powershell
.\.venv\Scripts\python -m scripts.prepare_demo --research INFY DIXON --max-calls 6
```

This warms all 35 portfolio companies and both research examples. Uncached transcript extraction consumes Gemini quota. Opening saved views does not parse PDFs or make model calls.

## Pipeline commands

```powershell
# Initialize SQLite and document storage (no network/model calls).
.\.venv\Scripts\python -m scripts.init_db

# Discover primary annual reports and transcripts (network, no model calls).
.\.venv\Scripts\python -m scripts.discover INFY

# First research smoke run: at most one uncached Gemini call.
.\.venv\Scripts\python -m scripts.research INFY --max-documents 1 --max-calls 1

# Broader bounded run; exact repeated chunks reuse cached extraction.
.\.venv\Scripts\python -m scripts.research INFY --max-documents 6 --max-calls 6

# Refresh EOD data and filings, producing preliminary attention cards.
.\.venv\Scripts\python -m scripts.refresh INFY RELIANCE --days 7 --price-percent 3 --volume-multiple 2

# All 35 coverage holdings; fetches sequentially to avoid source bursts.
.\.venv\Scripts\python -m scripts.refresh --portfolio

# Offline correctness tests; no provider calls or live finance requests.
.\.venv\Scripts\python -m unittest discover -s tests -v
```

`--refresh` on research refetches source documents. Content hashes preserve cached model results when the document is unchanged. `--max-calls 0` allows cached extraction only. The server-configured model-call cap also applies. Reports explicitly disclose unprocessed chunks; partial extraction is never presented as complete company research.

Reports, raw PDFs, parsed pages and SQLite are stored beneath `data/`. The pre-warmed database and source evidence are included in Git so a fresh deployment starts with all 35 covered companies. Override using `FINN_DATA_DIR` for a persistent deployment volume; an empty volume is automatically seeded at server startup from the bundled `data/` directory. Existing databases are never overwritten. Repeated source listings have separate freshness limits: discovery six hours, document URL one day, prices one hour and filings fifteen minutes.

## API and worker

Alternatively, run these in separate terminals without the embedded-worker server:

```powershell
.\.venv\Scripts\python -m uvicorn finn.api.app:app --host 127.0.0.1 --port 8000
.\.venv\Scripts\python -m scripts.worker
```

Open `http://127.0.0.1:8000/docs` to inspect the API. Submit `POST /api/research` with `{"ticker":"INFY","max_calls":1,"max_documents":1}`, then poll `/api/jobs/{id}`. Repeated active requests are deduplicated. Completed research is available at `/api/companies/INFY/research`. `/api/attention` serves saved refresh snapshots.

`/api/evidence/{document_id}?page=4` returns the saved source metadata and page text for checking a citation without another network/model call.

`/api/companies/INFY/filings?days=7` serves the full cached filing archive for that fetched window, including routine filings. Announcement attention cards use an exact rolling time cutoff; the archive retains the exchange's date-window response.

Run exactly one worker for now. Jobs persist in SQLite; an interrupted running job is eligible for recovery after thirty minutes without progress. This is a development API: production access control, hosting and automatic refresh scheduling remain to be implemented.

## Modules

| Module | Responsibility |
|---|---|
| `finn/sources` | NSE symbols, Screener primary-document discovery, NSE announcements and Yahoo EOD |
| `finn/documents` | Bounded PDF downloads, content hashing, page-preserving parsing and chunking |
| `finn/extraction` | Structured financial/narrative extraction and exact source-quote checks |
| `finn/models` | Gemini-only calls, per-run budgets, cache and usage logging |
| `finn/analysis` | Period/basis/currency matching and deterministic numerical verdicts |
| `finn/signals` | EOD thresholds and conservative filing triage |
| `finn/storage` | SQLite metadata, versioned caches and persistent jobs |
| `finn/jobs` | One-worker execution, progress and failure states |
| `finn/api` | Research requests, saved results, jobs and attention snapshots |
| `scripts` | Initialization, discovery, research, portfolio refresh and worker entry points |

## Current boundaries

- Narrative uses original earnings-call transcripts; annual reports remain linked in the source library. Fast financial snapshots and labeled calculated actuals use standardized Screener tables, as requested. Screener AI summaries are not used.
- Source quotations are verified against PDF page text. That does not prove the model interpreted the number, date or reporting basis correctly; manual financial verification remains necessary.
- The validator rejects EBITDA records without explicit EBITDA evidence, percentage records without percentage units in the quote, and numeric values absent from the supporting quote. Model instructions alone are not treated as sufficient validation.
- Guidance comparison refuses mismatched periods, reporting bases, currency bases, scopes and conflicting actuals. Directional expectations are extracted but require a baseline before verdicts. Aspirations remain context.
- Results cards show Revenue, EBITDA, PBT and PAT with QoQ/YoY deltas. Original-filing extraction runs in background jobs; marked standardized values fill gaps. Standardized EBITDA* is a derived proxy (PBT + interest + depreciation - other income), cross-checked against operating profit and excluded from guidance matching. Operating margin is not silently substituted for EBITDA margin.
- PDF scans requiring OCR, HTML-only transcripts, blocked exchange downloads, comprehensive BSE fallback and company-IR discovery adapters are not implemented yet. Failures remain visible.
- Announcement triage covers all 17 categories, with results, management changes, M&A, litigation and capital raises ranked high. Routine filings stay collapsed. Future approval notices stay routine; related results releases/attachments are grouped. Deep materiality still requires original-filing review.
- The latest four discovered transcripts are not guaranteed to represent four distinct fiscal quarters. Research reports disclose limited coverage; explicit quarter selection is a follow-up.
- No broker/news research, trading execution, native notifications, paid-model fallback is included.

## Verified initial run

On October 31, 2026, a one-document/one-call Infosys transcript run produced one accepted revenue-growth narrative and two actual growth facts with page citations. Two operating-margin records mislabeled by the model as EBITDA were rejected by the deterministic validator. The guidance is pending because its target fiscal year has not ended. This is a partial-document smoke run, not a completed four-quarter comparison.

An identical cache-only run used zero model calls. A live refresh retrieved 64 daily price/volume bars and eight exchange filings for the seven-day source window, with no attention cards triggered by the initial rules. No absence-of-risk conclusion follows from an empty attention feed.

The offline checks cover numerical matching, evidence rejection, market baselines, source discovery, cache reuse, job deduplication/recovery and API-to-worker execution.

See [WORKPLAN.md](WORKPLAN.md) for the full assessment scope and execution milestones.


Coverage cache preparation:

```powershell
.\.venv\Scripts\python -m scripts.warm_universe --max-calls 6 --wait
.\.venv\Scripts\python -m scripts.audit_universe
```

Keep `scripts.serve` running while warming so its single worker consumes queued research. The script reuses saved sections and reports missing primary transcripts honestly. The local HTTP audit writes `COVERAGE_STATUS.md` and detailed timing samples to `tmp/universe-latency.json`. `config/portfolio.json` is the exact 35-label coverage list; ZOMATO and TATAMOTORS explicitly resolve to ETERNAL and TMPV source data. These legacy labels remain visible in the watchlist and search. All coverage members are pinned against ad-hoc cache eviction.


The repository includes the pre-warmed `data/finn.sqlite3`, cached source PDFs/JSON, code, configuration, tests and documentation. Credentials, `.venv/`, `__pycache__/`, temporary logs, SQLite transient journals/locks and screenshots are ignored. Cache warming is optional for refreshing data, not a deployment prerequisite.

## Render / Railway startup

Build command: `pip install -r requirements.txt`

Start command: `python -m scripts.serve --host 0.0.0.0`

The server reads the platform's `PORT` automatically and starts its background worker. With the default settings it opens the committed pre-warmed database directly. If a persistent disk is mounted, set `FINN_DATA_DIR` to its writable directory (for example `/var/data/finn`); on first startup the bundled database and evidence files are copied there without source requests or model calls. Later starts preserve the volume's existing database. Use one application process/replica for this SQLite prototype.

All 35 companies have saved profiles, financial snapshots and five-year trajectories. Narrative reports are available for 34; TRENT retains its explicit no-primary-transcript availability record. Saved research is usable without a Gemini key; configure `GEMINI_API_KEY` in platform secrets to enable new analysis and refreshes. Fresh source prices/filings and new searches still require network access. Saved data retains its original timestamps; deployment does not make it live data.
