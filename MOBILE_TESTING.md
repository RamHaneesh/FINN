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

## Sources and honest limits

- Portfolio: 18 diverse NSE companies, including RELIANCE, TCS, HDFCBANK, DIXON and TRENT.
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
