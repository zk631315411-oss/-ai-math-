"""Diagnosis V2 worker consuming QA turns and immutable exercise attempts."""

from __future__ import annotations

import asyncio

from app.db.diagnosis_v2_db import list_pending_sources
from app.services.diagnosis.projectors import close_ready_dimension_windows, project_pending_stage_evidence
from app.services.diagnosis.scorers import SCORER_VERSION
from app.services.diagnosis.v2_service import process_exercise_attempt, process_qa_turn


DIAGNOSTIC_BATCH_THRESHOLD = 5
DIAGNOSTIC_CHECK_INTERVAL = 30


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
    return any(any(item.values()) for item in results)


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
