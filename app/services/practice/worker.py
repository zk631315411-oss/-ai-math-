"""Durable single-process worker for conversation practice drafts."""

from __future__ import annotations

import asyncio
import uuid

from app.config import config
from app.services.practice.agents import build_draft
from app.services.practice.repository import (
    claim_draft,
    finish_claim,
    get_draft_internal,
    list_recoverable_draft_ids,
    release_worker_claims,
    update_draft,
)


class PracticeWorker:
    def __init__(self) -> None:
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self._queued: set[str] = set()
        self._tasks: list[asyncio.Task] = []
        self.worker_id = str(uuid.uuid4())

    async def start(self) -> None:
        if any(not task.done() for task in self._tasks):
            return
        for draft_id in list_recoverable_draft_ids():
            self.enqueue(draft_id)
        worker_count = max(1, config.EXERCISE_MAX_CONCURRENCY)
        self._tasks = [
            asyncio.create_task(self._run(), name=f"practice-worker-{index + 1}")
            for index in range(worker_count)
        ]

    async def stop(self) -> None:
        if not self._tasks:
            return
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        release_worker_claims(self.worker_id)

    def enqueue(self, draft_id: str) -> None:
        if draft_id in self._queued:
            return
        self._queued.add(draft_id)
        self.queue.put_nowait(draft_id)

    async def _run(self) -> None:
        while True:
            draft_id = await self.queue.get()
            self._queued.discard(draft_id)
            try:
                draft = claim_draft(draft_id, self.worker_id)
                if not draft:
                    continue
                await build_draft(draft)
                completed = get_draft_internal(draft_id)
                finish_claim(
                    draft_id,
                    self.worker_id,
                    status="failed" if completed and completed.get("status") == "failed" else "ready",
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                update_draft(draft_id, status="failed", error=str(exc))
                finish_claim(draft_id, self.worker_id, status="failed", error=str(exc))
            finally:
                self.queue.task_done()


practice_worker = PracticeWorker()
