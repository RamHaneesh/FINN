import argparse
import logging

from finn.config import get_settings
from finn.jobs.worker import run
from finn.pipeline import Pipeline


def main():
    parser = argparse.ArgumentParser(description="Run FINN's single research worker")
    parser.add_argument("--once", action="store_true", help="Process at most one job and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    run(Pipeline(get_settings()), once=args.once)


if __name__ == "__main__":
    main()
