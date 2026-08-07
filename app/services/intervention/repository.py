"""SQLite persistence for the teaching-policy control plane."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from typing import Any

from app.db.connection import get_conn
from app.services.diagnosis.contracts import DiagnosticSignal


def _id() -> str:
    return str(uuid.uuid4())


def _loads(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default


def save_signals(signals: list[DiagnosticSignal]) -> list[str]:
    ids: list[str] = []
    conn = get_conn()
    try:
        with conn:
            for signal in signals:
                data = asdict(signal)
                identity = "|".join((
                    signal.source_type, signal.source_id, signal.signal_type,
                    signal.student_quote, signal.scorer_version,
                ))
                signal_id = str(uuid.uuid5(uuid.NAMESPACE_URL, identity))
                conn.execute(
                    """INSERT OR IGNORE INTO diagnostic_signals
                       (id,source_type,source_id,user_id,sequence_id,signal_type,concept_ids,
                        student_quote,confidence,strength,rationale,scorer_version)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        signal_id, signal.source_type, signal.source_id, signal.user_id,
                        signal.sequence_id, signal.signal_type,
                        json.dumps(signal.concept_ids, ensure_ascii=False), signal.student_quote,
                        signal.confidence, signal.strength, signal.rationale, signal.scorer_version,
                    ),
                )
                row = conn.execute("SELECT id FROM diagnostic_signals WHERE id=?", (signal_id,)).fetchone()
                if row:
                    ids.append(row["id"])
        return ids
    finally:
        conn.close()


def list_signals_for_source(source_type: str, source_id: str) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM diagnostic_signals WHERE source_type=? AND source_id=? ORDER BY created_at",
            (source_type, source_id),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["concept_ids"] = _loads(item.get("concept_ids"), [])
            result.append(item)
        return result
    finally:
        conn.close()


def create_snapshot(*, user_id: str, source_type: str, source_id: str,
                    tree_id: str = "", node_id: str = "", textbook_id: str = "",
                    sequence_id: str = "", concept_ids: list[str] | None = None,
                    state_payload: dict | None = None, signal_ids: list[str] | None = None) -> dict:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing = conn.execute(
            "SELECT * FROM diagnosis_snapshots WHERE source_type=? AND source_id=?",
            (source_type, source_id),
        ).fetchone()
        if existing:
            conn.commit()
            return unpack_snapshot(existing)
        row = conn.execute(
            "SELECT COALESCE(MAX(version),0) AS version FROM diagnosis_snapshots WHERE user_id=?",
            (user_id,),
        ).fetchone()
        snapshot_id = _id()
        conn.execute(
            """INSERT INTO diagnosis_snapshots
               (id,user_id,source_type,source_id,tree_id,node_id,textbook_id,sequence_id,
                concept_ids,state_payload,signal_ids,version)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                snapshot_id, user_id, source_type, source_id, tree_id, node_id,
                textbook_id, sequence_id,
                json.dumps(concept_ids or [], ensure_ascii=False),
                json.dumps(state_payload or {}, ensure_ascii=False),
                json.dumps(signal_ids or [], ensure_ascii=False), int(row["version"]) + 1,
            ),
        )
        conn.execute(
            """INSERT OR IGNORE INTO intervention_agent_jobs
               (id,snapshot_id,user_id,payload) VALUES (?,?,?,?)""",
            (_id(), snapshot_id, user_id, json.dumps({"snapshot_id": snapshot_id})),
        )
        conn.commit()
        return unpack_snapshot(conn.execute("SELECT * FROM diagnosis_snapshots WHERE id=?", (snapshot_id,)).fetchone())
    finally:
        conn.close()


def get_snapshot(snapshot_id: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM diagnosis_snapshots WHERE id=?", (snapshot_id,)).fetchone()
        return unpack_snapshot(row) if row else None
    finally:
        conn.close()


def latest_snapshot(user_id: str, *, tree_id: str = "", node_id: str = "",
                    sequence_id: str = "", concept_ids: list[str] | None = None) -> dict | None:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM diagnosis_snapshots WHERE user_id=? ORDER BY version DESC LIMIT 50",
            (user_id,),
        ).fetchall()
        requested = set(concept_ids or [])
        for row in rows:
            item = unpack_snapshot(row)
            if tree_id and item["tree_id"] and item["tree_id"] != tree_id:
                continue
            if node_id and item["node_id"] and item["node_id"] != node_id:
                continue
            if sequence_id and item["sequence_id"] and item["sequence_id"] != sequence_id:
                continue
            existing = set(item["concept_ids"])
            if requested and existing and requested.isdisjoint(existing):
                continue
            return item
        return None
    finally:
        conn.close()


def unpack_snapshot(row) -> dict:
    result = dict(row)
    result["concept_ids"] = _loads(result.get("concept_ids"), [])
    result["state_payload"] = _loads(result.get("state_payload"), {})
    result["signal_ids"] = _loads(result.get("signal_ids"), [])
    result["signals"] = list_signals_for_source(result["source_type"], result["source_id"])
    return result


def create_directive(*, snapshot: dict, action: str, teaching_goal: str,
                     qa_policy: dict, evidence_refs: list[str], confidence: float,
                     model_name: str, prompt_version: str, status: str) -> dict:
    directive_id = _id()
    context_version = f"{snapshot['id']}:{snapshot['version']}"
    conn = get_conn()
    try:
        with conn:
            conn.execute(
                """UPDATE tutor_directives SET status='expired',updated_at=CURRENT_TIMESTAMP
                   WHERE user_id=? AND tree_id=? AND node_id=? AND status='active'""",
                (snapshot["user_id"], snapshot.get("tree_id", ""), snapshot.get("node_id", "")),
            )
            conn.execute(
                """INSERT INTO tutor_directives
                   (id,user_id,snapshot_id,source_turn_id,tree_id,node_id,sequence_id,concept_ids,
                    teaching_goal,qa_policy,action,evidence_refs,confidence,status,context_version,
                    model_name,prompt_version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    directive_id, snapshot["user_id"], snapshot["id"],
                    snapshot["source_id"] if snapshot["source_type"] == "qa_turn" else "",
                    snapshot.get("tree_id", ""), snapshot.get("node_id", ""),
                    snapshot.get("sequence_id", ""), json.dumps(snapshot.get("concept_ids", []), ensure_ascii=False),
                    teaching_goal, json.dumps(qa_policy, ensure_ascii=False), action,
                    json.dumps(evidence_refs, ensure_ascii=False), confidence, status,
                    context_version, model_name, prompt_version,
                ),
            )
        return get_directive(directive_id)
    finally:
        conn.close()


def get_directive(directive_id: str) -> dict | None:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM tutor_directives WHERE id=?", (directive_id,)).fetchone()
        return unpack_directive(row) if row else None
    finally:
        conn.close()


def get_active_directive(user_id: str, *, tree_id: str = "", node_id: str = "",
                         sequence_id: str = "", concept_ids: list[str] | None = None) -> dict | None:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM tutor_directives WHERE user_id=? AND status='active'
               ORDER BY created_at DESC LIMIT 20""",
            (user_id,),
        ).fetchall()
        requested = set(concept_ids or [])
        for row in rows:
            item = unpack_directive(row)
            valid = not (
                (tree_id and item["tree_id"] and item["tree_id"] != tree_id)
                or (node_id and item["node_id"] and item["node_id"] != node_id)
                or (sequence_id and item["sequence_id"] and item["sequence_id"] != sequence_id)
                or (requested and item["concept_ids"] and requested.isdisjoint(item["concept_ids"]))
            )
            if valid:
                return item
            conn.execute(
                "UPDATE tutor_directives SET status='stale',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (item["id"],),
            )
            conn.execute(
                """UPDATE intervention_actions SET status='stale',updated_at=CURRENT_TIMESTAMP
                   WHERE directive_id=? AND status IN ('queued','running','ready')""",
                (item["id"],),
            )
            conn.execute(
                """UPDATE practice_drafts SET status='stale',updated_at=CURRENT_TIMESTAMP
                   WHERE intervention_action_id IN (
                       SELECT id FROM intervention_actions WHERE directive_id=?
                   ) AND status IN ('queued','running','ready','partial')""",
                (item["id"],),
            )
            conn.execute(
                """UPDATE exercise_agent_jobs SET status='cancelled',worker_id=NULL,lease_until=NULL,
                   updated_at=CURRENT_TIMESTAMP WHERE draft_id IN (
                       SELECT draft_id FROM intervention_actions
                       WHERE directive_id=? AND draft_id IS NOT NULL
                   ) AND status IN ('queued','running')""",
                (item["id"],),
            )
        conn.commit()
        return None
    finally:
        conn.close()


def unpack_directive(row) -> dict:
    result = dict(row)
    result["concept_ids"] = _loads(result.get("concept_ids"), [])
    result["qa_policy"] = _loads(result.get("qa_policy"), {})
    result["evidence_refs"] = _loads(result.get("evidence_refs"), [])
    return result


def mark_directive_applied(directive_id: str, turn_id: str) -> None:
    if not directive_id:
        return
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE tutor_directives SET status='applied',applied_turn_id=?,updated_at=CURRENT_TIMESTAMP
               WHERE id=? AND status='active'""",
            (turn_id, directive_id),
        )
        conn.commit()
    finally:
        conn.close()


def create_action(*, user_id: str, turn_id: str, node_id: str, action_type: str,
                  trigger_kind: str, payload: dict, directive_id: str = "") -> dict:
    conn = get_conn()
    try:
        existing = conn.execute(
            """SELECT * FROM intervention_actions WHERE user_id=? AND turn_id=?
               AND action_type=? AND trigger_kind=? AND status NOT IN ('failed','stale','cancelled')
               ORDER BY created_at DESC LIMIT 1""",
            (user_id, turn_id, action_type, trigger_kind),
        ).fetchone()
        if existing:
            return unpack_action(existing)
        action_id = _id()
        conn.execute(
            """INSERT INTO intervention_actions
               (id,user_id,directive_id,turn_id,node_id,action_type,trigger_kind,payload)
               VALUES (?,?,?,?,?,?,?,?)""",
            (action_id, user_id, directive_id or None, turn_id, node_id, action_type,
             trigger_kind, json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
        return unpack_action(conn.execute("SELECT * FROM intervention_actions WHERE id=?", (action_id,)).fetchone())
    finally:
        conn.close()


def update_action(action_id: str, *, status: str, draft_id: str | None = None,
                  error: str | None = None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE intervention_actions SET status=?,draft_id=COALESCE(?,draft_id),error=?,
               updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (status, draft_id, error, action_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_actions_for_turn(user_id: str, turn_id: str) -> list[dict]:
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM intervention_actions WHERE user_id=? AND turn_id=? ORDER BY created_at",
            (user_id, turn_id),
        ).fetchall()
        return [unpack_action(row) for row in rows]
    finally:
        conn.close()


def get_planning_status_for_turn(user_id: str, turn_id: str) -> dict | None:
    """Return the durable controller job for a QA turn, if diagnosis published it."""

    conn = get_conn()
    try:
        row = conn.execute(
            """SELECT j.status,j.error,j.attempts,j.updated_at
               FROM diagnosis_snapshots s
               JOIN intervention_agent_jobs j ON j.snapshot_id=s.id
               WHERE s.user_id=? AND s.source_type='qa_turn' AND s.source_id=?
               ORDER BY s.version DESC LIMIT 1""",
            (user_id, turn_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def unpack_action(row) -> dict:
    result = dict(row)
    result["payload"] = _loads(result.get("payload"), {})
    return result


def list_recoverable_job_ids(limit: int = 100) -> list[str]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """SELECT id FROM intervention_agent_jobs WHERE status='queued'
               OR (status='running' AND (lease_until IS NULL OR lease_until<CURRENT_TIMESTAMP))
               ORDER BY created_at LIMIT ?""",
            (limit,),
        ).fetchall()
        return [row["id"] for row in rows]
    finally:
        conn.close()


def get_job_id_for_snapshot(snapshot_id: str) -> str | None:
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT id FROM intervention_agent_jobs WHERE snapshot_id=?", (snapshot_id,)
        ).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def claim_job(job_id: str, worker_id: str, lease_minutes: int = 10) -> dict | None:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            f"""UPDATE intervention_agent_jobs SET status='running',worker_id=?,
                lease_until=datetime('now','+{max(1, int(lease_minutes))} minutes'),
                attempts=attempts+1,updated_at=CURRENT_TIMESTAMP
                WHERE id=? AND (status='queued' OR lease_until IS NULL OR lease_until<CURRENT_TIMESTAMP)""",
            (worker_id, job_id),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return None
        row = conn.execute("SELECT * FROM intervention_agent_jobs WHERE id=?", (job_id,)).fetchone()
        conn.commit()
        result = dict(row)
        result["payload"] = _loads(result.get("payload"), {})
        return result
    finally:
        conn.close()


def finish_job(job_id: str, worker_id: str, *, status: str,
               result: dict | None = None, error: str | None = None) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE intervention_agent_jobs SET status=?,result=?,error=?,worker_id=NULL,
               lease_until=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=? AND worker_id=?""",
            (status, json.dumps(result or {}, ensure_ascii=False), error, job_id, worker_id),
        )
        conn.commit()
    finally:
        conn.close()


def release_worker_claims(worker_id: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE intervention_agent_jobs SET status='queued',worker_id=NULL,lease_until=NULL,
               updated_at=CURRENT_TIMESTAMP WHERE worker_id=? AND status='running'""",
            (worker_id,),
        )
        conn.commit()
    finally:
        conn.close()


def get_preferences(user_id: str) -> dict:
    conn = get_conn()
    try:
        row = conn.execute("SELECT learning_preferences FROM user_profiles WHERE user_id=?", (user_id,)).fetchone()
        return _loads(row["learning_preferences"], {}) if row else {}
    finally:
        conn.close()


def update_preferences(user_id: str, values: dict) -> dict:
    current = get_preferences(user_id)
    current.update(values)
    conn = get_conn()
    try:
        conn.execute(
            """INSERT INTO user_profiles (user_id,learning_preferences,updated_at)
               VALUES (?,?,CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET learning_preferences=excluded.learning_preferences,
               updated_at=CURRENT_TIMESTAMP""",
            (user_id, json.dumps(current, ensure_ascii=False)),
        )
        conn.commit()
        return current
    finally:
        conn.close()
