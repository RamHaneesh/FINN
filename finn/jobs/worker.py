import logging
import time

from finn.models import ModelError
from finn.pipeline import Pipeline
from finn.sources.http import SourceError
from finn.jobs.progress import heartbeat

logger = logging.getLogger(__name__)


def run_once(pipeline: Pipeline) -> bool:
    heartbeat(pipeline)
    job = pipeline.store.claim()
    if job is None:
        return False
    job_id = job["id"]
    try:
        payload = dict(job["payload"])
        kind = payload.pop("_kind", "research")
        def progress(stage):
            heartbeat(pipeline, job_id)
            pipeline.store.update_job(job_id, stage)
        if kind == "refresh":
            from finn.services.portfolio import PortfolioService
            result = PortfolioService(pipeline).refresh(progress)
        elif kind == "headlines":
            from finn.services.results import extract_headlines
            result = extract_headlines(pipeline, payload["event"])
        elif kind == "business":
            from finn.services.business import build_business
            progress("business")
            result = build_business(pipeline, job["ticker"], **payload)
        else:
            report = pipeline.research(job["ticker"], **payload, progress=progress)
            result = report.model_dump(mode="json")
        pipeline.store.update_job(job_id, "complete", "completed", result)
    except Exception as exc:
        detail = str(exc) if isinstance(exc, (SourceError, ModelError)) else f"{type(exc).__name__}; inspect source access and configuration"
        pipeline.store.update_job(job_id, "failed", "failed", error=detail)
        logger.warning("Research job %s failed: %s", job_id, type(exc).__name__)
    return True


def run(pipeline: Pipeline, once=False):
    # Run exactly one worker for this prototype. Stale jobs recover after 30 minutes.
    while True:
        found = run_once(pipeline)
        if once:
            return
        if not found:
            time.sleep(2)
