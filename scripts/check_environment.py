"""Repeatable FINN diagnostics. Never logs credentials or API response bodies."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import importlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def record(name, status, detail):
    return {"check": name, "status": status, "detail": detail}


def local_checks():
    rows = [record("isolation", "PASS" if sys.prefix != sys.base_prefix else "FAIL", sys.executable)]
    for line in (ROOT / "requirements.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, expected = line.split("==")
        try:
            actual = version(name)
            if actual != expected:
                rows.append(record(name, "FAIL", f"Expected {expected}; installed {actual}"))
        except PackageNotFoundError:
            rows.append(record(name, "FAIL", "Package missing"))
    result = subprocess.run([sys.executable, "-m", "pip", "check"], capture_output=True, text=True, timeout=30)
    rows.append(record("pip check", "PASS" if result.returncode == 0 else "FAIL", result.stdout.strip()))
    for name in ["fastapi", "uvicorn", "pydantic_settings", "httpx", "pypdf", "bs4", "yfinance", "pandas", "numpy", "google.genai", "sqlite3"]:
        try:
            importlib.import_module(name)
        except Exception as exc:
            rows.append(record(f"import {name}", "FAIL", type(exc).__name__))
    return rows


def webpage(name, url):
    import httpx
    try:
        with httpx.Client(timeout=25, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FINN source-access-check)"})
        if response.status_code != 200:
            return record(name, "FAIL", f"HTTP {response.status_code}")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ", strip=True).lower()
        blocked = any(marker in text for marker in ["verify you are human", "access denied", "just a moment...", "captcha"])
        return record(name, "FAIL" if blocked else "PASS", "Access challenge detected" if blocked else "HTML retrieved; document discovery/parsing still needs implementation")
    except Exception as exc:
        return record(name, "FAIL", type(exc).__name__)


def prices():
    import yfinance as yf
    try:
        bars = yf.Ticker("RELIANCE.NS").history(period="1mo", auto_adjust=False, timeout=20)
        if bars.empty or not {"Close", "Volume"}.issubset(bars.columns):
            return record("Yahoo EOD", "FAIL", "No usable Close/Volume bars returned")
        return record("Yahoo EOD", "PASS", f"RELIANCE.NS: {len(bars)} daily bars; latest {bars.index[-1].date()}")
    except Exception as exc:
        return record("Yahoo EOD", "FAIL", type(exc).__name__)


def announcements():
    import httpx
    from zoneinfo import ZoneInfo
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    try:
        with httpx.Client(timeout=25, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.nseindia.com/"}) as client:
            client.get("https://www.nseindia.com/")
            response = client.get("https://www.nseindia.com/api/corporate-announcements", params={"index": "equities", "symbol": "RELIANCE", "from_date": (today - timedelta(days=30)).strftime("%d-%m-%Y"), "to_date": today.strftime("%d-%m-%Y")})
        if response.status_code != 200:
            return record("NSE announcements", "FAIL", f"HTTP {response.status_code}; source adapter needs an allowed alternative if unavailable on deployment host")
        data = response.json()
        if not isinstance(data, list):
            return record("NSE announcements", "FAIL", "Unexpected response structure")
        if not data:
            return record("NSE announcements", "WARN", "Valid empty list; filing extraction not verified")
        valid = all(isinstance(item, dict) and "symbol" in item for item in data)
        return record("NSE announcements", "PASS" if valid else "FAIL", f"Received {len(data)} records; schema {'recognized' if valid else 'unrecognized'}")
    except Exception as exc:
        return record("NSE announcements", "FAIL", type(exc).__name__)


def model_check(generate=False):
    import httpx
    provider = "Gemini"
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return record(provider, "SKIP", "No API key configured in environment or .env")
    try:
        with httpx.Client(timeout=30) as client:
            headers = {"x-goog-api-key": key}
            response = client.get("https://generativelanguage.googleapis.com/v1beta/models", headers=headers)
            if response.status_code != 200:
                return record(provider, "FAIL", f"Model-list HTTP {response.status_code}; check key, permissions, quota or network. Response body omitted.")
            payload = response.json()
            entries = payload.get("models", [])
            names = [entry.get("name") for entry in entries]
            if not generate:
                return record(provider, "PASS", f"Authentication/model listing passed ({len(names)} models on returned page). Generation/quota NOT verified.")
            model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
            if not model:
                return record(provider, "WARN", "Authentication passed; set provider MODEL in .env for generation check")
            model = model.removeprefix("models/")
            response = client.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers=headers, json={"contents": [{"parts": [{"text": "Reply with OK only."}]}], "generationConfig": {"maxOutputTokens": 64}})
            if response.status_code != 200:
                return record(provider, "FAIL", f"Generation HTTP {response.status_code}; response body omitted")
            data = response.json()
            text = " ".join(part.get("text", "") for item in data.get("candidates", []) for part in item.get("content", {}).get("parts", []))
            return record(provider, "PASS" if text.strip() else "WARN", "Generation returned text" if text.strip() else "HTTP 200 but no text; inspect model/output limits")
    except Exception as exc:
        return record(provider, "FAIL", f"{type(exc).__name__}; error details omitted to protect credentials")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Check public sources and configured model authentication")
    parser.add_argument("--generate", action="store_true", help="Also send one tiny Gemini generation request; may consume quota/credits")
    args = parser.parse_args()
    if args.generate and not args.live:
        parser.error("--generate requires --live")
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
    rows = local_checks()
    if args.live:
        checks = [prices, announcements,
                  lambda: webpage("Screener discovery", "https://www.screener.in/company/RELIANCE/consolidated/"),
                  lambda: webpage("Company IR annual reports", "https://www.infosys.com/investors/reports-filings/annual-report.html"),
                  lambda: model_check(args.generate)]
        with ThreadPoolExecutor(max_workers=6) as pool:
            rows.extend(pool.map(lambda check: check(), checks))
    report = {"checked_at_utc": datetime.now(timezone.utc).isoformat(), "checks": rows}
    destination = ROOT / "tmp" / "environment-check.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for row in rows:
        print(f"[{row['status']}] {row['check']}: {row['detail']}")
    print(f"Report: {destination}")
    return 1 if any(row["status"] == "FAIL" for row in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
