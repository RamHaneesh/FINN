# Single-service Render Free deployment

FastAPI serves FINN's mobile interface, API, cached data and one embedded research worker from a single Render web service. No Vercel project or frontend build is required.

Current configuration separates the fixed 18-stock Push portfolio (`push_portfolio` plus protected `push_cache`) from 50 fully dynamic Pull slots (`research_cache`, dated sections and `company_access` LRU metadata). No Pull company is pinned. A 51st search evicts the least-recently searched Pull company without changing Push holdings or snapshots. The initial warm-up list in `config/pull_universe.json` does not resurrect evicted slots on restart. On Render Free, only the bundled data is restored after a host reset; runtime changes are temporary.

## Live service

- Public URL: [FINN](https://finn-investment-agent-f3ra.onrender.com/)
- Health: [API and worker status](https://finn-investment-agent-f3ra.onrender.com/api/health)
- Render service: `finn-investment-agent`, Singapore, Free plan.
- First deployed source: `2e84765`.

Verified on 1 November 2026: the public health endpoint returned HTTP 200 with the worker available; INFY and DMART APIs each returned a business profile, financial snapshot, five trajectory rows and saved research. A 390 × 844 browser check confirmed the 35-company digest, Push-to-Pull deep linking, DMART search, correct section order and no horizontal overflow or browser errors. The deployment used the existing cached evidence; these checks did not perform a new Gemini extraction or establish a phone-network latency guarantee.

## Service settings

The repository's `render.yaml` describes the deployment. The same settings can be entered manually:

| Setting | Value |
|---|---|
| Service type | Web Service |
| Repository | `https://github.com/RamHaneesh/FINN` |
| Branch | `main` |
| Runtime | Python |
| Python version | `3.12.10` |
| Build command | `pip install -r requirements.txt` |
| Start command | `python -m scripts.serve --host 0.0.0.0` |
| Instance plan | **Free** |
| Health check | `/api/health` |
| Instances | One |
| Persistent disk | None |

Environment variables:

```text
PYTHON_VERSION=3.12.10
FINN_DATA_DIR=/tmp/finn
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_API_KEY=<enter privately in Render>
```

The server reads Render's `PORT` automatically. The Gemini key belongs in Render's environment settings; never put it in Git, frontend code or build/start commands. Existing cached research works without a key; new extraction requires it and available provider quota.

## Free-tier behavior

Render Free sleeps after 15 minutes without incoming traffic and may take approximately one minute to wake. Its runtime filesystem is temporary: newly generated analyses, jobs and preference changes can be lost on sleep/restart/redeploy. The bundled database and evidence restore the pre-warmed companies on each fresh startup. The worker runs while the service is active, without a guarantee of uninterrupted background execution.

Render grants 750 free instance-hours per workspace/month, shared across free services. Other bandwidth/build limits apply. The free memory ceiling can constrain large PDF research. Keep the Free plan selected; no paid disk, upgrade or subscription is authorized.

Because the UI and API share one service, Render handles the initial wake before serving the page. A cached localhost benchmark does not guarantee an instant public first load. Before a scheduled demo, open the public URL manually and verify it is ready. Do not use artificial keep-alive requests to bypass provider limits.

Reference: [Render free-tier limits](https://render.com/docs/free).

## Deployment and verification

1. Push the deployment files to the source repository.
2. In Render, create a Web Service using the public repository and settings above, or import `render.yaml` as a Blueprint.
3. Enter the Gemini secret privately, confirm **Free**, and deploy.
4. Wait for the build and service health checks to pass. Use the actual `https://<service-name>.onrender.com` URL returned by Render.
5. Open that URL in an incognito browser and on a smartphone using mobile data. Confirm Push Digest, filters, Preferences and deep links work.
6. Open INFY and DMART; verify business profile, financial snapshot, five-year trajectory and narrative evidence.
7. Check `/api/health` and worker availability. Test one permitted new analysis and confirm progress updates while switching tabs.
8. Confirm bundled company views return after a restart. Runtime additions are temporary under this plan.

The prototype uses shared preferences and public mutation endpoints. Model budgets apply per job rather than as a global abuse limit. Keep provider quotas bounded and restrict quota-consuming routes before broad public promotion. This is an evaluation prototype, without production authentication or multi-user isolation.

A public deployment is complete only when the live service and its company views have passed these checks.
