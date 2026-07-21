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


def list_by_sequence_id(sequence_id: str, max_stage: int = 5, limit: int = 5) -> list[dict]:
    """按 section + 难度筛选练习题（用于按页出题）。"""
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM exercise_bank
           WHERE sequence_id=? AND target_stage <= ? AND source='textbook'
           ORDER BY target_stage ASC LIMIT ?""",
        (sequence_id, max_stage, limit),
    ).fetchall()
    conn.close()
    return [_unpack(dict(r)) for r in rows]


def submit_answer(exercise_id: str, student_answer: str) -> int:
    """更新学生答案（允许多次提交）。"""
    conn = get_conn()
    cursor = conn.execute(
        """UPDATE exercise_bank
           SET is_answered = 1, student_answer = ?
           WHERE id = ?""",
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


def _unpack(d: dict) -> dict:
    d["hints"] = json.loads(d.get("hints", "[]"))
    d["computable"] = json.loads(d.get("computable", "{}"))
    d["error_analysis"] = json.loads(d.get("error_analysis", "null")) if d.get("error_analysis") else None
    return d
