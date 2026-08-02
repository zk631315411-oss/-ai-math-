"""Diagnosis V2 orchestration: adapt, score, validate, persist, project."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from app.config import config
from app.db.diagnosis_v2_db import (
    finish_run,
    run_is_terminal,
    save_observations,
    start_run,
)
from app.services.diagnosis.adapters import adapt_exercise_attempt, adapt_qa_turn, exercise_kg_context
from app.services.diagnosis.projectors import close_ready_dimension_windows, project_pending_stage_evidence
from app.services.diagnosis.dialogue_state import project_pending_dialogue_states
from app.services.diagnosis.scorers import (
    PROMPT_VERSION,
    SCORER_VERSION,
    ObservationValidationError,
    score_exercise_dimensions,
    score_exercise_stage,
    score_qa_dimensions,
    score_qa_stage,
)


SCORER_TYPES = {
    "qa_turn": ("qa_stage", "qa_dimension"),
    "exercise_attempt": ("exercise_stage", "exercise_dimension"),
}


async def process_qa_turn(row: dict) -> dict[str, bool]:
    event = adapt_qa_turn(row)
    stage_task = _run_scorer(
        source_type="qa_turn", source_id=event.turn_id, scorer_type="qa_stage",
        scorer=lambda: score_qa_stage(event),
    )
    dimension_task = _run_scorer(
        source_type="qa_turn", source_id=event.turn_id, scorer_type="qa_dimension",
        scorer=lambda: score_qa_dimensions(event),
    )
    stage_ok, dimension_ok = await asyncio.gather(stage_task, dimension_task)
    _project_after_scoring()
    return {"stage": stage_ok, "dimension": dimension_ok}


async def process_exercise_attempt(row: dict) -> dict[str, bool]:
    event = adapt_exercise_attempt(row)
    kg_nodes, kg_relations = exercise_kg_context(event)
    stage_task = _run_scorer(
        source_type="exercise_attempt", source_id=event.attempt_id, scorer_type="exercise_stage",
        scorer=lambda: score_exercise_stage(event, kg_nodes, kg_relations),
    )
    dimension_task = _run_scorer(
        source_type="exercise_attempt", source_id=event.attempt_id, scorer_type="exercise_dimension",
        scorer=lambda: score_exercise_dimensions(event),
    )
    stage_ok, dimension_ok = await asyncio.gather(stage_task, dimension_task)
    _project_after_scoring()
    return {"stage": stage_ok, "dimension": dimension_ok}


async def _run_scorer(
    *,
    source_type: str,
    source_id: str,
    scorer_type: str,
    scorer: Callable[[], Awaitable[tuple[list, str]]],
) -> bool:
    if run_is_terminal(source_type, source_id, scorer_type, SCORER_VERSION):
        return True
    run_id = start_run(
        source_type=source_type,
        source_id=source_id,
        scorer_type=scorer_type,
        scorer_version=SCORER_VERSION,
        model_name=config.PROFILE_LLM_MODEL,
        prompt_version=PROMPT_VERSION,
    )
    try:
        observations, raw = await scorer()
        save_observations(run_id, observations)
        finish_run(run_id, "success", raw_output=raw)
        return True
    except ObservationValidationError as exc:
        finish_run(run_id, "rejected", error_reason=str(exc))
        return False
    except Exception as exc:
        finish_run(run_id, "failed", error_reason=str(exc))
        return False


def _project_after_scoring() -> None:
    project_pending_stage_evidence()
    close_ready_dimension_windows()
    project_pending_dialogue_states()
