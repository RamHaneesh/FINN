import argparse
import json

from finn.config import get_settings
from finn.models import ModelError
from finn.pipeline import Pipeline
from finn.sources.http import SourceError


def main():
    parser = argparse.ArgumentParser(description="Run bounded primary-source research; uncached extraction consumes Gemini quota")
    parser.add_argument("ticker")
    parser.add_argument("--max-documents", type=int, choices=range(1, 7), default=6)
    parser.add_argument("--max-calls", type=int, choices=range(0, 21), default=None)
    parser.add_argument("--refresh", action="store_true", help="Refetch source documents; unchanged content still reuses model cache")
    args = parser.parse_args()
    try:
        pipeline = Pipeline(get_settings())
        report = pipeline.research(args.ticker, max_documents=args.max_documents, max_calls=args.max_calls, refresh=args.refresh, progress=lambda stage: print(f"Stage: {stage}", flush=True))
        destination = pipeline.store.root / "research" / f"{report.ticker}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        print(json.dumps({"report": str(destination), "narratives": len(report.narratives), "facts": len(report.facts), "comparisons": len(report.comparisons), "model_calls": report.model_calls, "cache_hits": report.cache_hits, "coverage": report.coverage, "warnings": report.warnings}, indent=2))
    except Exception as exc:
        detail = str(exc) if isinstance(exc, (SourceError, ModelError, ValueError)) else type(exc).__name__
        parser.exit(1, f"Research failed: {detail}\n")


if __name__ == "__main__":
    main()
