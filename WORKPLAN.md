# FINN: Final Workplan

## Product purpose

FINN is a mobile-first investment intelligence prototype for the ENAM Holdings AI Engineer Build Challenge.

Its central question is: **What changed, and did management deliver?**

Build a focused, working product around management narrative versus actual performance. Add a compact financial snapshot and trajectory as supporting context. Push should surface only developments that deserve attention.

Assessment deadline stated in the brief: **Sunday, November 1, 2026**.

## Implementation checkpoint: October 31, 2026

- Initial backend modules and CLI entry points are implemented; see `README.md` for commands and current boundaries.
- SQLite storage, document discovery/download/parsing, bounded Gemini extraction, evidence validation, conservative comparisons, initial alert rules, persistent research jobs and a development API are connected.
- Eighteen offline checks pass, including API-to-worker execution. Live Infosys transcript extraction and EOD/filing refresh were verified; repeated extraction used zero model calls.
- This is an initial backend slice. Four-quarter analysis coverage, fully reviewed financial extraction, deeper filing materiality, scheduling, mobile frontend and deployment remain outstanding.

## 1. Agreed scope

### Pull: narrative versus numbers

The investor searches for an NSE company and sees management statements from the last four quarters alongside subsequent performance.

- Start with revenue growth and EBITDA margin where those measures are applicable and consistently disclosed.
- Extract explicit guidance, directional expectations and aspirations under one narrative model.
- Compare explicit guidance numerically; evaluate directional expectations only when the metric and period are clear.
- Keep unmeasurable aspirations as context without a met/missed verdict.
- Preserve original guidance and later revisions as separate, dated statements.
- Show Met, Missed, Pending or Cannot compare, with a short explanation and both sources.
- Add a four-quarter financial view using the same validated records. Missing metrics remain unavailable.
- Use annual reports for business, accounting and reporting context; transcripts for management narrative; primary results disclosures for actual performance.

### Push: a selective attention feed

- Monitor a mock portfolio of 15-20 NSE/BSE companies across sectors and sizes.
- Offer a digest with a default 24-hour window and selectable periods.
- Surface material events, supported narrative/result divergences and configurable EOD price/volume anomalies.
- Let users configure watched announcement categories and anomaly thresholds.
- Explain why each card appeared and show its source and data timestamp.
- Keep routine filings outside the main feed, accessible through a separate filing archive.
- Show an empty state when nothing earns attention; do not manufacture daily content.
- Deliver prototype alerts in the app through scheduled polling. Native notifications and real-time exchange delivery are deferred.

Prepare 3-5 ad-hoc research examples using the general pipeline. Start deep validation with two companies, then expand. An unfamiliar NSE ticker must use the same discovery and processing path, with honest processing and unavailable-data states.

## 2. Recommended technology stack

| Layer | Choice | Reason |
|---|---|---|
| Frontend | React + TypeScript + Vite | Flexible phone-first interface and a static production build |
| Styling | Tailwind CSS | Fast implementation of consistent responsive layouts |
| Backend | Python + FastAPI | Shared Python environment for ingestion, document processing and analysis |
| Validation | Pydantic schemas | Explicit contracts for model output, facts and API responses |
| Persistence | SQLite initially | Simple server-local storage for facts, jobs, preferences and cached analysis |
| Document storage | Files on persistent server storage | Retain raw PDFs, parsed text and document hashes |
| Document parsing | pypdf first; evaluate a table parser/OCR only for documents that need it | Keep the initial dependency set small; validate extraction against source pages |
| Data fetching | HTTP client with source-specific adapters; EOD provider such as yfinance if validated | Isolate source changes and failures |
| Models | Gemini API only; start with `gemini-3.5-flash-lite` | Check actual account access, quota and schema support; consider `gemini-3.8-flash` later, with no automatic fallback |
| Background processing | One Python worker with a persistent SQLite jobs table | Keep research work outside request lifetimes without adding a broker initially |
| Scheduling | A single scheduled refresh entry point | Reuse the same pipeline for manual refreshes and polling |
| Packaging | One repository and one container image | Reduce deployment coordination; serve built frontend and API from one origin |

Alternatives considered:

- Next.js plus a Python worker: suitable, but adds another server framework without a strong need for server-rendered pages here.
- Django plus templates/HTMX: suitable for a Python-heavy build, but React provides more direct control over the intended interactive mobile views.

No distributed microservices, Redis, vector database or agent orchestration framework in the initial scope. Introduce infrastructure only when a measured limitation requires it.

## 3. Data-source rules

| Data | Allowed source path | Usage |
|---|---|---|
| EOD prices and volume | Public market-data provider such as Yahoo Finance | Portfolio anomalies and market context |
| Announcements | NSE/BSE disclosures | Push events and original filing links |
| Annual reports | Links discovered through Screener or company IR | Primary-source research and reporting context |
| Earnings-call transcripts | Links discovered through Screener or company IR | Management narrative and guidance |
| Actual quarterly results | Original company/exchange results disclosures | Numerical comparison evidence |

Screener is a discovery route; primary company documents are the research evidence. Do not ground pull analysis in news, broker notes, research reports or the model's outside company knowledge. Push-side professional-background enrichment is permitted by the brief but deferred.

Retain source URL, company identity, document type, publication date, covered period, fetch timestamp and content hash. Preserve page references and exact supporting text wherever available.

## 4. Modular pipeline

```text
Scheduled refresh / ticker search
                |
        Resolve company identity
                |
    Discover allowed source documents
                |
      Fetch, hash and cache raw data
                |
       Parse text and financial tables
                |
   Extract narrative, facts and filing events
                |
     Validate periods, units and evidence
                |
          Shared evidence store
            /             \
 Narrative comparison   Materiality and anomaly rules
            \             /
        Persist analysis and attention cards
                |
          API and mobile interface
```

| Module | Responsibility | Main output |
|---|---|---|
| `sources/` | Company resolution; separate exchange, market-data and IR/Screener discovery adapters | Company and document listings |
| `documents/` | Download, hashing, duplicate detection, parsing and page mapping | Versioned document text/tables |
| `extraction/` | Structured extraction of narrative, facts and announcements | Validated candidate records |
| `analysis/` | Match statements to actuals and calculate assessments | Cited comparisons |
| `signals/` | Apply materiality, user category preferences and market thresholds | Attention items with reasons |
| `models/` | Provider adapters, routing, response validation, usage and budgets | Consistent model interface |
| `storage/` | Database access, file storage and cache keys | Persisted records and artifacts |
| `jobs/` | Job claims, progress, retries, scheduling and restart recovery | Observable job lifecycle |
| `api/` | Search, research jobs, company views, evidence, feed and settings | Frontend responses |
| `web/` | Attention, company research and evidence views | Responsive phone experience |

Keep these as modules in one backend, rather than separately deployed services.

## 5. Shared records and comparison safeguards

Core records: Company, Document, Evidence, NarrativeStatement, FinancialFact, Comparison, Announcement, PriceBar, AttentionItem, Job and UserPreference.

Every narrative/fact should include:

- Company and source document identity.
- Source page and supporting quote/table text.
- Metric, value or range, unit and currency where applicable.
- Statement date and target/reporting period.
- Standalone/consolidated basis and segment/company scope.
- Narrative type, extraction version and validation status.

Comparison rules:

1. Match company, metric, scope, reporting basis and target period before calculating.
2. Normalize units explicitly; preserve the original values.
3. Distinguish annual, quarterly, YoY and QoQ measures.
4. Do not treat absent EBITDA as zero or silently substitute another profit measure.
5. Do not infer an annual verdict from one quarter without an explicitly supported method.
6. Explain whether a result met a range, exceeded it or fell below it. Store the factual relationship separately from any positive/negative interpretation.
7. Distinguish management revisions from the original expectation.
8. Return Cannot compare when evidence is incompatible or missing.
9. Calculate numerical differences in code; the model explains validated evidence.

## 6. Importance versus noise

Use rules and extracted event details together. Category alone is insufficient: a results filing differs from an advertisement announcing publication; a downgrade differs from a rating reaffirmation.

An item earns feed placement when it has supported implications for earnings, financial risk, management or capital allocation, contradicts a tracked expectation, or crosses a user-selected threshold.

- Deduplicate related disclosures into one event while retaining all source documents.
- Use the fast model to extract event details and supporting evidence.
- Apply explicit eligibility rules before generating a card.
- Preserve potentially material but uncertain items for review; do not silently label them routine.
- Examine rejected filings during development to check for missed important events.
- Do not interpret missing data as no material change. Surface source failures separately.

## 7. Model routing and caching

### Model policy

- Initial provider/model: Gemini API with `gemini-3.5-flash-lite`. No OpenAI API key is required or used.
- `gemini-3.8-flash` is a deferred option, to be evaluated against quality, available quota and cost before enabling it.
- Fast model: document classification, narrative/fact extraction and concise source-grounded explanations.
- Optional reasoning model: genuinely ambiguous synthesis that cannot be resolved by deterministic checks, only if access and budget allow.
- Code: numerical calculations, period matching constraints, thresholds and cache decisions.
- A reasoning model is not required for the prototype to complete its main workflow.
- Validate actual API access and quotas early. Do not assume a consumer subscription provides API credits.
- Keep provider keys on the backend. Log model, latency, token usage and cache hits without logging secrets.

### Cache layers

1. Raw documents and source responses.
2. Parsed text/tables keyed by content hash and parser version.
3. Extracted records keyed by document hash, schema/prompt version and model configuration.
4. Analysis keyed by relevant record versions and analysis rules.
5. Renderable cards keyed by analysis version and applicable user settings.

Unchanged repeated requests should reuse saved results without another model call. New documents, changed questions or analysis versions may require work. Refresh source listings independently so cached research does not hide new disclosures. Recompute only affected downstream records.

Precompute demo companies. For new tickers, return a job ID and show discovery, parsing, extraction and comparison progress. Deduplicate simultaneous requests for the same analysis.

## 8. Deployment and mobile experience

- Serve a responsive web app over HTTPS; no installation required.
- Main navigation: Attention, Company Research and Evidence; keep settings lightweight.
- Put the conclusion and essential numbers first; allow expansion into exact evidence.
- Display data freshness, analysis status and partial-data limitations.
- Test phone-width layouts, touch interactions, slow connections and source links on an actual smartphone.
- Store cache/database on durable server storage. Files on an ephemeral hosting filesystem will not survive restarts.
- Deployment gate: confirm an affordable persistent volume. If unavailable, replace the storage adapter with managed database/object storage while retaining the pipeline contracts.
- Run the API and a single worker from the same image, either under a process supervisor or as separate processes sharing the same local persistent volume. Confirm hosting support before committing to this arrangement.
- Persist job state, checkpoint completed stages and recover interrupted jobs on restart. Use bounded retries and backoff for provider/source failures.

## 9. Execution milestones and acceptance checks

### M1: Validate the hardest assumptions

- Check allowed source access, model API access and persistent deployment options.
- Select two non-financial companies with accessible documents and measurable narrative.
- Manually verify several statement/result pairs across four quarters.

Pass: enough primary evidence exists to demonstrate a useful, defensible comparison. If not, change the initial companies or narrow the metrics before building more UI.

### M2: Complete one end-to-end research workflow

- Implement discovery, storage, parsing, extraction, comparison and API output for one company.
- Show citations and unsupported-comparison states.
- Add the mobile comparison card and compact financial view.

Pass: a user can inspect a comparison and independently verify both source passages on a phone.

### M3: Generalize and cache

- Expand to the second validated company and 3-5 research examples.
- Exercise an unfamiliar ticker through the same pipeline.
- Add progress, request deduplication, cache invalidation and recovery.

Pass: an identical repeated request makes no model call; changed documents invalidate the affected analysis; an unsupported ticker/document fails clearly.

### M4: Connect selective push

- Configure 15-20 portfolio companies and fetch EOD prices/volume plus exchange filings.
- Implement selectable-window digest, category preferences and market thresholds.
- Add supported narrative divergence signals where research is available.
- Preserve all filings in the archive while keeping routine content out of the attention feed.

Pass: seeded fixtures verify trigger logic; real fetched data verifies ingestion. Any demonstration fixtures are explicitly labeled and never presented as live events.

### M5: Deploy and submit

- Verify fresh deployment, persistent cache, restart behavior and smartphone use.
- Check numerical correctness, source fidelity and empty/error states.
- Document setup, architecture, data limitations and tradeoffs in the repository.
- Preserve AI build history and prepare the short covering note.

Submit: working mobile-accessible link, GitHub repository, AI build history and covering writeup to `assessment@enam.com`, with subject `ENAM - IIT screening - 2027`, as specified in the brief.

## 10. Assessment coverage and deliberate omissions

| Assessment expectation | Planned coverage |
|---|---|
| Mobile-first working prototype | Deployed phone-tested responsive web interface |
| Portfolio and research coverage | 15-20 monitored companies; 3-5 prepared research examples |
| Generalization | Dynamic NSE company resolution and source discovery |
| Three guided data sources | EOD market data, exchange announcements and primary fundamentals |
| Push | Windowed digest, configurable thresholds/categories and in-app alerts |
| Pull | Four-quarter narrative versus actuals, source-grounded |
| Product judgment | Sparse attention feed, evidence-first comparisons and honest uncertainty |
| Model efficiency | Fast models, deterministic calculations, selective escalation and versioned caching |
| Submission package | Prototype, repository, build history and covering note |

Deferred: full coverage of all eight research outputs, voice/chat assistant, native push, real-time prices, elaborate management biographies, OCR for every possible scan, distributed workers and automatic investment recommendations. These do not block the chosen workflow.

## 11. Suggested improvements, in priority order

1. **Build a small verified evaluation set early.** Include clear guidance, vague aspiration, revised guidance, incompatible periods and missing data. Measure extraction and verdict correctness against manually checked evidence.
2. **Use a promise timeline.** Preserve what management said, when it changed and what period it concerned. This makes revisions visible without implying deception.
3. **Make evidence a product feature.** Show the statement and actual side by side, with dates and direct document references.
4. **Separate data gaps from investment signals.** A failed fetch is a coverage problem; it should never become reassurance or a negative company verdict.
5. **Measure first-time latency and cost.** Record stage timings and cache hits before choosing optimization work. Do not promise instant uncached research.
6. **Keep source adapters replaceable.** Exchange and IR fetching can be fragile; isolate these dependencies and support a second allowed discovery route.

## References

Challenge documents in this workspace:

- `Problem_Statement/1. ENAM_AI_Engineer_Build_Challenge_Main.pdf`
- `Problem_Statement/2. ENAM_AI_Engineer_Build_Challenge_Reference.pdf`

Technical documentation checked while comparing stacks:

- [Vite deployment](https://vite.dev/guide/static-deploy)
- [Next.js deployment](https://nextjs.org/docs/app/getting-started/deploying)
- [FastAPI background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/)
- [Appropriate uses for SQLite](https://www.sqlite.org/whentouse.html)
- [Render free-service storage limitations](https://render.com/docs/free)
