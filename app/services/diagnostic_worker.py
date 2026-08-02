"""Diagnosis V2 worker consuming QA turns and immutable exercise attempts."""

from __future__ import annotations

import asyncio

from app.db.diagnosis_v2_db import list_pending_sources
from app.services.diagnosis.projectors import close_ready_dimension_windows, project_pending_stage_evidence
from app.services.diagnosis.dialogue_state import project_pending_dialogue_states
from app.services.diagnosis.scorers import SCORER_VERSION
from app.services.diagnosis.v2_service import process_exercise_attempt, process_qa_turn


DIAGNOSTIC_BATCH_THRESHOLD = 5
DIAGNOSTIC_CHECK_INTERVAL = 30
DIALOGUE_STATE_BATCH_SIZE = 100
DIALOGUE_STATE_MAX_BATCHES = 10

# user_id 级别的诊断锁，防止事件触发与轮询并发处理同一用户
_diagnosis_locks: dict[str, asyncio.Lock] = {}


def _get_diagnosis_lock(user_id: str) -> asyncio.Lock:
    """获取用户级别的诊断锁，避免并发触发同一用户的多轮诊断。"""
    if user_id not in _diagnosis_locks:
        _diagnosis_locks[user_id] = asyncio.Lock()
    return _diagnosis_locks[user_id]


async def listen_qa_done(bus, user_id: str, persist_done: asyncio.Event | None = None) -> None:
    """通过 StreamBus 监听 QA 完成事件，实时触发诊断。

    作为 answer_turn 内部 StreamBus 的订阅者，收到 done 事件后：
    1. 等待持久化完成（确保 qa_turn_records 已落盘）
    2. 获取用户级锁防止并发
    3. 立即触发诊断
    不阻塞主事件流，诊断失败不影响主流程。
    """
    try:
        async for event in bus.subscribe("diagnosis", replay=True):
            if event.get("event") == "done" or event.get("type") == "done":
                break
        # 等待持久化完成，确保诊断能读到刚写入的记录
        if persist_done is not None:
            await persist_done.wait()
        # 获取用户级锁，防止与轮询并发处理同一用户
        lock = _get_diagnosis_lock(user_id)
        async with lock:
            await run_diagnostic_batch(user_id)
    except Exception as exc:
        print(f"[diagnostic_worker] 实时诊断触发失败: {exc}")


def should_trigger_diagnostic_batch(user_id: str) -> bool:
    """Compatibility helper: true when either V2 source has pending records."""

    for source_type, scorer_types in (
        ("qa_turn", ("qa_stage", "qa_dimension")),
        ("exercise_attempt", ("exercise_stage", "exercise_dimension")),
    ):
        for scorer_type in scorer_types:
            if list_pending_sources(
                source_type, scorer_type, SCORER_VERSION, limit=1, user_id=user_id
            ):
                return True
    return False


async def run_diagnostic_batch(user_id: str | None = None) -> bool:
    """Process each source independently; one failure never marks another source."""

    qa_rows = _merge_pending_rows("qa_turn", ("qa_stage", "qa_dimension"), user_id)
    exercise_rows = _merge_pending_rows(
        "exercise_attempt", ("exercise_stage", "exercise_dimension"), user_id
    )
    results: list[dict[str, bool]] = []
    for row in qa_rows:
        results.append(await process_qa_turn(row))
    for row in exercise_rows:
        results.append(await process_exercise_attempt(row))
    project_pending_stage_evidence()
    close_ready_dimension_windows()
    dialogue_count = _drain_dialogue_state_backlog(user_id)
    return any(any(item.values()) for item in results) or dialogue_count > 0


def _drain_dialogue_state_backlog(user_id: str | None = None) -> int:
    total = 0
    for _ in range(DIALOGUE_STATE_MAX_BATCHES):
        count = project_pending_dialogue_states(
            DIALOGUE_STATE_BATCH_SIZE, user_id=user_id
        )
        total += count
        if count < DIALOGUE_STATE_BATCH_SIZE:
            break
    return total


def _merge_pending_rows(
    source_type: str,
    scorer_types: tuple[str, ...],
    user_id: str | None,
) -> list[dict]:
    merged: dict[str, dict] = {}
    for scorer_type in scorer_types:
        rows = list_pending_sources(
            source_type, scorer_type, SCORER_VERSION,
            limit=DIAGNOSTIC_BATCH_THRESHOLD, user_id=user_id,
        )
        for row in rows:
            merged.setdefault(row["id"], row)
    return list(merged.values())[:DIAGNOSTIC_BATCH_THRESHOLD]


async def check_and_run_diagnostic() -> bool:
    return await run_diagnostic_batch()


async def diagnostic_worker_loop() -> None:
    print(f"[DiagnosticWorkerV2] loop started, interval={DIAGNOSTIC_CHECK_INTERVAL}s")
    while True:
        try:
            await check_and_run_diagnostic()
        except Exception as exc:
            print(f"[DiagnosticWorkerV2] loop failed: {exc}")
        await asyncio.sleep(DIAGNOSTIC_CHECK_INTERVAL)
