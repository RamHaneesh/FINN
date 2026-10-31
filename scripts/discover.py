import argparse
import json

from finn.config import get_settings
from finn.pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser(description="Discover original annual reports and transcripts; no model call")
    parser.add_argument("ticker")
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    try:
        links = Pipeline(get_settings()).discover(args.ticker, refresh=args.refresh)
        print(json.dumps([link.model_dump(mode="json") for link in links], indent=2))
    except Exception as exc:
        parser.exit(1, f"Discovery failed: {type(exc).__name__}; check symbol and source access.\n")


if __name__ == "__main__":
    main()
