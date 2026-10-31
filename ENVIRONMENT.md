# FINN environment

Use CPython 3.12 and the project-local `.venv`. Global Python packages are not part of FINN's runtime.

## Run checks

Run from the workspace root; activation is optional:

```powershell
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python scripts/check_environment.py
.\.venv\Scripts\python scripts/check_environment.py --live
```

Optional activation: `.\.venv\Scripts\Activate.ps1`. If activation is blocked, use the explicit interpreter commands above.

## Model choice

- Provider: **Gemini API only**. No OpenAI API key is required or used.
- Initial model: **`gemini-3.5-flash-lite`**.
- Future candidate: **`gemini-3.8-flash`**, deferred until we evaluate quality, account access and quota/cost. No automatic fallback is enabled.
- [Official model documentation](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite) confirms the initial model identifier and structured-output support.

Use available free-tier quota for the prototype. Verify actual eligibility and limits in AI Studio; do not assume every account has free access. Exhausting quota must not automatically enable paid usage.

## Model authentication and generation setup

### 1. Obtain a Gemini API key

Create a key in [Google AI Studio](https://aistudio.google.com/app/apikey), following the [official key instructions](https://ai.google.dev/gemini-api/docs/api-key). Check project API permissions and quota.

### 2. Configure the root `.env`

The file already exists. Edit it locally:

```dotenv
GEMINI_API_KEY=your_actual_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
```

Replace the placeholder with your actual key. Never paste credentials into chat or frontend code. `.env` is Git-ignored; `.env.example` is a shareable template and is not loaded by the script.

Only if `.env` is missing, create it without overwriting credentials:

```powershell
if (-not (Test-Path -LiteralPath '.env')) {
    Copy-Item -LiteralPath '.env.example' -Destination '.env'
}
```

Process environment variables take precedence over `.env`. The script accepts `GOOGLE_API_KEY` as an alternative when `GEMINI_API_KEY` is absent. Prefer `GEMINI_API_KEY` for consistent configuration.

### 3. Verify authentication

```powershell
.\.venv\Scripts\python scripts/check_environment.py --live
```

Expected: `[PASS] Gemini` with authentication/model-list success. This verifies listing access, not generation quota. `[SKIP] Gemini` means no key was loaded.

### 4. Verify generation

```powershell
.\.venv\Scripts\python scripts/check_environment.py --live --generate
```

This sends one small Gemini request and consumes API quota; charges depend on project/model billing. Expected: `[PASS] Gemini: Generation returned text`.

Only after this passes are authentication and basic generation verified. Financial extraction, structured-output correctness and sustained throughput still need testing during implementation. Missing quota must produce a clear failure, not a paid-model fallback.

### Troubleshooting

| Result | Next action |
|---|---|
| SKIP: no key | Add `GEMINI_API_KEY` to the root `.env` |
| WARN: model not set | Set `GEMINI_MODEL=gemini-3.5-flash-lite` |
| HTTP 400 | Check model/request compatibility and API configuration |
| HTTP 401 | Verify the key is valid and correctly copied |
| HTTP 403 | Check project permissions, API enablement, key restrictions and regional availability |
| HTTP 404 | Verify the exact model identifier and account access |
| HTTP 429 | Check rate limits/free-tier quota; wait or reduce requests; do not automatically enable billing |
| Timeout / connection error | Check network access and retry outside the restricted sandbox |
| HTTP 200 but no text | Check output limits/model behavior; generation is not fully verified |

Keys and API response bodies are omitted from diagnostics. Use AI Studio for account-specific failures. The latest non-secret report is saved to `tmp/environment-check.json`.

## Diagnostic coverage and verification status

- Local checks validate isolation, exact requirement pins, `pip check` and core imports.
- After the global package rollback, `.venv` remained healthy with global/user site-packages disabled.
- Gemini-only requirements contain 49 pins. The OpenAI SDK and its exclusive dependencies (`httpx2`, `httpcore2`, `jiter`, `truststore`) were removed from both the requirements file and `.venv`.
- Network-enabled checks on October 31, 2026 fetched 21 RELIANCE.NS daily bars (latest October 30) and 18 NSE announcement records.
- Screener and Infosys annual-report discovery pages were accessible. Page access is not complete document ingestion; discovery and parsing remain implementation work.
- yfinance emitted a non-fatal pandas deprecation warning; EOD retrieval succeeded.
- Gemini authentication/model listing and a small `gemini-3.5-flash-lite` generation request passed on October 31, 2026. Credentials were not displayed. This verifies basic access, not sustained throughput or future free-tier quota.
- Sandbox DNS failures do not establish source unavailability. Recheck sources from the eventual deployment host.

## Official references

- [Gemini API keys](https://ai.google.dev/gemini-api/docs/api-key)
- [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite)
- [Gemini model listing](https://ai.google.dev/api/models)
