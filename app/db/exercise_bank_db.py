"""题库 CRUD — exercise_bank 表操作。"""

import uuid
import json
from app.db.connection import get_conn


def _uid():
    return str(uuid.uuid4())


def save_exercise(user_id: str, topic: str, difficulty: str, target_stage: int,
                  question: str, answer: str, verification: str = "",
                  hints: list | None = None, computable: dict | None = None,
                  source_chat_id: str = "", source: str = "llm",
                  sequence_id: str = "") -> str:
    eid = _uid()
    conn = get_conn()
    conn.execute(
        """INSERT INTO exercise_bank
           (id, user_id, topic, difficulty, target_stage, question, answer,
            verification, hints, computable, source_chat_id, source, sequence_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (eid, user_id, topic, difficulty, target_stage,
         question, answer, verification,
         json.dumps(hints or [], ensure_ascii=False),
         json.dumps(computable or {}, ensure_ascii=False),
         source_chat_id, source, sequence_id),
    )
    conn.commit()
    conn.close()
    return eid


def get_exercise(exercise_id: str) -> dict | None:
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM exercise_bank WHERE id=?",
        (exercise_id,),
    ).fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    d["hints"] = json.loads(d.get("hints", "[]"))
    d["computable"] = json.loads(d.get("computable", "{}"))
    return d


def list_exercises(user_id: str, topic: str = "", limit: int = 20) -> list[dict]:
    conn = get_conn()
    if topic:
        rows = conn.execute(
            """SELECT * FROM exercise_bank
               WHERE user_id=? AND topic=? ORDER BY created_at DESC LIMIT ?""",
            (user_id, topic, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT * FROM exercise_bank
               WHERE user_id=? ORDER BY created_at DESC LIMIT ?""",
            (user_id, limit),
        ).fetchall()
    conn.close()
    return [_unpack(dict(r)) for r in rows]


def list_user_exercises(user_id: str, topic: str = "", limit: int = 20) -> list[dict]:
    """Return owned/generated exercises plus textbook exercises attempted by a user."""
    conn = get_conn()
    where = ["(eb.user_id=? OR state.user_id IS NOT NULL)"]
    params: list = [user_id, user_id]
    if topic:
        where.append("eb.topic=?")
        params.append(topic)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT eb.* FROM exercise_bank eb
        LEFT JOIN exercise_user_state state
          ON state.exercise_id=eb.id AND state.user_id=?
        WHERE {' AND '.join(where)}
        ORDER BY COALESCE(state.updated_at, eb.created_at) DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    exercises = [_unpack(dict(row)) for row in rows]
    states = get_user_exercise_states(user_id, [exercise["id"] for exercise in exercises], conn=conn)
    conn.close()
    return [_with_user_state(exercise, states.get(exercise["id"])) for exercise in exercises]


def list_by_sequence_id(sequence_id: str, max_stage: int = 5, limit: int = 5) -> list[dict]:
    """按 section + 难度筛选练习题（用于按页出题）。"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM exercise_bank
           WHERE sequence_id=? AND target_stage <= ? AND source='textbook'
             AND quality_score >= 0
           ORDER BY target_stage ASC LIMIT ?""",
        (sequence_id, max_stage, limit),
    ).fetchall()
    conn.close()
    return [_unpack(dict(r)) for r in rows]


def submit_answer(exercise_id: str, student_answer: str) -> int:
    """Legacy template mutation helper. New API routes use per-user state."""
    conn = get_conn()
    cursor = conn.execute(
        """UPDATE exercise_bank
           SET is_answered = 1, student_answer = ?
           WHERE id = ? AND is_answered = 0""",
        (student_answer, exercise_id),
    )
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected


def record_result(exercise_id: str, is_correct: bool, error_analysis: dict | None = None):
    conn = get_conn()
    conn.execute(
        """UPDATE exercise_bank
           SET is_correct = ?, error_analysis = ?
           WHERE id = ?""",
        (1 if is_correct else 0,
         json.dumps(error_analysis, ensure_ascii=False) if error_analysis else None,
         exercise_id),
    )
    conn.commit()
    conn.close()


def update_hint_level(exercise_id: str) -> int:
    """递增 hint_level（≤3），返回新值。"""
    conn = get_conn()
    current = conn.execute(
        "SELECT hint_level FROM exercise_bank WHERE id=?", (exercise_id,)
    ).fetchone()
    if not current:
        conn.close()
        return 0
    new_level = min(3, current["hint_level"] + 1)
    conn.execute(
        "UPDATE exercise_bank SET hint_level=? WHERE id=?", (new_level, exercise_id)
    )
    conn.commit()
    conn.close()
    return new_level


def report_error(exercise_id: str):
    """学生纠错 → quality_score -1。"""
    conn = get_conn()
    conn.execute(
        "UPDATE exercise_bank SET quality_score = quality_score - 1 WHERE id=?",
        (exercise_id,),
    )
    conn.commit()
    conn.close()


def get_user_exercise_states(
    user_id: str,
    exercise_ids: list[str],
    *,
    conn=None,
) -> dict[str, dict]:
    if not exercise_ids:
        return {}
    owns_conn = conn is None
    conn = conn or get_conn()
    placeholders = ",".join("?" for _ in exercise_ids)
    rows = conn.execute(
        f"SELECT * FROM exercise_user_state WHERE user_id=? AND exercise_id IN ({placeholders})",
        [user_id, *exercise_ids],
    ).fetchall()
    if owns_conn:
        conn.close()
    return {row["exercise_id"]: dict(row) for row in rows}


def get_user_exercise_state(user_id: str, exercise_id: str) -> dict | None:
    return get_user_exercise_states(user_id, [exercise_id]).get(exercise_id)


def attach_user_states(exercises: list[dict], user_id: str) -> list[dict]:
    states = get_user_exercise_states(user_id, [exercise["id"] for exercise in exercises])
    return [_with_user_state(exercise, states.get(exercise["id"])) for exercise in exercises]


def increment_user_hint_level(user_id: str, exercise_id: str) -> int:
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO exercise_user_state (user_id, exercise_id, hint_level)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, exercise_id) DO UPDATE SET
                    hint_level=MIN(3, exercise_user_state.hint_level + 1),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (user_id, exercise_id),
            )
            row = conn.execute(
                "SELECT hint_level FROM exercise_user_state WHERE user_id=? AND exercise_id=?",
                (user_id, exercise_id),
            ).fetchone()
        return int(row["hint_level"])
    finally:
        conn.close()


def save_user_exercise_result(
    user_id: str,
    exercise_id: str,
    student_answer: str,
    is_correct: bool | None,
    grading_feedback: str,
    grading_status: str,
    attempt_id: str,
) -> None:
    correct_value = None if is_correct is None else (1 if is_correct else 0)
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """
                INSERT INTO exercise_user_state (
                    user_id, exercise_id, is_answered, student_answer, is_correct,
                    grading_feedback, grading_status, latest_attempt_id
                ) VALUES (?, ?, 1, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, exercise_id) DO UPDATE SET
                    is_answered=1,
                    student_answer=excluded.student_answer,
                    is_correct=excluded.is_correct,
                    grading_feedback=excluded.grading_feedback,
                    grading_status=excluded.grading_status,
                    error_analysis='{}',
                    latest_attempt_id=excluded.latest_attempt_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    user_id, exercise_id, student_answer, correct_value,
                    grading_feedback or "", grading_status, attempt_id,
                ),
            )
    finally:
        conn.close()


def save_user_error_analysis(user_id: str, exercise_id: str, error_analysis: dict | None) -> None:
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """
                UPDATE exercise_user_state
                SET error_analysis=?, updated_at=CURRENT_TIMESTAMP
                WHERE user_id=? AND exercise_id=?
                """,
                (json.dumps(error_analysis or {}, ensure_ascii=False), user_id, exercise_id),
            )
    finally:
        conn.close()


def report_user_exercise_error(user_id: str, exercise_id: str) -> bool:
    """Record one quality report per user and exercise. Return whether it was new."""
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO exercise_user_state (user_id, exercise_id)
                VALUES (?, ?)
                """,
                (user_id, exercise_id),
            )
            cursor = conn.execute(
                """
                UPDATE exercise_user_state
                SET reported_error=1, updated_at=CURRENT_TIMESTAMP
                WHERE user_id=? AND exercise_id=? AND reported_error=0
                """,
                (user_id, exercise_id),
            )
            if cursor.rowcount:
                conn.execute(
                    "UPDATE exercise_bank SET quality_score=quality_score-1 WHERE id=?",
                    (exercise_id,),
                )
        return bool(cursor.rowcount)
    finally:
        conn.close()


def _unpack(d: dict) -> dict:
    d["hints"] = json.loads(d.get("hints", "[]"))
    d["computable"] = json.loads(d.get("computable", "{}"))
    d["error_analysis"] = json.loads(d.get("error_analysis", "null")) if d.get("error_analysis") else None
    return d


def _with_user_state(exercise: dict, state: dict | None) -> dict:
    result = dict(exercise)
    result.update({
        "hint_level": 0,
        "is_answered": False,
        "student_answer": None,
        "is_correct": None,
        "grading_feedback": "",
        "grading_status": "not_submitted",
        "error_analysis": None,
    })
    if not state:
        return result
    result.update({
        "hint_level": int(state.get("hint_level") or 0),
        "is_answered": bool(state.get("is_answered")),
        "student_answer": state.get("student_answer"),
        "is_correct": None if state.get("is_correct") is None else bool(state.get("is_correct")),
        "grading_feedback": state.get("grading_feedback") or "",
        "grading_status": state.get("grading_status") or "not_submitted",
        "error_analysis": json.loads(state.get("error_analysis") or "{}") or None,
    })
    return result
