import argparse
import json

from finn.config import ROOT, get_settings
from finn.domain import normalize_ticker
from finn.pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser(description="Refresh portfolio EOD data/filings and save initial attention cards; no model calls")
    parser.add_argument("tickers", nargs="*")
    parser.add_argument("--portfolio", action="store_true")
    parser.add_argument("--days", type=int, choices=range(1, 91), default=1)
    parser.add_argument("--price-percent", type=float, default=3.)
    parser.add_argument("--volume-multiple", type=float, default=2.)
    parser.add_argument("--categories", nargs="*", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.price_percent <= 0 or args.volume_multiple <= 0:
        parser.error("Thresholds must be positive")
    tickers = args.tickers
    if args.portfolio:
        tickers += [row["ticker"] for row in json.loads((ROOT / "config" / "portfolio.json").read_text())["companies"]]
    if not tickers:
        parser.error("Provide NSE tickers or --portfolio")
    try:
        tickers = list(dict.fromkeys(normalize_ticker(ticker) for ticker in tickers))
    except ValueError as exc:
        parser.error(str(exc))
    pipeline = Pipeline(get_settings())
    failures = False
    for ticker in tickers:
        data = pipeline.refresh(ticker, args.days, args.price_percent, args.volume_multiple, args.categories, args.force)
        print(json.dumps(data, indent=2), flush=True)
        failures |= bool(data["warnings"])
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
