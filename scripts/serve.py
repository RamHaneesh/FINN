"""Single-command local server with one embedded background worker."""
import argparse
import os

import uvicorn


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    args = parser.parse_args()
    os.environ["FINN_EMBEDDED_WORKER"] = "true"
    uvicorn.run("finn.api.app:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
