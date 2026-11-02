
# FINN: Financial Investment Agent

**A mobile-first financial research tool for public-market investors**

[**Live Mobile Demo**](https://finn-investment-agent-f3ra.onrender.com/) · No login required

---

## 1. What I Built

Investors have to go through many company announcements to find information that matters. Checking whether management has delivered on past promises also takes time, as the information is spread across earnings call transcripts and financial reports.

FINN helps with both tasks through two main features:

- **Push Digest:** Highlights important company announcements and unusual market movements while keeping routine filings separate.
- **Company Deep Dive:** Lets users research a company, review its financial performance over five years, and compare management's past commitments against actual results.

The main feature is **Narrative vs. Numbers**: comparing what management said it would achieve with what the company actually delivered.

FINN uses company filings, financial statements, and earnings call transcripts as its main sources of information.

## 2. Why I Chose Narrative vs. Numbers

The assessment offered several possible directions, including business snapshots, financial analysis, cash-flow quality, guidance, and bull-versus-bear analysis.

I chose **Narrative vs. Numbers as the main feature**, supported by business snapshots, financial snapshots, five-year trends, and management guidance.

This gave the project one clear purpose: helping investors compare what management said with what the company actually delivered.

The supporting features reuse the same financial data, making them useful without adding unnecessary complexity.

I deliberately deferred:

- **Balance Sheet Analysis:** Debt, leverage, and working capital need additional sector-specific checks and interpretation.
- **Cash-Flow Quality:** Comparing reported profits with cash generation requires another data pipeline and additional validation.
- **Bull vs. Bear Analysis:** Building reliable investment cases requires broader evidence and more interpretation, increasing the risk of unsupported conclusions.

## 3. Architecture and Key Decisions

```text
Mobile Interface
      |
      v
FastAPI Server (Python 3.12)
      |
      ├── SQLite Cache
      |     ├── Company Profiles
      |     ├── Financial Data
      |     └── 5-Year Financial Trends
      |
      └── Research Worker
            ├── Downloads and processes transcripts
            ├── Gemini extracts relevant information
            └── Python checks financial calculations
```

### Key Engineering Decisions

- **AI extracts, code calculates:** Gemini extracts management statements, figures, and dates from transcripts. Python handles financial calculations and compares management's targets with reported results.
- **Evidence before completeness:** When a statement is unclear or cannot be compared with reported financial data, FINN displays it as commentary with a source citation rather than assigning a Met/Missed result.
- **Fast access to common companies:** Financial data for 50 NSE-listed companies is stored in a local SQLite database. Other companies can be researched through on-demand extraction.
- **Separate Push and Pull universes:** Push uses a fixed 18-company portfolio in `config/portfolio.json`, mirrored in SQLite's `push_portfolio` table. The independent `config/pull_universe.json` defines the initial 50-company warm-up list; searching other tickers never changes Push membership.
- **Pull cache retention:** Strictly 50 dynamic company slots, including portfolio tickers when opened in Pull. Every slot is eligible for least-recently searched eviction. Explicit company opens update recency; background polling does not. `research_cache` stores latest sections, `dated_cache` stores ticker/date versions and `company_access` tracks LRU metadata. Eviction removes Pull sections and owned extraction records. The separate `push_portfolio` and protected `push_cache` retain all 18 Push holdings and their price/filing/financial inputs. Raw PDF archives and usage logs are separate from the 50-company limit; this is not a total-disk quota.
- **Research runs separately:** Basic company information and financial trends load first. Transcript analysis runs in the background so it does not hold up the rest of the page.

## 4. Performance and Testing

- **Response time:** The current local coverage/latency audit is recorded in `docs/coverage.md`. These are measured localhost responses, not a public/mobile latency guarantee.
- **Company coverage:** 50 companies have profiles, financial snapshots and trajectory tables in the cache. Annual history is limited to what the source exposes (currently four observations for JIOFIN and three for Nestl� consolidated).
- **Push portfolio:** Exactly 18 fixed companies: RELIANCE, TCS, HDFCBANK, INFY, DIXON, CAMS, NTPC, DMART, TRENT, LT, BHARTIARTL, MARUTI, HAL, ZOMATO, SUNPHARMA, BAJFINANCE, TATAMOTORS and SIEMENS.
- **Transcript reports:** 34 companies have verified transcript reports. TRENT is marked as having no public transcript archive.
- **Tests:** 40 backend unit tests and 3 automated UI checks cover the pipelines, Push/Pull isolation, cache retention and progressive completion.

## 5. Mobile Reviewer Walkthrough

### Push Digest (Company Updates and Market Movements)

**What you see:**

- A feed of important company announcements and unusual market movements, with routine filings kept separate.
- Badges highlighting volume spikes, sharp price movements, management changes, and earnings releases.
- Financial results cards showing Revenue, EBITDA, PBT, and PAT, along with quarter-on-quarter and year-on-year changes.

**What you can do:**

- Filter the feed by Results, Management, or Market Moves, and change the time window.
- Expand the Routine & Lower-Priority Filings section to view announcements that are kept out of the main feed.
- Open Preferences to view or change the thresholds used for market alerts.
- Tap **Deep dive →** on an alert to open the company's research page.

### Company Deep Dive (On-Demand Research)

**What you see:**

- **Business Snapshot:** An overview of the company's business, main segments, and products.
- **Financial Snapshot:** Recent quarterly financial results with growth and margin figures.
- **5-Year Trajectory:** A table showing how revenue, profit, and margins have changed over five years, including growth rates.
- **Narrative vs. Numbers:** When available, compares management's past commitments with reported financial results and shows whether a target was met or missed.
- **Active Guidance & Commentary:** When available, shows future targets and management statements that cannot be directly compared with financial results, along with
source citations.

**What you can do:**

- Search for any NSE-listed company using the search bar or quick-selection chips.
- Open transcript citations to read the original statement, along with the speaker and page reference.
- Tap the FINN logo to reset filters and return to the default digest.

## 6. Key Trade-offs and What I Left Out

- **Mobile-first interface:** I focused on a simple, single-column layout rather than a large desktop dashboard. This keeps the information easy to scan on a phone.
- **Primary sources only:** I left out broker reports, news articles, and sentiment analysis to keep the research focused on company disclosures and reported financials.
- **No forced scorecards:** Qualitative or unclear management statements are shown as commentary rather than assigned an unsupported numerical result.
- **No live intraday streaming:** I focused on end-of-day market movements and company announcements rather than building a live streaming system.
- **Single-service deployment:** The application runs as one FastAPI service on Render. The SQLite database is included with the repository to make the cached data available when the service starts.

## 7. Where I Would Take It Next

- **Cash-flow analysis:** Compare reported profits with operating cash flow to identify companies whose profits are not translating into cash.
- **Live exchange updates:** Add real-time company announcement feeds to make important updates available sooner.
- **Earnings call audio:** Process earnings call audio to identify changes in management's statements before written transcripts become available.

## 8. AI Build History

A sanitized Markdown export of my Codex build session, covering the development process, prompts, and testing, is available [here](docs/ai_build_history.md).

## 9. Local Setup

### Requirements

- Python 3.12
- Git

### Run the application

```bash
git clone https://github.com/RamHaneesh/FINN.git
cd FINN

python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
# .venv\Scripts\activate

pip install -r requirements.txt

python -m scripts.serve --host 0.0.0.0 --port 8000
```

Open http://localhost:8000 in your browser.

For mobile testing, use a browser's device emulation at a width of approximately 390px.

### Run Tests

```bash
# Backend tests
python -m unittest discover -s tests -v

# UI tests (requires Node.js)
node --test tests/test_analysis_ui.mjs tests/test_company_ui.mjs tests/test_completion_ui.mjs
```
