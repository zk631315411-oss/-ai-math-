"""Recoverable application worker for asynchronous policy planning."""

from __future__ import annotations

import asyncio
import uuid

from app.config import config
from app.services.intervention import repository as repo


class InterventionWorker:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._queued: set[str] = set()
        self._tasks: list[asyncio.Task] = []
        self.worker_id = str(uuid.uuid4())

    async def start(self) -> None:
        if any(not task.done() for task in self._tasks):
            return
        for job_id in repo.list_recoverable_job_ids():
            self.enqueue(job_id)
        count = max(1, config.INTERVENTION_MAX_CONCURRENCY)
        self._tasks = [asyncio.create_task(self._run(), name=f"intervention-worker-{i + 1}") for i in range(count)]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        repo.release_worker_claims(self.worker_id)

    def enqueue_snapshot(self, snapshot_id: str) -> None:
        job_id = repo.get_job_id_for_snapshot(snapshot_id)
        if job_id:
            self.enqueue(job_id)

    def enqueue(self, job_id: str) -> None:
        if job_id in self._queued:
            return
        self._queued.add(job_id)
        self.queue.put_nowait(job_id)

    async def _run(self) -> None:
        while True:
            job_id = await self.queue.get()
            self._queued.discard(job_id)
            try:
                job = repo.claim_job(job_id, self.worker_id)
                if not job:
                    continue
                snapshot = repo.get_snapshot(job["snapshot_id"])
                if not snapshot:
                    repo.finish_job(job_id, self.worker_id, status="failed", error="snapshot_not_found")
                    continue
                from app.services.intervention.service import intervention_service
                result = await asyncio.to_thread(intervention_service.plan_snapshot, snapshot)
                repo.finish_job(job_id, self.worker_id, status="ready", result=result)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                repo.finish_job(job_id, self.worker_id, status="failed", error=str(exc))
            finally:
                self.queue.task_done()


intervention_worker = InterventionWorker()
