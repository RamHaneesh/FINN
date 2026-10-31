import logging
import time

from finn.models import ModelError
from finn.pipeline import Pipeline
from finn.sources.http import SourceError

logger = logging.getLogger(__name__)


def run_once(pipeline: Pipeline) -> bool:
    job = pipeline.store.claim()
    if job is None:
        return False
    job_id = job["id"]
    try:
        report = pipeline.research(job["ticker"], **job["payload"], progress=lambda stage: pipeline.store.update_job(job_id, stage))
        pipeline.store.update_job(job_id, "complete", "completed", report.model_dump(mode="json"))
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
