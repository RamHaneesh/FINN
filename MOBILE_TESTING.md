# FINN mobile demo

## Open the running app

- This computer: [FINN](http://127.0.0.1:8000/).
- Phone on the same Wi-Fi: [FINN on the local network](http://172.23.70.196:8000/).
- API reference: [FastAPI docs](http://127.0.0.1:8000/docs).

The LAN address was verified for this computer on October 31, 2026. It can change after reconnecting to Wi-Fi. If Windows requests firewall access, allow Python on the private network for phone testing. No public deployment has been created.

Restart when needed:

```powershell
.\.venv\Scripts\python -m scripts.serve --host 0.0.0.0 --port 8000
```

This runs the UI, API and one background worker. Do not also start `scripts.worker` against the same database.

## Two-minute walkthrough

1. **Push Digest:** opens by default with a rolling 24-hour filing window and active signals for the latest saved EOD session. Price triggers default to ≥ ±3%; volume must be strictly > 2× the prior 20-session mean, excluding the current session.
2. **Results:** select Last 7 days, then Results. Inspect the Revenue, EBITDA, PBT and PAT rows and green/red QoQ/YoY badges. Open the source attachment or the company's deep dive. Related releases and results attachments are grouped.
3. **Routine filings:** expand the collapsed panel. These documents remain available without occupying the main feed.
4. **Preferences:** change the price/volume thresholds and save. Cached market bars are immediately reevaluated, without a model call.
5. **Pull Deep Dive:** try INFY and DIXON. Both have real cached financial tables and partial transcript analysis. Infosys includes a completed comparison: FY26 constant-currency guidance of 3–3.5% versus a disclosed actual of 3.1%. Dixon retains unclear/incompatible statements as context rather than inventing verdicts. Financial snapshots appear before narrative cards on phones.
6. **Evidence:** open a narrative's transcript reference. Inspect the exact quote and full PDF page context, or follow the original document link.
7. **Generalization:** enter another NSE symbol, with or without `.NS`. A saved snapshot opens immediately; uncached research is a background job with progress. The app stays usable while documents are processed. Missing or incompatible evidence produces an unavailable comparison rather than an invented verdict.
8. **Company suggestions:** type part of a company name or symbol (for example, `infosys`, `dix` or `hdfc`), then tap a suggestion. Keyboard users can use Up/Down and Enter; Escape closes the list. Suggestions filter a locally cached official NSE equity directory, with no model call per keystroke. If the directory is unavailable, saved portfolio companies remain available and exact tickers can still be entered.
9. **Recent searches:** explicit successful searches appear below the search box and in the suggestion menu when the input is empty. The last eight unique companies are stored in this browser; the four most recent are shown as quick buttons. Clear recent removes this browser's history. Automatic default views are not counted as searches.
10. **FINN home:** choose a longer digest window/filter and scroll down, then tap the FINN logo. It restores the default 24-hour/all-signals digest, clears the research input, collapses panels and smoothly scrolls to the top. The header stays accessible while scrolling. Saved alert preferences, recent history and cached research are preserved. Reduced-motion preferences disable the scroll animation.
11. **Background analysis:** choose a company without saved narrative research and start analysis. A progress card shows financials, transcript discovery, document reading, narrative analysis and comparison; document/section counts update during work. Only elapsed time and processing stage are shown, with no remaining-time estimate. Queue position and an unavailable worker are shown explicitly. Buttons are disabled while the request is active, and duplicate requests reuse the existing job.
12. **Guidance review:** open INFY. The previous completed financial year shows only verified Met/Missed comparisons. Future measurable targets appear separately under Active Guidance. Additional statements and unmatched targets are collapsed at the bottom. Open DIXON to check the clean empty state when saved evidence does not establish a verified historical comparison. Update analysis selects prior-year calls, the following results call and a recent call; it preserves validated historical findings across runs. Changed historical targets retain separate verdicts rather than overwriting the original target.
12. **Leave and return:** switch to Push Digest or reload while analysis runs. The background activity button remains available and reopens the current job. No new model request is submitted merely to reconnect. Completion and failure remain visible; a failed job preserves earlier research and offers an explicit retry. Partial source coverage is labeled on completion.

The progress clock and stage state are persisted in SQLite. API health includes `worker_available`. Start the app through `scripts.serve` to include the analysis worker; a standalone API without a worker can accept queued requests but cannot execute them.

## Sources and honest limits

- Portfolio: 35 diverse NSE companies, including RELIANCE, TCS, HDFCBANK, DIXON and TRENT.
- All 17 reference categories are recognized by deterministic metadata rules; categories are triage, not a claim that every event is economically material.
- Narrative quotes come from original transcripts. Financial tables come from standardized Screener data, labeled separately. Annual reports remain linked and are not parsed during interactive page loads.
- Results extraction from original filings runs in the worker. Incomplete primary extraction can use marked standardized values. `†` identifies a standardized fallback in mixed-source cards.
- `EBITDA*` in standardized tables is a derived proxy: PBT + interest + depreciation − other income. It is cross-checked against operating profit and excluded from guidance matching. It is not presented as separately disclosed EBITDA.
- In this verification, Reliance's original filing supplied EBITDA and PBT with deltas; Revenue/PAT use marked standardized values. NTPC primary extraction did not establish supported quarter values, so its card retains the labeled standardized table.
- Current transcript analysis has partial coverage. Some targets remain pending or cannot be compared due to period/scope/basis uncertainty. Aspirations and explicit refusals to give guidance do not receive met/missed verdicts.
- No seeded alerts or fabricated financial figures are presented as live data.

## Caching and speed

Page/API requests read saved SQLite records. PDF parsing and Gemini calls are isolated in worker jobs. Discovery, raw PDFs, parsed pages and structured extraction have separate local caches.

Mobile company responses omit the full internal fact inventory and annual table; the interface receives its four-quarter snapshot, comparisons and source references. HTTP compression reduces transfer size. Full records remain available through the research/evidence API.

The initial local benchmark recorded median responses of approximately 2 ms for HTML, 56 ms for the digest, and 6–7 ms for INFY/DIXON company views, all below 300 ms. This is a localhost measurement; Wi-Fi and actual phone rendering add latency. The verification also used a 390 × 844 browser viewport with no horizontal overflow.

Refresh real cached data before a future demo:

```powershell
.\.venv\Scripts\python -m scripts.prepare_demo --research INFY DIXON --max-calls 6
```

The refresh button performs portfolio updates in the background. Model extraction uses `gemini-3.5-flash-lite` with per-run call caps; there is no paid-model fallback.

UI density check: at 390px width, Push uses a single summary ribbon and shows the first alert without scrolling. Results show values and deltas without exchange boilerplate; volume cards show traded volume and prior-20-session baseline. Deep dive from HDFCBANK, NTPC and CAMS must select that company. SEDEMAC shows the snapshot first, then sourced Management Commentary instead of an empty comparison card. Commentary has no Met/Missed verdict.

Pull context sections: Business snapshot → Financial snapshot → Trajectory → Narrative vs. Numbers. Business snapshots now copy the public Screener company profile directly (About plus explicitly dated revenue-segment headings and product/brand sections). There are no model calls, transcript discovery or PDF parsing on this path. `business-profile-v2` replaces and ignores old transcript-based `business-v1` summaries. Financial-source HTML also populates the profile cache. Profile refresh runs in a separate short background task, independent of the narrative worker. Existing portfolio/search profiles are prewarmed for instant views. A first unseen ticker needs a profile-only HTML fetch; unsupported public brands/mix are omitted and login-only details are not accessed. Source outages show a quiet profile link, never an invented description or a red analysis error.

The 5-year trajectory is a compact table: financial year, revenue (₹ cr), revenue YoY (%), EBITDA margin (%) and PAT (₹ cr). Five completed annual years are visible without large charts. Python computes growth and margins; the bottom ribbon shows revenue/PAT CAGR. True five-year CAGR uses the preceding sixth annual observation; shorter history is labeled with its actual duration. The first displayed YoY also uses the preceding saved year. Loss/non-positive endpoints have no CAGR. Derived EBITDA margin is marked *. The versioned `trajectory-v1` response is reused until annual values or reporting basis change. Source and calculation method remain expandable. Mobile section order is Business snapshot → Financial snapshot → 5-year trajectory → Narrative vs. Numbers. DMART and INFY live API/render tests confirm five rows, both CAGR labels and cache-only repeats. This remains standardized-table evidence, separately labeled from primary-source management quotes.

Automatic completion: opening any company (search, recent or Push deep link) calls the missing-section planner only if required. `/api/company/{ticker}/complete` fills absent business/financial/annual context independently of the narrative queue; a missing narrative report queues the normal capped research job. Cached context and completed research with zero statements are reused. Missing annual tables are fetched before trajectory is recomputed; undisclosed metrics are not fabricated. Active jobs are deduplicated. Failed automatic context attempts and failed narrative jobs have a 30-minute cooldown; explicit profile refresh/analysis retry remain available. Completed partial narrative coverage does not trigger an automatic extraction loop. Client polling only redraws changed context and does not overwrite another selected company.

Progressive loading and retention: each explicit company opening marks its server-side last-opened time (`?opened=true`); polling does not change recency. Context fields fill independently, with temporary financial/trajectory placeholders while context is pending. The narrative processing card is mounted inside Narrative vs. Numbers, shows “Extracting guidance from primary transcripts…” with a measured elapsed timer, and is replaced with saved results after completion. The same processing element survives company switches and home reset.

SQLite keeps latest-value aliases for fast reads plus `dated_cache` records keyed by namespace, ticker and Indian-calendar date. Portfolio tickers from `config/portfolio.json` are pinned and their dated section versions do not expire. At most 50 ad-hoc companies retain Deep Dive results, ordered by explicit last opening; eviction removes dated/latest sections and associated extraction/document cache records. A late background result cannot resurrect an evicted company. Immutable downloaded PDF blobs and provider-usage audit records remain a separate source/audit archive. An explicitly revisited evicted ticker is eligible for fetching again. `Store.get_dated(namespace,ticker,YYYY-MM-DD)` reads a saved dated version. Same-day saves replace that day's record; different dates remain separately addressable.

The final coverage universe contains exactly 35 configured labels. Run `scripts.audit_universe` for a 35-company live HTTP audit; it checks saved profiles/financials/five annual rows and reports every measured response, including first-request and maximum latency. It does not hide outliers or make a phone/Wi-Fi SLA. The assembled company view is cached and invalidated when its underlying source sections change.
