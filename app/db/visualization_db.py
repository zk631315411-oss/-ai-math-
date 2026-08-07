"""Persistence for structured math visualizations and animation jobs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any, Iterable

from app.db.connection import get_conn


def init_visualization_schema(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS math_visualizations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            turn_id TEXT,
            assistant_message_id TEXT,
            chat_history_id TEXT,
            version INTEGER NOT NULL DEFAULT 1,
            kind TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            spec_json TEXT NOT NULL,
            animation_recipe_json TEXT,
            animation_status TEXT NOT NULL DEFAULT 'not_requested',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_math_visualizations_turn
            ON math_visualizations(turn_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_math_visualizations_message
            ON math_visualizations(assistant_message_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_math_visualizations_chat
            ON math_visualizations(chat_history_id, created_at);

        CREATE TABLE IF NOT EXISTS animation_jobs (
            id TEXT PRIMARY KEY,
            visualization_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            rq_job_id TEXT,
            status TEXT NOT NULL DEFAULT 'queued',
            error TEXT NOT NULL DEFAULT '',
            video_key TEXT,
            poster_key TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY(visualization_id) REFERENCES math_visualizations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_animation_jobs_visualization
            ON animation_jobs(visualization_id, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS uq_animation_jobs_active
            ON animation_jobs(visualization_id)
            WHERE status IN ('queued','running','completed');
        """
    )


def save_visualization(
    artifact: dict[str, Any],
    *,
    user_id: str,
    turn_id: str | None,
    chat_history_id: str | None,
) -> dict[str, Any]:
    conn = get_conn()
    try:
        init_visualization_schema(conn)
        conn.execute(
            """INSERT OR IGNORE INTO math_visualizations(
                   id,user_id,turn_id,chat_history_id,version,kind,title,spec_json,
                   animation_recipe_json,animation_status
               ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (
                artifact["id"], user_id, turn_id, chat_history_id,
                int(artifact.get("version", 1)), artifact["kind"], artifact.get("title", ""),
                json.dumps(artifact.get("spec") or {}, ensure_ascii=False, allow_nan=False),
                json.dumps(artifact.get("_animation_recipe"), ensure_ascii=False, allow_nan=False)
                if artifact.get("_animation_recipe") else None,
                artifact.get("animation_status", "not_requested"),
            ),
        )
        conn.commit()
        return get_visualization(artifact["id"], user_id)
    finally:
        conn.close()


def attach_turn_visualizations(turn_id: str, assistant_message_id: str) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """UPDATE math_visualizations SET assistant_message_id=?,updated_at=CURRENT_TIMESTAMP
               WHERE turn_id=?""",
            (assistant_message_id, turn_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_visualization(visualization_id: str, user_id: str) -> dict[str, Any]:
    conn = get_conn()
    try:
        init_visualization_schema(conn)
        row = conn.execute(
            "SELECT * FROM math_visualizations WHERE id=? AND user_id=?",
            (visualization_id, user_id),
        ).fetchone()
        if not row:
            raise KeyError("visualization not found")
        return _artifact_dict(conn, row)
    finally:
        conn.close()


def get_visualization_record(visualization_id: str) -> dict[str, Any]:
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM math_visualizations WHERE id=?", (visualization_id,)).fetchone()
        if not row:
            raise KeyError("visualization not found")
        result = dict(row)
        result["spec"] = json.loads(result.pop("spec_json") or "{}")
        result["animation_recipe"] = json.loads(result.pop("animation_recipe_json") or "null")
        return result
    finally:
        conn.close()


def visualizations_for_turns(conn, turn_ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    ids = list(dict.fromkeys(item for item in turn_ids if item))
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT * FROM math_visualizations WHERE turn_id IN ({placeholders}) ORDER BY created_at",
        ids,
    ).fetchall()
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row["turn_id"], []).append(_artifact_dict(conn, row))
    return result


def visualizations_for_chats(conn, chat_ids: Iterable[str]) -> dict[str, list[dict[str, Any]]]:
    ids = list(dict.fromkeys(item for item in chat_ids if item))
    if not ids:
        return {}
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT * FROM math_visualizations WHERE chat_history_id IN ({placeholders}) ORDER BY created_at",
        ids,
    ).fetchall()
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        result.setdefault(row["chat_history_id"], []).append(_artifact_dict(conn, row))
    return result


def decorate_chat_history(conn, rows: Iterable[Any]) -> list[dict[str, Any]]:
    history = [dict(row) for row in rows]
    by_chat = visualizations_for_chats(conn, [item.get("id") for item in history])
    for item in history:
        item["visualizations"] = by_chat.get(item.get("id"), [])
    return history


def decorate_messages(conn, rows: Iterable[Any]) -> list[dict[str, Any]]:
    messages = [dict(row) for row in rows]
    by_turn = visualizations_for_turns(conn, [message.get("turn_id") for message in messages])
    for message in messages:
        message["visualizations"] = by_turn.get(message.get("turn_id"), []) if message.get("role") == "assistant" else []
    return messages


def create_animation_job(visualization_id: str, user_id: str) -> tuple[dict[str, Any], bool]:
    conn = get_conn()
    try:
        init_visualization_schema(conn)
        visualization = conn.execute(
            "SELECT * FROM math_visualizations WHERE id=? AND user_id=?",
            (visualization_id, user_id),
        ).fetchone()
        if not visualization:
            raise KeyError("visualization not found")
        if not visualization["animation_recipe_json"]:
            raise ValueError("visualization has no animation recipe")
        existing = conn.execute(
            """SELECT * FROM animation_jobs WHERE visualization_id=? AND user_id=?
               AND status IN ('queued','running','completed') ORDER BY created_at DESC LIMIT 1""",
            (visualization_id, user_id),
        ).fetchone()
        if existing:
            return dict(existing), False
        job_id = str(uuid.uuid4())
        try:
            conn.execute(
                "INSERT INTO animation_jobs(id,visualization_id,user_id,status) VALUES(?,?,?,'queued')",
                (job_id, visualization_id, user_id),
            )
        except sqlite3.IntegrityError:
            concurrent = conn.execute(
                """SELECT * FROM animation_jobs WHERE visualization_id=? AND user_id=?
                   AND status IN ('queued','running','completed') ORDER BY created_at DESC LIMIT 1""",
                (visualization_id, user_id),
            ).fetchone()
            if concurrent:
                return dict(concurrent), False
            raise
        conn.execute(
            "UPDATE math_visualizations SET animation_status='queued',updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (visualization_id,),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM animation_jobs WHERE id=?", (job_id,)).fetchone()
        return dict(row), True
    finally:
        conn.close()


def set_rq_job_id(job_id: str, rq_job_id: str) -> None:
    conn = get_conn()
    try:
        conn.execute("UPDATE animation_jobs SET rq_job_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (rq_job_id, job_id))
        conn.commit()
    finally:
        conn.close()


def get_animation_job(job_id: str, user_id: str | None = None) -> dict[str, Any]:
    conn = get_conn()
    try:
        query = "SELECT * FROM animation_jobs WHERE id=?"
        params: tuple[Any, ...] = (job_id,)
        if user_id is not None:
            query += " AND user_id=?"
            params = (job_id, user_id)
        row = conn.execute(query, params).fetchone()
        if not row:
            raise KeyError("animation job not found")
        return dict(row)
    finally:
        conn.close()


def update_animation_job(
    job_id: str,
    status: str,
    *,
    error: str = "",
    video_key: str | None = None,
    poster_key: str | None = None,
) -> None:
    if status not in {"queued", "running", "completed", "failed"}:
        raise ValueError("invalid animation job status")
    conn = get_conn()
    try:
        row = conn.execute("SELECT visualization_id FROM animation_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise KeyError("animation job not found")
        completed_sql = ",completed_at=CURRENT_TIMESTAMP" if status in {"completed", "failed"} else ""
        conn.execute(
            f"""UPDATE animation_jobs SET status=?,error=?,video_key=COALESCE(?,video_key),
                   poster_key=COALESCE(?,poster_key),updated_at=CURRENT_TIMESTAMP{completed_sql}
               WHERE id=?""",
            (status, error[:1000], video_key, poster_key, job_id),
        )
        conn.execute(
            "UPDATE math_visualizations SET animation_status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (status, row["visualization_id"]),
        )
        conn.commit()
    finally:
        conn.close()


def delete_visualizations_for_chat(chat_history_id: str) -> list[str]:
    conn = get_conn()
    try:
        init_visualization_schema(conn)
        rows = conn.execute(
            """SELECT j.video_key,j.poster_key FROM animation_jobs j
               JOIN math_visualizations v ON v.id=j.visualization_id
               WHERE v.chat_history_id=?""",
            (chat_history_id,),
        ).fetchall()
        ids = [row[0] for row in conn.execute("SELECT id FROM math_visualizations WHERE chat_history_id=?", (chat_history_id,)).fetchall()]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM animation_jobs WHERE visualization_id IN ({placeholders})", ids)
        conn.execute("DELETE FROM math_visualizations WHERE chat_history_id=?", (chat_history_id,))
        conn.commit()
        return [key for row in rows for key in row if key]
    finally:
        conn.close()


def migrate_visualization_user(old_user_id: str, new_user_id: str) -> int:
    conn = get_conn()
    try:
        init_visualization_schema(conn)
        cursor = conn.execute(
            "UPDATE math_visualizations SET user_id=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (new_user_id, old_user_id),
        )
        conn.execute(
            "UPDATE animation_jobs SET user_id=?,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            (new_user_id, old_user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def _artifact_dict(conn, row) -> dict[str, Any]:
    latest_job = conn.execute(
        "SELECT * FROM animation_jobs WHERE visualization_id=? ORDER BY created_at DESC LIMIT 1",
        (row["id"],),
    ).fetchone()
    artifact = {
        "id": row["id"],
        "version": row["version"],
        "kind": row["kind"],
        "title": row["title"],
        "spec": json.loads(row["spec_json"] or "{}"),
        "animation_available": bool(row["animation_recipe_json"]),
        "animation_status": row["animation_status"],
    }
    if latest_job:
        artifact["animation_job_id"] = latest_job["id"]
    return artifact
