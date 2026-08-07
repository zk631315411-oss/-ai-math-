"""SQLite persistence for practice v2.

The repository deliberately keeps item content immutable. User state is stored
on sessions and attempts so a generated item can be reused without leaking a
different user's answer.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from app.db.connection import get_conn
from app.textbooks import canonical_textbook_id


def _id() -> str:
    return str(uuid.uuid4())


def _loads(value: Any, default: Any):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def context_hash(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_draft(*, user_id: str, context: dict[str, Any], trigger_kind: str,
                 intervention_goal: str, evidence_quote: str,
                 auto_prepared: bool = True, parent_draft_id: str | None = None) -> dict:
    snapshot = dict(context)
    snapshot["textbook_id"] = canonical_textbook_id(snapshot.get("textbook_id", ""))
    snapshot["evidence_quote"] = evidence_quote
    snapshot["intervention_goal"] = intervention_goal
    digest = context_hash(snapshot)
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            """SELECT * FROM practice_drafts
               WHERE user_id=? AND turn_id=? AND context_hash=? AND status NOT IN ('stale','cancelled','failed')
               ORDER BY version DESC LIMIT 1""",
            (user_id, snapshot.get("turn_id", ""), digest),
        ).fetchone()
        if existing:
            conn.commit()
            return unpack_draft(existing)
        draft_id = _id()
        if parent_draft_id:
            parent = conn.execute(
                "SELECT version FROM practice_drafts WHERE id=? AND user_id=?",
                (parent_draft_id, user_id),
            ).fetchone()
            version = int(parent["version"]) + 1 if parent else 1
        else:
            row = conn.execute(
                "SELECT COALESCE(MAX(version),0) AS version FROM practice_drafts WHERE user_id=? AND turn_id=?",
                (user_id, snapshot.get("turn_id", "")),
            ).fetchone()
            version = int(row["version"]) + 1
        conn.execute(
            """INSERT INTO practice_drafts
               (id,user_id,turn_id,tree_id,node_id,textbook_id,sequence_id,concept_ids,
                trigger_kind,intervention_goal,evidence_quote,selection_reason,
                context_snapshot,context_hash,status,auto_prepared,version,parent_draft_id)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (draft_id, user_id, snapshot.get("turn_id", ""), snapshot.get("tree_id", ""),
             snapshot.get("node_id", ""), snapshot.get("textbook_id", ""), snapshot.get("sequence_id", ""),
             json.dumps(snapshot.get("concept_ids", []), ensure_ascii=False), trigger_kind,
             intervention_goal, evidence_quote, "", json.dumps(snapshot, ensure_ascii=False), digest,
             "queued", 1 if auto_prepared else 0, version, parent_draft_id),
        )
        conn.execute(
            "INSERT INTO exercise_agent_jobs (id,draft_id,task_kind,payload) VALUES (?,?,?,?)",
            (_id(), draft_id, "plan", json.dumps({"context": snapshot}, ensure_ascii=False)),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM practice_drafts WHERE id=?", (draft_id,)).fetchone()
        return unpack_draft(row)
    finally:
        conn.close()


def get_draft(draft_id: str, user_id: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM practice_drafts WHERE id=? AND user_id=?", (draft_id, user_id)).fetchone()
        return unpack_draft(row) if row else None
    finally:
        conn.close()


def update_draft(draft_id: str, **values) -> None:
    if not values:
        return
    allowed = {"status", "selection_reason", "error"}
    values = {key: value for key, value in values.items() if key in allowed}
    if not values:
        return
    values["updated_at"] = "CURRENT_TIMESTAMP"
    assignments = []
    params = []
    for key, value in values.items():
        if value == "CURRENT_TIMESTAMP":
            assignments.append(f"{key}=CURRENT_TIMESTAMP")
        else:
            assignments.append(f"{key}=?")
            params.append(value)
    params.append(draft_id)
    conn = get_conn()
    try:
        conn.execute(f"UPDATE practice_drafts SET {', '.join(assignments)} WHERE id=?", params)
        conn.commit()
    finally:
        conn.close()


def mark_stale_for_context(*, user_id: str, tree_id: str, node_id: str,
                           concept_ids: list[str]) -> int:
    """Invalidate recommendations that no longer belong to the active branch.

    A draft on the same node remains valid when its knowledge scope overlaps;
    drafts on another branch, or a disjoint scope on the same branch, become
    stale but remain queryable for audit.
    """
    if not tree_id:
        return 0
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id,node_id,concept_ids FROM practice_drafts
               WHERE user_id=? AND tree_id=? AND status IN ('queued','running','ready','partial')""",
            (user_id, tree_id),
        ).fetchall()
        current = set(concept_ids)
        stale_ids = []
        for row in rows:
            previous = set(_loads(row["concept_ids"], []))
            if row["node_id"] != node_id or (current and previous and current.isdisjoint(previous)):
                stale_ids.append(row["id"])
        if stale_ids:
            placeholders = ",".join("?" for _ in stale_ids)
            conn.execute(
                f"""UPDATE practice_drafts SET status='stale',updated_at=CURRENT_TIMESTAMP
                    WHERE id IN ({placeholders})""",
                stale_ids,
            )
            conn.execute(
                f"""UPDATE exercise_agent_jobs SET status='cancelled',worker_id=NULL,lease_until=NULL,
                    updated_at=CURRENT_TIMESTAMP WHERE draft_id IN ({placeholders})
                    AND status IN ('queued','running')""",
                stale_ids,
            )
            conn.commit()
        return len(stale_ids)
    finally:
        conn.close()


def list_recoverable_draft_ids(limit: int = 100) -> list[str]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT p.id FROM practice_drafts p
               JOIN exercise_agent_jobs j ON j.draft_id=p.id AND j.task_kind='plan'
               WHERE p.status='queued'
                  OR (p.status='running' AND (j.lease_until IS NULL OR j.lease_until<CURRENT_TIMESTAMP))
               ORDER BY p.created_at LIMIT ?""",
            (limit,),
        ).fetchall()
        return [row["id"] for row in rows]
    finally:
        conn.close()


def claim_draft(draft_id: str, worker_id: str, lease_minutes: int = 15) -> dict | None:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        job = conn.execute(
            """SELECT id FROM exercise_agent_jobs
               WHERE draft_id=? AND task_kind='plan' AND branch_role=''
                 AND (status='queued' OR (status='running' AND (lease_until IS NULL OR lease_until<CURRENT_TIMESTAMP)))
               ORDER BY created_at LIMIT 1""",
            (draft_id,),
        ).fetchone()
        if not job:
            conn.rollback()
            return None
        cursor = conn.execute(
            f"""UPDATE exercise_agent_jobs SET status='running',worker_id=?,
                lease_until=datetime('now','+{max(1, int(lease_minutes))} minutes'),
                attempts=attempts+1,updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND (status='queued' OR lease_until IS NULL OR lease_until<CURRENT_TIMESTAMP)""",
            (worker_id, job["id"]),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return None
        conn.execute(
            "UPDATE practice_drafts SET status='running',updated_at=CURRENT_TIMESTAMP WHERE id=? AND status IN ('queued','running')",
            (draft_id,),
        )
        row = conn.execute("SELECT * FROM practice_drafts WHERE id=?", (draft_id,)).fetchone()
        conn.commit()
        return unpack_draft(row) if row else None
    finally:
        conn.close()


def finish_claim(draft_id: str, worker_id: str, *, status: str,
                 error: str | None = None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE exercise_agent_jobs SET status=?,worker_id=NULL,lease_until=NULL,error=?,
               updated_at=CURRENT_TIMESTAMP WHERE draft_id=? AND task_kind='plan' AND worker_id=?""",
            (status, error, draft_id, worker_id),
        )
        conn.commit()
    finally:
        conn.close()


def release_worker_claims(worker_id: str) -> None:
    """Return in-flight work to the durable queue during graceful shutdown."""
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            "SELECT draft_id FROM exercise_agent_jobs WHERE worker_id=? AND status='running'",
            (worker_id,),
        ).fetchall()
        if rows:
            ids = [row["draft_id"] for row in rows]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"UPDATE exercise_agent_jobs SET status='queued',worker_id=NULL,lease_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE worker_id=? AND status='running'",
                (worker_id,),
            )
            conn.execute(
                f"UPDATE practice_drafts SET status='queued',updated_at=CURRENT_TIMESTAMP WHERE id IN ({placeholders}) AND status='running'",
                ids,
            )
        conn.commit()
    finally:
        conn.close()


def get_draft_internal(draft_id: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM practice_drafts WHERE id=?", (draft_id,)).fetchone()
        return unpack_draft(row) if row else None
    finally:
        conn.close()


def update_job(draft_id: str, task_kind: str, *, status: str, result: dict | None = None,
               error: str | None = None, branch_role: str = "") -> None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM exercise_agent_jobs WHERE draft_id=? AND task_kind=? AND branch_role=? ORDER BY created_at DESC LIMIT 1",
            (draft_id, task_kind, branch_role),
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE exercise_agent_jobs SET status=?, result=?, error=?, attempts=attempts+1,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (status, json.dumps(result or {}, ensure_ascii=False), error, row["id"]),
            )
        else:
            conn.execute(
                """INSERT INTO exercise_agent_jobs
                   (id,draft_id,task_kind,branch_role,status,result,attempts,error)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (_id(), draft_id, task_kind, branch_role, status,
                 json.dumps(result or {}, ensure_ascii=False), 1, error),
            )
        conn.commit()
    finally:
        conn.close()


def add_item(item: dict) -> str:
    item_id = item.get("id") or _id()
    textbook_id = canonical_textbook_id(item.get("textbook_id", ""))
    conn = get_conn()
    try:
        conn.execute(
            """INSERT OR IGNORE INTO exercise_items
               (id,textbook_id,source_locator,sequence_id,concept_ids,question_type,target_stage,
                difficulty,question,answer_spec,hints,rubric,source,trust_status,owner_user_id,
                generation_model,reviewer_model,prompt_version,context_hash,item_kind,concept_names,
                prerequisite_concept_ids,prerequisite_concept_names,primary_concept_id,
                primary_concept_name,secondary_concept_ids,stage_rationale,literacy_tags,stem_source,
                solution_source,solution_review_status,source_hash,parent_item_id,source_asset_id,
                original_textbook_name,source_page,source_problem_no,source_subitem_no,
                stem_review_status,review_status,diagnostic_goal,kg_mapping_status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (item_id, textbook_id, item.get("source_locator", ""), item.get("sequence_id", ""),
             json.dumps(item.get("concept_ids", []), ensure_ascii=False), item.get("question_type", "concept"),
             int(item.get("target_stage") or 1), item.get("difficulty", "basic"), item["question"],
             json.dumps(item.get("answer_spec", {}), ensure_ascii=False), json.dumps(item.get("hints", []), ensure_ascii=False),
             json.dumps(item.get("rubric", []), ensure_ascii=False), item.get("source", "llm"),
             item.get("trust_status", "machine_reviewed"), item.get("owner_user_id"), item.get("generation_model", ""),
             item.get("reviewer_model", ""), item.get("prompt_version", ""), item.get("context_hash", ""),
             item.get("item_kind", "exercise_item"), json.dumps(item.get("concept_names", []), ensure_ascii=False),
             json.dumps(item.get("prerequisite_concept_ids", []), ensure_ascii=False),
             json.dumps(item.get("prerequisite_concept_names", []), ensure_ascii=False),
             item.get("primary_concept_id", (item.get("concept_ids") or [""])[0]),
             item.get("primary_concept_name", (item.get("concept_names") or [""])[0]),
             json.dumps(item.get("secondary_concept_ids", []), ensure_ascii=False),
             item.get("stage_rationale", ""), json.dumps(item.get("literacy_tags", []), ensure_ascii=False),
             item.get("stem_source", item.get("source", "textbook")), item.get("solution_source", "textbook"),
             item.get("solution_review_status", "reviewed" if item.get("trust_status") in {"teacher_approved", "machine_verified"} else "unreviewed"),
             item.get("source_hash", ""), item.get("parent_item_id"), item.get("source_asset_id", ""),
             item.get("original_textbook_name", ""), item.get("source_page"),
             item.get("source_problem_no", ""), item.get("source_subitem_no"),
             item.get("stem_review_status", "unreviewed"),
             item.get("review_status", "draft_subject_review"),
             item.get("diagnostic_goal", "application"),
             item.get("kg_mapping_status", "unverified")),
        )
        conn.commit()
        return item_id
    finally:
        conn.close()


def list_items(*, textbook_id: str, sequence_id: str, concept_ids: list[str],
               user_id: str = "", include_machine: bool = True, limit: int = 50,
               item_kind: str = "exercise_item", exclude_ids: set[str] | None = None) -> list[dict]:
    textbook_id = canonical_textbook_id(textbook_id)
    conn = get_conn()
    try:
        clauses = ["textbook_id=?", "item_kind=?", "kg_mapping_status='verified'",
                   "review_status='approved'", "solution_review_status IN ('reviewed','teacher_approved')",
                   "(trust_status='teacher_approved' OR (trust_status='machine_verified' AND source='textbook')" \
                   " OR (trust_status='machine_reviewed' AND owner_user_id=?))"]
        params: list[Any] = [textbook_id, item_kind, user_id]
        if not include_machine:
            clauses[-1] = "trust_status='teacher_approved'"
            params = [textbook_id, item_kind]
        if sequence_id:
            clauses.append("(sequence_id=? OR sequence_id='')")
            params.append(sequence_id)
        if exclude_ids:
            placeholders = ",".join("?" for _ in exclude_ids)
            clauses.append(f"id NOT IN ({placeholders})")
            params.extend(sorted(exclude_ids))
        rows = conn.execute(
            f"SELECT * FROM exercise_items WHERE {' AND '.join(clauses)} ORDER BY created_at, id LIMIT ?",
            [*params, limit],
        ).fetchall()
        result = [unpack_item(row) for row in rows]
        if concept_ids:
            matching = [item for item in result if set(item["concept_ids"]) & set(concept_ids)]
            if matching:
                result = matching
            result.sort(key=lambda item: 0 if set(item["concept_ids"]) & set(concept_ids) else 1)
        return result
    finally:
        conn.close()


def attach_draft_item(draft_id: str, item_id: str, role: str, rank: int, reason: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO practice_draft_items (draft_id,item_id,branch_role,rank,reason) VALUES (?,?,?,?,?)",
            (draft_id, item_id, role, rank, reason),
        )
        conn.commit()
    finally:
        conn.close()


def list_draft_items(draft_id: str, user_id: str) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT i.*, d.branch_role, d.rank, d.reason FROM practice_draft_items d
               JOIN exercise_items i ON i.id=d.item_id JOIN practice_drafts p ON p.id=d.draft_id
               WHERE d.draft_id=? AND p.user_id=? ORDER BY d.rank, d.branch_role""",
            (draft_id, user_id),
        ).fetchall()
        return [unpack_item(row) | {"branch_role": row["branch_role"], "rank": row["rank"], "reason": row["reason"]} for row in rows]
    finally:
        conn.close()


def create_session(draft_id: str, user_id: str, first_item_id: str | None,
                   selection_decision: dict | None = None,
                   *, status: str = "active", outcome_status: str = "undetermined") -> dict:
    session_id = _id()
    conn = get_conn()
    try:
        count = conn.execute("SELECT COUNT(*) FROM practice_draft_items WHERE draft_id=?", (draft_id,)).fetchone()[0]
        conn.execute(
            """INSERT INTO practice_sessions
               (id,draft_id,user_id,current_item_id,item_count,status,outcome_status,selection_decision)
               VALUES (?,?,?,?,?,?,?,?)""",
            (session_id, draft_id, user_id, first_item_id, count,
             status, outcome_status, json.dumps(selection_decision or {}, ensure_ascii=False)),
        )
        conn.commit()
        return {"id": session_id, "draft_id": draft_id, "current_item_id": first_item_id,
                "item_count": count, "completed_count": 0, "status": status,
                "selection_decision": selection_decision or {}, "outcome_status": outcome_status,
                "mastery_verified": False, "ungradable_retries": 0}
    finally:
        conn.close()


def get_session(session_id: str, user_id: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM practice_sessions WHERE id=? AND user_id=?", (session_id, user_id)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["summary"] = _loads(result.get("summary"), {})
        result["selection_decision"] = _loads(result.get("selection_decision"), {})
        result["mastery_verified"] = bool(result.get("mastery_verified"))
        return result
    finally:
        conn.close()


def get_item(item_id: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM exercise_items WHERE id=?", (item_id,)).fetchone()
        return unpack_item(row) if row else None
    finally:
        conn.close()


def get_attempted_item_ids(session_id: str, user_id: str) -> set[str]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT item_id FROM practice_attempts WHERE session_id=? AND user_id=?",
            (session_id, user_id),
        ).fetchall()
        return {row["item_id"] for row in rows}
    finally:
        conn.close()


def get_hint_level(session_id: str, item_id: str, user_id: str) -> int:
    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT MAX(hint_level) AS level FROM practice_hint_events
               WHERE session_id=? AND item_id=? AND user_id=?""",
            (session_id, item_id, user_id),
        ).fetchone()
        return int((row and row["level"]) or 0)
    finally:
        conn.close()


def record_hint(session: dict, item: dict, level: int) -> None:
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO practice_hint_events (id,session_id,item_id,user_id,hint_level) VALUES (?,?,?,?,?)",
            (_id(), session["id"], item["id"], session["user_id"], level),
        )
        conn.commit()
    finally:
        conn.close()


def save_attempt(*, session: dict, item: dict, answer: str, grade: dict, hint_level: int,
                 next_item_id: str | None, next_reason: str,
                 selection_decision: dict | None = None,
                 counts_toward_limit: bool = True,
                 outcome_status: str = "undetermined",
                 mastery_verified: bool = False,
                 ungradable_retries: int | None = None) -> dict:
    attempt_id = _id()
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        current = conn.execute(
            "SELECT current_item_id,completed_count,status,summary FROM practice_sessions WHERE id=? AND user_id=?",
            (session["id"], session["user_id"]),
        ).fetchone()
        if (not current or current["status"] != "active"
                or current["current_item_id"] != item["id"]
                or int(current["completed_count"]) != int(session.get("completed_count") or 0)):
            conn.rollback()
            raise ValueError("该题已提交或练习会话已发生变化")
        conn.execute(
            """INSERT INTO practice_attempts
               (id,session_id,draft_id,item_id,user_id,student_answer,verdict,evidence_quotes,
               rubric_findings,feedback,error_analysis,hint_level,next_item_id,next_reason,
               counts_toward_limit,selection_decision)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (attempt_id, session["id"], session["draft_id"], item["id"], session["user_id"], answer,
             grade["verdict"], json.dumps(grade.get("evidence_quotes", []), ensure_ascii=False),
             json.dumps(grade.get("rubric_findings", []), ensure_ascii=False), grade.get("feedback", ""),
             json.dumps(grade.get("error_analysis", {}), ensure_ascii=False), hint_level, next_item_id,
             next_reason, 1 if counts_toward_limit else 0,
             json.dumps(selection_decision or {}, ensure_ascii=False)),
        )
        prior_completed = int(session.get("completed_count") or 0)
        completed = prior_completed + (1 if counts_toward_limit else 0)
        status = ("inconclusive" if outcome_status == "inconclusive"
                  else "completed" if (not next_item_id and counts_toward_limit) or completed >= 3
                  else "active")
        summary = _loads(current["summary"], {}) or {}
        verdict_counts = summary.get("verdict_counts") or {
            "correct": 0, "partial": 0, "incorrect": 0, "ungradable": 0,
        }
        verdict_counts[grade["verdict"]] = int(verdict_counts.get(grade["verdict"], 0)) + 1
        summary.update({
            "last_verdict": grade["verdict"],
            "hint_level": hint_level,
            "hints_used": int(summary.get("hints_used") or 0) + (1 if hint_level else 0),
            "verdict_counts": verdict_counts,
            "outcome_status": outcome_status,
            "mastery_verified": bool(mastery_verified),
        })
        retries = (int(session.get("ungradable_retries") or 0) + 1
                   if grade["verdict"] == "ungradable" else 0)
        if ungradable_retries is not None:
            retries = int(ungradable_retries)
        cursor = conn.execute(
            """UPDATE practice_sessions SET current_item_id=?, completed_count=?, status=?, summary=?,
               outcome_status=?, mastery_verified=?, ungradable_retries=?, selection_decision=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=? AND user_id=? AND status='active'
               AND current_item_id=? AND completed_count=?""",
            (next_item_id, completed, status, json.dumps(summary, ensure_ascii=False), outcome_status,
             1 if mastery_verified else 0, retries,
             json.dumps(selection_decision or {}, ensure_ascii=False), session["id"], session["user_id"],
             item["id"], int(session.get("completed_count") or 0)),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            raise ValueError("该题已提交或练习会话已发生变化")
        conn.commit()
        return {"attempt_id": attempt_id, "completed_count": completed, "status": status, "summary": summary}
    finally:
        conn.close()


def _unpack_json_fields(result: dict, fields: tuple[str, ...]) -> dict:
    list_fields = {
        "concept_ids", "concept_names", "prerequisite_concept_ids",
        "prerequisite_concept_names", "secondary_concept_ids", "literacy_tags",
        "hints", "rubric", "diagnostic_goal",
    }
    for field in fields:
        result[field] = _loads(result.get(field), [] if field in list_fields else {})
    return result


def unpack_item(row) -> dict:
    result = dict(row)
    return _unpack_json_fields(result, ("concept_ids", "concept_names", "prerequisite_concept_ids",
                                        "prerequisite_concept_names", "secondary_concept_ids",
                                        "literacy_tags", "answer_spec", "hints", "rubric"))


def unpack_draft(row) -> dict:
    result = dict(row)
    result["concept_ids"] = _loads(result.get("concept_ids"), [])
    result["context_snapshot"] = _loads(result.get("context_snapshot"), {})
    result["auto_prepared"] = bool(result.get("auto_prepared"))
    return result
