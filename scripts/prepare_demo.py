"""Warm real portfolio data and transcript research before a mobile demonstration."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json

from finn.config import get_settings
from finn.pipeline import Pipeline
from finn.services.portfolio import PortfolioService
from finn.sources.financials import FinancialSource


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--research", nargs="*", default=["INFY", "DIXON"])
    parser.add_argument("--max-calls", type=int, default=6)
    args = parser.parse_args()
    pipeline = Pipeline(get_settings())
    service = PortfolioService(pipeline)
    def warm(company):
        ticker = company["ticker"]
        result = pipeline.refresh(ticker, days=30, price_threshold=3, volume_multiple=2)
        try:
            FinancialSource(pipeline.store, pipeline.http).fetch(ticker)
        except Exception as exc:
            result["warnings"].append(f"Financial table: {type(exc).__name__}")
        print(json.dumps({"ticker": ticker, "bars": result["price_bar_count"], "filings": result["filing_count"], "warnings": result["warnings"]}), flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(warm, service.companies))
    for ticker in args.research:
        try:
            report = pipeline.research(ticker, max_documents=6, max_calls=args.max_calls, progress=lambda stage: print(f"{ticker}: {stage}", flush=True))
            print(f"{ticker}: {len(report.comparisons)} comparisons, {report.model_calls} model calls, coverage={report.coverage}", flush=True)
        except Exception as exc:
            print(f"{ticker}: research failed ({type(exc).__name__}); snapshot remains usable", flush=True)


if __name__ == "__main__":
    main()
