"""Single-command local server with one embedded background worker."""
import argparse
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    os.environ["FINN_EMBEDDED_WORKER"] = "true"
    uvicorn.run("finn.api.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
