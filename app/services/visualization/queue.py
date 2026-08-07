"""RQ enqueue boundary kept free of Manim imports."""

from __future__ import annotations

from app.config import config
from app.db.visualization_db import get_animation_job, set_rq_job_id, update_animation_job


def enqueue_animation(job_id: str) -> str:
    try:
        from redis import Redis
        from rq import Queue, Retry

        connection = Redis.from_url(config.VISUALIZATION_REDIS_URL)
        connection.ping()
        queue = Queue(config.VISUALIZATION_QUEUE, connection=connection)
        rq_job = queue.enqueue(
            "app.workers.manim_worker.render_animation_job",
            job_id,
            job_timeout=120,
            retry=Retry(max=1, interval=[5]),
            result_ttl=3600,
            failure_ttl=86400,
        )
        set_rq_job_id(job_id, rq_job.id)
        return rq_job.id
    except Exception as exc:
        update_animation_job(job_id, "failed", error=f"动画渲染服务不可用: {exc}")
        raise RuntimeError("动画渲染服务当前不可用") from exc


def reconcile_animation_job(job: dict) -> dict:
    """Repair queued/running DB state after an RQ timeout or worker death."""
    if job.get("status") not in {"queued", "running"} or not job.get("rq_job_id"):
        return job
    try:
        from redis import Redis
        from rq.job import Job

        connection = Redis.from_url(config.VISUALIZATION_REDIS_URL)
        rq_job = Job.fetch(job["rq_job_id"], connection=connection)
        raw_status = rq_job.get_status(refresh=True)
        rq_status = getattr(raw_status, "value", str(raw_status)).lower()
        if rq_status in {"failed", "stopped", "canceled", "cancelled"}:
            detail = (rq_job.exc_info or "动画渲染任务异常终止").strip().splitlines()[-1]
            update_animation_job(job["id"], "failed", error=detail)
            return get_animation_job(job["id"], job.get("user_id"))
        expected = "running" if rq_status in {"started", "busy"} else "queued"
        if job.get("status") != expected and rq_status in {
            "queued", "deferred", "scheduled", "started", "busy",
        }:
            update_animation_job(job["id"], expected)
            return get_animation_job(job["id"], job.get("user_id"))
    except Exception:
        # Polling still returns the durable last-known state while Redis is unavailable.
        return job
    return job
