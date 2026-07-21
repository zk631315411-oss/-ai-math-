"""Persistence for diagnosis V2 runs, evidence, and source adapters."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Any

from app.db.connection import get_conn
from app.services.diagnosis.contracts import DimensionObservation, StageObservation


def _id() -> str:
    return str(uuid.uuid4())


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def save_exercise_attempt(
    *,
    exercise: dict,
    student_answer: str,
    is_correct: bool,
    grading_feedback: str,
    grader_version: str,
    grading_valid: bool = True,
) -> str:
    attempt_id = _id()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO exercise_attempts (
                id, exercise_id, user_id, sequence_id, target_concept, target_stage,
                difficulty, question, student_answer, correct_answer, is_correct,
                hint_level, grading_feedback, grader_version
                , analysis_status, grading_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                attempt_id,
                exercise["id"],
                exercise["user_id"],
                exercise.get("sequence_id") or "",
                exercise.get("topic") or "",
                exercise.get("target_stage"),
                exercise.get("difficulty") or "",
                exercise.get("question") or "",
                student_answer,
                exercise.get("answer") or "",
                1 if is_correct else 0,
                int(exercise.get("hint_level") or 0),
                grading_feedback or "",
                grader_version or "",
                "ready" if is_correct else "pending",
                "valid" if grading_valid else "invalid",
            ),
        )
        conn.commit()
        return attempt_id
    finally:
        conn.close()


def update_exercise_attempt_error(attempt_id: str, error_analysis: dict | None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "UPDATE exercise_attempts SET error_analysis=?, analysis_status='ready' WHERE id=?",
            (json.dumps(error_analysis or {}, ensure_ascii=False), attempt_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_pending_sources(
    source_type: str,
    scorer_type: str,
    scorer_version: str,
    *,
    limit: int = 20,
    user_id: str | None = None,
) -> list[dict]:
    table = "qa_turn_records" if source_type == "qa_turn" else "exercise_attempts"
    where = [
        "NOT EXISTS (SELECT 1 FROM diagnosis_runs r "
        f"WHERE r.source_type=? AND r.source_id={table}.id "
        "AND r.scorer_type=? AND r.scorer_version=? AND "
        "(r.status IN ('success','rejected') OR r.attempts >= 3))"
    ]
    params: list[Any] = [source_type, scorer_type, scorer_version]
    if user_id:
        where.append(f"{table}.user_id=?")
        params.append(user_id)
    if source_type == "qa_turn":
        where.append("COALESCE(error, '') = ''")
    else:
        where.append("analysis_status='ready'")
        where.append("grading_status='valid'")
    params.append(limit)
    conn = get_conn()
    try:
        rows = conn.execute(
            f"SELECT * FROM {table} WHERE {' AND '.join(where)} ORDER BY created_at ASC LIMIT ?",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_previous_qa_turn(row: dict) -> dict | None:
    marker_id = row.get("marker_id")
    chat_id = row.get("chat_id")
    if not marker_id and not chat_id:
        return None
    conn = get_conn()
    try:
        previous = conn.execute(
            """
            SELECT * FROM qa_turn_records
            WHERE user_id=? AND id<>? AND created_at < ? AND COALESCE(error, '')=''
              AND ((? <> '' AND marker_id=?) OR (? <> '' AND chat_id=?))
            ORDER BY created_at DESC LIMIT 1
            """,
            (
                row["user_id"], row["id"], row.get("created_at") or "",
                marker_id or "", marker_id or "", chat_id or "", chat_id or "",
            ),
        ).fetchone()
        return dict(previous) if previous else None
    finally:
        conn.close()


def unpack_qa_row(row: dict) -> dict:
    result = dict(row)
    result["context_snapshot"] = _loads(result.get("context_snapshot"), {})
    result["messages_snapshot"] = _loads(result.get("messages_snapshot"), [])
    return result


def unpack_exercise_attempt(row: dict) -> dict:
    result = dict(row)
    result["is_correct"] = bool(result.get("is_correct"))
    result["error_analysis"] = _loads(result.get("error_analysis"), {})
    return result


def start_run(
    *,
    source_type: str,
    source_id: str,
    scorer_type: str,
    scorer_version: str,
    model_name: str,
    prompt_version: str,
) -> str:
    run_id = _id()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO diagnosis_runs (
                id, source_type, source_id, scorer_type, scorer_version, status,
                model_name, prompt_version, attempts
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(source_type, source_id, scorer_type, scorer_version) DO UPDATE SET
                status='running', attempts=diagnosis_runs.attempts + 1,
                model_name=excluded.model_name, prompt_version=excluded.prompt_version,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                run_id,
                source_type,
                source_id,
                scorer_type,
                scorer_version,
                "running",
                model_name,
                prompt_version,
            ),
        )
        row = conn.execute(
            """
            SELECT id FROM diagnosis_runs
            WHERE source_type=? AND source_id=? AND scorer_type=? AND scorer_version=?
            """,
            (source_type, source_id, scorer_type, scorer_version),
        ).fetchone()
        conn.commit()
        return row["id"]
    finally:
        conn.close()


def finish_run(run_id: str, status: str, *, raw_output: str = "", error_reason: str = "") -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            UPDATE diagnosis_runs SET status=?, raw_output=?, error_reason=?,
                updated_at=CURRENT_TIMESTAMP WHERE id=?
            """,
            (status, raw_output or "", error_reason or "", run_id),
        )
        conn.commit()
    finally:
        conn.close()


def run_is_terminal(
    source_type: str,
    source_id: str,
    scorer_type: str,
    scorer_version: str,
) -> bool:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT status, attempts FROM diagnosis_runs
            WHERE source_type=? AND source_id=? AND scorer_type=? AND scorer_version=?
            """,
            (source_type, source_id, scorer_type, scorer_version),
        ).fetchone()
        return bool(row and (row["status"] in {"success", "rejected"} or row["attempts"] >= 3))
    finally:
        conn.close()


def save_observations(
    run_id: str,
    observations: list[StageObservation | DimensionObservation],
) -> list[str]:
    conn = get_conn()
    ids: list[str] = []
    try:
        with conn:
            for observation in observations:
                data = asdict(observation)
                is_stage = isinstance(observation, StageObservation)
                identity = "|".join(
                    str(value or "")
                    for value in (
                        run_id,
                        "stage" if is_stage else "dimension",
                        observation.concept_name if is_stage else observation.dimension,
                        "" if is_stage else observation.facet,
                        observation.student_quote,
                    )
                )
                evidence_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
                conn.execute(
                    """
                    INSERT OR IGNORE INTO diagnostic_evidence (
                        id, run_id, source_type, source_id, user_id, sequence_id,
                        observation_type, concept_name, observed_stage, dimension,
                        facet, direction, strength, student_quote, behavior,
                        support_level, scorer_version, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence_id,
                        run_id,
                        observation.source_type,
                        observation.source_id,
                        observation.user_id,
                        observation.sequence_id,
                        "stage" if is_stage else "dimension",
                        observation.concept_name if is_stage else None,
                        observation.observed_stage if is_stage else None,
                        None if is_stage else observation.dimension,
                        None if is_stage else observation.facet,
                        observation.direction,
                        observation.strength,
                        observation.student_quote,
                        observation.behavior if is_stage else None,
                        observation.support_level if is_stage else "unknown",
                        observation.scorer_version,
                        json.dumps(data, ensure_ascii=False),
                    ),
                )
                row = conn.execute("SELECT id FROM diagnostic_evidence WHERE id=?", (evidence_id,)).fetchone()
                if row:
                    ids.append(row["id"])
        return ids
    finally:
        conn.close()


def get_evidence(evidence_id: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM diagnostic_evidence WHERE id=?", (evidence_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_unprojected_stage_evidence(limit: int = 100) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT e.* FROM diagnostic_evidence e
            WHERE e.observation_type='stage' AND NOT EXISTS (
                SELECT 1 FROM state_projection_log p
                WHERE p.evidence_id=e.id AND p.projection_type='stage'
                  AND p.projection_version='v2'
            ) ORDER BY e.created_at ASC LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def list_unwindowed_dimension_events(user_id: str | None = None) -> list[dict]:
    where = "e.observation_type='dimension' AND e.window_id IS NULL"
    params: list[Any] = []
    if user_id:
        where += " AND e.user_id=?"
        params.append(user_id)
    conn = get_conn()
    try:
        rows = conn.execute(
            f"SELECT e.* FROM diagnostic_evidence e WHERE {where} ORDER BY e.created_at ASC",
            params,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
