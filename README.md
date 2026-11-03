# FINN — Financial Investment Agent

**A mobile-first investment research prototype for the ENAM Holdings AI Engineer Build Challenge.**

[Open the live demo](https://finn-investment-agent-f3ra.onrender.com/) · No login required

FINN helps investors answer two questions: **What changed in my portfolio?** and **Did management deliver what it promised?**

| View | What it does |
|---|---|
| **Push Digest** | Tracks 18 fixed portfolio companies and highlights material filings and unusual price/volume moves. |
| **Pull Deep Dive** | Researches any supported NSE ticker, including companies outside the portfolio. Opens saved sections first and fills missing data in the background. |

**Try it in two minutes:** Open Push Digest, select **Last 7 days**, and tap a source badge. Then open Pull Deep Dive and search **INFY**, **DMART**, or another NSE ticker to explore the business, financials, and management guidance.

## 1. What I Built

### Push Digest

- **Material alerts:** Results, management changes, capital raises, M&A, and legal/risk events. Routine filings stay in an expandable section.
- **Market moves:** Flags price changes of at least ±3% or volume above 2× the previous 20-session average. Thresholds can be changed in **Preferences**.
- **Results cards:** Revenue, EBITDA, PBT, and PAT with quarter-on-quarter (QoQ) and year-on-year (YoY) changes where available.
- **Portfolio ticker tape:** Swipe through the 18 holdings to see saved closing prices and daily changes.
- **Source badges:** Open the filing or EOD price source directly from an alert.

### Pull Deep Dive

**Search any supported NSE company—not just the pre-warmed list.** The initial 50 companies are cached to give reviewers a faster first experience. Try a 51st company such as **CLEAN**, or any other NSE ticker you want to research. FINN fetches missing sections automatically; first-time analysis depends on source availability and Gemini quota. The 50-company limit applies only to saved research at a time, not the searchable universe.

Sections appear in this order:

| Section | What you see |
|---|---|
| **Business snapshot** | A short company description, plus products, brands, and segments disclosed in its profile. |
| **Financial snapshot** | Quarterly Revenue, EBITDA, PBT, and PAT with QoQ/YoY changes. |
| **5-year trajectory** | Up to five completed financial years: Revenue, revenue growth, EBITDA margin, and PAT, with Revenue/PAT CAGR summaries. |
| **Narrative vs. Numbers** | Clear historical guidance comparisons marked **Met** or **Missed**, with source evidence. Future targets appear separately under **Active Guidance**. |

Qualitative commentary is shown when strict numerical comparisons are unavailable. Vague or unmatched statements stay in expandable context sections rather than appearing as failed comparisons.

## 2. Why Narrative vs. Numbers

Management promises and actual results are spread across documents and quarters. FINN puts the target, outcome, and evidence on one screen. Business and financial snapshots support this main workflow.

### Deliberately deferred

Cash-flow forensics, detailed debt schedules, and bull/bear debates need further data and validation, so they are outside this prototype.

## 3. Architecture and Technical Decisions

### Stack

| Layer | Technology |
|---|---|
| Interface | Responsive HTML, CSS, and vanilla JavaScript; no frontend build step |
| API and calculations | Python 3.12, FastAPI, Pydantic |
| Storage | SQLite cache, job queue, and local PDF files |
| Extraction | Gemini through the Google Gen AI SDK; PDF text parsed with pypdf |
| Hosting | One Render service serving the frontend, API, worker, and scheduler |

### Pipeline

```text
Mobile browser → FastAPI → saved SQLite sections
                      │
                      ├─ Push: filings + EOD prices → rules → alert archive → digest
                      │
                      └─ Pull: company profile + financial tables → snapshots/trajectory
                               primary transcripts → background Gemini extraction
                                                   → Python comparison rules
```

### Code calculates; Gemini extracts

Python calculates growth, margins, CAGR, alerts, and verdicts. Gemini extracts guidance from transcripts and financial facts from results filings. Business descriptions come directly from company profiles.

Quotes are checked against source text. Comparisons require matching metrics, periods, units, and reporting basis. Derived EBITDA is labeled and excluded from guidance comparisons.

### Data sources

| Data | Source |
|---|---|
| Push announcements | NSE exchange filings |
| Transcripts and results evidence | Primary company/exchange documents, including BSE/NSE-hosted PDFs |
| Business profiles and standardized financial tables | Screener company pages |
| EOD prices and volumes | Yahoo Finance through yfinance |

The brief names Yahoo Finance for prices, NSE/BSE for filings, and Screener or company investor-relations sites for report/transcript links. The reference glossary also identifies Screener as a source of standardized financials.

Screener profile text and standardized tables provide company context; they are not original company documents. Narrative evidence uses primary transcripts and filings, with source citations. FINN does not use news sentiment, social media, or broker recommendations.

### Separate Push and Pull storage

| Policy | Behavior |
|---|---|
| **Push portfolio** | Fixed membership in `push_portfolio`; protected inputs in `push_cache`. Pull searches never change it. |
| **Push alerts** | Stored in `push_alerts` for 90 days by event date. The digest shows at most 30 days, defaulting to 24 hours. Expired alerts are removed at startup, hourly, and after refreshes. |
| **Pull research** | Strictly 50 dynamic company slots. A 51st company evicts the least recently searched company, including its saved sections and owned extraction records. Portfolio companies have no reserved Pull slots. |
| **Research history** | Latest sections live in `research_cache`; dated versions in `dated_cache`. Push cleanup does not delete financial history, transcripts, or narrative comparisons. Pull eviction still follows its own policy. |

Raw PDF archives and usage logs are separate from the 50-company limit; it is not a total disk-space limit.

### Refreshing data

- **Push:** Queues a refresh of filings and EOD data daily at **6:30 pm IST**, including weekends. A busy worker may delay execution. Users can also tap **Refresh** anytime. The server must be running; restarting after 6:30 pm catches up that day once, with duplicate prevention stored in SQLite.
- **Pull:** Missing sections load automatically when a company is opened. Existing analysis shows its last analysed date; tap **Update analysis** to run the research again when it is old.
- **While analysis runs:** Saved sections remain usable, and the narrative section updates when processing finishes.


## 4. Coverage and Verification

The figures below describe the pre-warmed demo cache, not a restriction on company coverage. Uncached NSE companies follow the same research pipeline.

The [3 November 2026 coverage audit](docs/coverage.md) records:

- **50/50** saved business profiles, financial snapshots, and trajectory tables.
- **48** saved research reports. Primary transcripts were unavailable in the searched archive for **TRENT** and **ITC**.
- **300** cached localhost requests, all below 50 ms; maximum **30.87 ms**. These are local measurements, not a public/mobile latency guarantee.
- A **51st-company test with CLEAN** confirmed that Pull stayed at 50 companies while all 18 Push holdings remained unchanged.

### Fixed Push portfolio

```text
RELIANCE, TCS, HDFCBANK, INFY, DIXON, CAMS, NTPC, DMART, TRENT,
LT, BHARTIARTL, MARUTI, HAL, ZOMATO, SUNPHARMA, BAJFINANCE,
TATAMOTORS, SIEMENS
```

Membership is defined in [`config/portfolio.json`](config/portfolio.json). The initial 50-company research list is in [`config/pull_universe.json`](config/pull_universe.json); it does not limit what users can search.

Checks cover financial calculations, source evidence, cache isolation, scheduling, and alert retention. Commands to run them are included in the setup section.

## 5. Mobile Reviewer Walkthrough

### Explore the digest

1. Choose **Last 7 days** or **Last 30 days**.
2. Tap a summary count to jump to its section; Routine Filtered also expands its list.
3. Filter by **Company events** or **Market moves**, then verify a source badge.
4. Tap **Deep dive →** on an alert to research the company. The ticker tape has no research links.

### Research a company

1. Search **INFY**, **DMART**, or any supported NSE ticker, or reopen a recent search.
2. Read the snapshots and trajectory, then inspect guidance comparisons and citations.
3. Try another NSE ticker to see missing sections load automatically.
4. For older saved research, check **Last analysed** and tap **Update analysis** to run it again.

Tap the **FINN** logo to return to the default digest and reset its filters.

## 6. Trade-offs and Known Limits

- **EOD, not streaming:** Prices are saved closing data. A recent refresh does not mean live prices or complete filing coverage; source gaps are shown.
- **Available evidence:** Missing transcripts do not prove a company never holds calls. FINN avoids inventing comparisons when evidence is missing.
- **Financial history:** JIOFIN currently has four annual observations; NESTLEIND consolidated has three. Shorter histories and CAGR periods are labeled.
- **Reporting differences:** Consolidated/standalone basis is preserved. Derived EBITDA is a proxy, not separately disclosed EBITDA.
- **Legacy ticker labels:** ZOMATO uses ETERNAL source data; TATAMOTORS uses TMPV source data. Historical periods may span corporate reorganizations.
- **First-time research:** Uncached companies need network access; parsing and extraction take longer than reading saved data.
- **Render storage:** Bundled data restores the cached demo on fresh deployments. New runtime data can reset on the free service's temporary filesystem. Keeping it awake does not make storage persistent.

## 7. Next Milestones

- Add cash-flow reconciliation with sector-specific checks.
- Extract debt maturity schedules and annual-report footnotes.
- Add earnings-call audio transcription when written transcripts are unavailable.

## 8. AI Build History

Development prompts, decisions, and iterations are documented in [the build history](docs/ai_build_history.md). [AI_BUILD_CHAT_HISTORY.md](docs/AI_BUILD_CHAT_HISTORY.md) contains the same export under an alternative filename.

## 9. Local Setup and Deployment

### Prerequisites

Python **3.12**, Git, and optionally Node.js 18+ for frontend checks.

### Install and run

```bash
git clone https://github.com/RamHaneesh/FINN.git
cd FINN
python -m venv .venv
```

Activate the environment for your shell:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

Then install and start FINN:

```bash
pip install -r requirements.txt
python -m scripts.serve --host 0.0.0.0 --port 8000
```

Open [localhost:8000](http://localhost:8000). For a phone on the same Wi-Fi network, open `http://<your-computer-LAN-IP>:8000` if local firewall settings allow it.

### Configure Gemini

Cached research can be browsed without a key. New model extraction requires a Gemini API key and available quota.

Copy `.env.example` to `.env` in the project root and set:

```dotenv
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

Keep `.env` private. FINN reads it automatically at startup; restart the server after changing it. No OpenAI key is required.

### Run checks

```bash
python -m unittest discover -s tests -v
node --test tests/test_analysis_ui.mjs tests/test_company_ui.mjs tests/test_completion_ui.mjs tests/test_digest_ui.mjs
```

### Deploy on Render

Use [`render.yaml`](render.yaml) for the single-service configuration. Set `GEMINI_API_KEY` privately in Render; the server reads Render's `PORT` automatically. Keep one service instance and use `python -m scripts.serve` so the embedded worker and scheduler start together.

See [deployment instructions](docs/DEPLOYMENT.md) for environment variables and storage details. Check [`/api/health`](https://finn-investment-agent-f3ra.onrender.com/api/health) for API and worker status.
