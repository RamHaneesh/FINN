"""Persisted stage progress and elapsed time; no remaining-time estimates."""
from datetime import datetime, timezone

from finn.domain import utc_now

STAGES = [
    ("financial_tables", "Financial snapshot", "Fetching the company's financial table."),
    ("discovering_transcripts", "Find transcripts", "Finding original management transcripts."),
    ("parsing", "Read transcripts", "Downloading and reading the source documents."),
    ("extracting", "Analyze narrative", "Extracting management statements and checking source quotes."),
    ("comparing", "Compare delivery", "Matching targets with actuals and saving the evidence."),
]


def seconds_since(value, now=None):
    return max(0, ((now or datetime.now(timezone.utc)) - datetime.fromisoformat(value)).total_seconds())


def heartbeat(pipeline, job_id=None):
    saved = pipeline.store.get("worker-status-v1", "main")
    if not saved or saved.get("job_id") != job_id or seconds_since(saved["seen_at"]) >= 10:
        pipeline.store.put("worker-status-v1", "main", {"seen_at": utc_now(), "job_id": job_id})


class JobProgress:
    def __init__(self, store, embedded_alive=False):
        self.store, self.embedded_alive = store, embedded_alive

    def worker_available(self):
        saved = self.store.get("worker-status-v1", "main")
        return self.embedded_alive or bool(saved and seconds_since(saved["seen_at"]) < 180)

    def latest(self, ticker):
        jobs = [job for job in self.store.recent_jobs(ticker) if job["payload"].get("_kind", "research") == "research"]
        active = next((job for job in jobs if job["status"] in {"queued", "running"}), None)
        return self.present(active or jobs[0], include_result=False) if jobs else None

    def present(self, job, include_result=True):
        data = dict(job)
        active = job["status"] in {"queued", "running"}
        end = datetime.now(timezone.utc) if active else datetime.fromisoformat(job["updated_at"])
        elapsed = seconds_since(job.get("started_at", job["created_at"]), end)
        parts = job["stage"].split(":")
        phase = parts[0]
        index = next((index for index, (key, _, _) in enumerate(STAGES) if key == phase), 0)
        title, detail = STAGES[index][1:]
        if phase == "parsing" and len(parts) == 3:
            detail = f"Reading transcript {parts[1]} of {parts[2]}. The financial snapshot is available separately."
        if phase == "extracting" and len(parts) == 3:
            detail = f"Checking source section {parts[1]} of {parts[2]} for this focused run."
        if job["status"] == "queued":
            title, detail = "Waiting to start", "Your analysis is queued. It will continue if you leave this view."
        elif job["status"] == "completed":
            title = "Analysis saved"
            detail = "Partial source coverage; open the verification notes." if (job.get("result") or {}).get("coverage") == "partial" else "Research and source evidence are ready."
        elif job["status"] == "failed":
            title, detail = "Analysis could not finish", job.get("error") or "Please retry. Previous saved research is preserved."
        queue_ahead = 0
        if job["status"] == "queued":
            with self.store.connection() as db:
                queue_ahead = db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running') AND id!=? AND created_at<=?", (job["id"], job["created_at"])).fetchone()[0]
        data["progress"] = {"phase": phase, "step": index + 1 if job["status"] == "running" else 5 if job["status"] == "completed" else 0, "total_steps": 5, "title": title, "detail": detail, "elapsed_seconds": round(elapsed), "queue_ahead": queue_ahead, "worker_available": self.worker_available(), "last_activity_seconds": round(seconds_since(job["updated_at"])), "stages": [title for _, title, _ in STAGES]}
        if not include_result:
            data.pop("result", None)
            data.pop("payload", None)
        return data
