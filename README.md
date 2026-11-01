# FINN: Financial Investment Agent

**Mobile-First Investment Intelligence Layer for Public-Market Investors**

[**Live Mobile Demo**](https://finn-investment-agent-f3ra.onrender.com/) · **No Login Required** · **Recommended Test Tickers: INFY, DIXON, CAMS**

---

## 1. Executive Summary

Public-market investors are overwhelmed by hundreds of daily exchange filings (~75% of which are routine compliance paperwork). Meanwhile, holding corporate management accountable to past guidance requires manually tracking historical commitments across conference call transcripts and reconciling them against subsequent quarterly filings.

**FINN** automates this workflow across two interaction modes:
* **Push (Proactive Triage):** Categorizes filings using a 17-class taxonomy, surfacing high-materiality events (earnings, management changes, M&A) while suppressing routine paperwork, paired with end-of-day anomaly triggers (>2× 20-day volume spikes, ≥±3% price moves).
* **Pull (Narrative vs. Numbers):** On-demand deep dive comparing management's historical commitments (extracted from primary concall transcripts) against trailing financial delivery (standardized P&L tables).

**Primary Source Discipline:** Strictly grounded in official exchange filings, primary concall transcripts, and standardized financial tables. No broker notes, no secondary news, and zero ungrounded generative hallucinations.

---

## 2. Architecture & Key Engineering Decisions

```text
Mobile Client (390px Viewport)
       │
       ▼
  FastAPI Server (Python 3.12 / Uvicorn)
       │
       ├─► [Fast Path: <25ms] ──► SQLite Cache (35-Ticker Pre-Warmed Universe)
       │                          ├─ Business Profiles & Segment Mix
       │                          ├─ Standardized Financial Snapshots
       │                          └─ 5-Year Growth & Margin Trajectory
       │
       └─► [Deep Path: Async] ──► Embedded Research Worker
                                  ├─ Primary Concall PDF Downloader & Slicer
                                  ├─ Gemini Extraction (Strict JSON Schema)
                                  └─ Metric Verification Engine (Met / Missed)
```

### Architectural Principles

* **Code Calculates, Models Extract:** Gemini extracts structured quotes, metrics, and target dates from primary transcripts. All arithmetic, YoY/QoQ deltas, 5-year CAGRs, and guidance verdicts are computed deterministically in Python.
* **Truth over Forced Completeness:** Only compatible historical targets and reported actuals receive a strict Met/Missed scorecard. Ambiguous, qualitative, or mismatched statements are preserved as contextual commentary with verified citations, while future targets remain cleanly separated under Active Guidance rather than manufacturing a speculative LLM verdict.
* **Progressive Hydration:** Fast data (profiles, financials, and 5-year trajectories) loads in under 25ms. Heavy transcript analysis runs asynchronously in an embedded worker without blocking the user interface.
* **Pre-Warmed Coverage Universe:** 35 actively traded NSE companies are pre-seeded in SQLite to ensure instant mobile evaluation. Uncached tickers automatically fall back to live on-demand extraction.

---

## 3. Verified Performance Benchmarks

* **Response Latency:** **< 25 ms** across all 35 companies (measured across 210 warm API requests; median: ~7 ms).
* **Pre-Warmed Scope:**
  * **35/35 companies** with complete Business Profiles, Financial Snapshots, and 5-Year Trajectories.
  * **34/34 companies** with verified Concall Narrative Reports (`TRENT` explicitly marked as having no public transcript archive).
* **Test Suite:** **39 backend unit tests** and **3 automated UI checks** passing across quote verification, margin validation, cache eviction, and recovery rules.

---

## 4. Mobile Reviewer Guide (5-Step Walkthrough)

### Step 1: Push Digest (Signal Triage)
* Open the **Push Digest** feed.
* Inspect the **CAMS** card: flags a **6.27× volume anomaly** (7.08M shares vs. 1.13M 20-day baseline).
* Filter to **Results** to view **NTPC**: displays Revenue (₹54,270 Cr), EBITDA, PBT, and PAT with QoQ and YoY delta badges.
* Tap **Routine Filings** at the bottom to verify low-signal compliance paperwork is collapsed.

### Step 2: Push-to-Pull Deep Linking
* Tap the **`Deep dive →`** button on any push card (e.g., CAMS or NTPC).
* The app smoothly switches to the **Pull** tab and immediately loads that company's research.

### Step 3: Narrative vs. Numbers (The Core Demo)
* In the search bar, tap the **`[INFY]`** chip:
  * Review the clean section sequence: **Business Snapshot → Financial Snapshot → 5-Year Trajectory**.
  * Inspect the **Narrative vs. Numbers** card: FY2026 constant-currency revenue guidance of **3.0%–3.5%** verified against actual delivery of **3.1%**, marked **Met** with inline transcript citations (Pages 21 and 4).

### Step 4: Handling Ambiguity (Truth over Hallucination)
* Tap **`[DIXON]`**, **`[DMART]`**, or **`[SEDEMAC]`**:
  * Inspect the **5-Year Trajectory** table showing compounding revenue and margin trends.
  * Notice how qualitative statements (e.g., raw material cost pressure on EBITDA) are displayed as contextual commentary with transcript citations instead of manufacturing a fake numerical verdict.

### Step 5: Mobile Interaction Polish
* Tap the top **FINN** logo at any time: resets active filters, returns to the default digest, and scrolls to top.
* Tap **Preferences** beside the Refresh button to inspect configurable anomaly thresholds (volume multiplier and price move %).

---

## 5. Deliberate Trade-Offs (What Was Left Out & Why)

* **No Desktop Dashboard Bloat:** Engineered strictly mobile-first (390px viewport). A fund manager needs actionable alerts while moving; desktop multi-pane widgets were avoided to maximize signal density.
* **No Secondary News or Broker Notes:** Secondary commentary introduces bias and noise. Restricting the engine to primary filings guarantees auditability.
* **No Speculative Scorecards:** When management statements are qualitative or mismatched, FINN displays them as contextual commentary with primary citations rather than fabricating fake numerical verdicts.
* **Single-Service Deployment:** Packaged as a consolidated FastAPI service on Render Free. The pre-warmed SQLite database is bundled in Git so all 35 companies load with zero cold-start database delay.

---

## 6. Local Setup & Reproduction

```bash
# 1. Clone repository and create virtual environment (Python 3.12)
git clone https://github.com/RamHaneesh/FINN.git
cd FINN
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch server
python -m scripts.serve --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser (or use mobile device emulation at 390px width).

### Running Tests
```bash
# Run 39 offline backend tests
python -m unittest discover -s tests -v

# Run frontend integration checks (Node.js)
node --test tests/test_analysis_ui.mjs tests/test_company_ui.mjs tests/test_completion_ui.mjs
```