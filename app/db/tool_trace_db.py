"""Persistence and redaction for ToolRuntime call traces."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from app.db.connection import get_conn


logger = logging.getLogger("tool_runtime.trace")
_SENSITIVE_KEYS = {"token", "authorization", "api_key", "apikey", "password", "secret", "image", "image_data"}


def init_tool_trace_schema(conn) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS tool_call_traces (
            id TEXT PRIMARY KEY,
            turn_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            chat_history_id TEXT,
            assistant_message_id TEXT,
            round_index INTEGER NOT NULL,
            tool_call_id TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            call_fingerprint TEXT NOT NULL,
            arguments_summary TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL,
            error_code TEXT,
            retryable INTEGER NOT NULL DEFAULT 0,
            duration_ms INTEGER NOT NULL DEFAULT 0,
            artifact_ids TEXT NOT NULL DEFAULT '[]',
            model_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_tool_trace_turn ON tool_call_traces(turn_id, round_index);
        CREATE INDEX IF NOT EXISTS idx_tool_trace_chat ON tool_call_traces(chat_history_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_tool_trace_user ON tool_call_traces(user_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_tool_trace_tool_status ON tool_call_traces(tool_name, status);
        """
    )


def save_tool_trace(
    *,
    turn_id: str,
    user_id: str,
    round_index: int,
    tool_call_id: str,
    tool_name: str,
    call_fingerprint: str,
    arguments: dict[str, Any],
    status: str,
    error_code: str | None,
    retryable: bool,
    duration_ms: int,
    artifact_ids: list[str],
    model_name: str,
    chat_history_id: str | None = None,
    assistant_message_id: str | None = None,
) -> str:
    trace_id = str(uuid.uuid4())
    summary = redact_arguments(arguments)
    conn = get_conn()
    try:
        init_tool_trace_schema(conn)
        conn.execute(
            """INSERT INTO tool_call_traces(
                id,turn_id,user_id,chat_history_id,assistant_message_id,round_index,
                tool_call_id,tool_name,call_fingerprint,arguments_summary,status,error_code,
                retryable,duration_ms,artifact_ids,model_name
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                trace_id, turn_id, user_id, chat_history_id, assistant_message_id, round_index,
                tool_call_id, tool_name, call_fingerprint,
                json.dumps(summary, ensure_ascii=False, sort_keys=True), status, error_code,
                int(retryable), duration_ms, json.dumps(artifact_ids), model_name,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    logger.info(json.dumps({
        "event": "tool_call_trace", "trace_id": trace_id, "turn_id": turn_id,
        "tool": tool_name, "status": status, "error_code": error_code,
        "duration_ms": duration_ms, "arguments": summary,
    }, ensure_ascii=False, separators=(",", ":")))
    return trace_id


def redact_arguments(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[max-depth]"
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in list(value.items())[:20]:
            lowered = str(key).lower()
            if any(secret in lowered for secret in _SENSITIVE_KEYS):
                result[str(key)] = "[redacted]"
            elif key in {"points", "vectors", "lines", "samples", "coordinates"} and isinstance(item, list):
                result[str(key)] = {"count": len(item), "sha256": _hash(item)}
            else:
                result[str(key)] = redact_arguments(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        if len(value) > 12:
            return {"count": len(value), "sha256": _hash(value)}
        return [redact_arguments(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        if value.startswith("data:image"):
            return "[redacted-image]"
        if len(value) > 240:
            return {"preview": value[:160], "length": len(value), "sha256": _hash(value)}
    return value


def query_tool_traces(
    *, turn_id: str | None = None, chat_id: str | None = None,
    tool: str | None = None, status: str | None = None,
    since: str | None = None, limit: int = 100,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for column, value in (("turn_id", turn_id), ("chat_history_id", chat_id), ("tool_name", tool), ("status", status)):
        if value:
            clauses.append(f"{column}=?")
            params.append(value)
    if since:
        datetime.fromisoformat(since.replace("Z", "+00:00"))
        clauses.append("created_at>=?")
        params.append(since)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(max(1, min(limit, 1000)))
    conn = get_conn()
    try:
        init_tool_trace_schema(conn)
        rows = conn.execute(
            f"SELECT * FROM tool_call_traces{where} ORDER BY created_at DESC LIMIT ?", params
        ).fetchall()
        return [_decode_row(dict(row)) for row in rows]
    finally:
        conn.close()


def attach_turn_traces(turn_id: str, assistant_message_id: str) -> None:
    conn = get_conn()
    try:
        init_tool_trace_schema(conn)
        conn.execute(
            "UPDATE tool_call_traces SET assistant_message_id=? WHERE turn_id=?",
            (assistant_message_id, turn_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_traces_for_chat(chat_history_id: str) -> None:
    conn = get_conn()
    try:
        init_tool_trace_schema(conn)
        conn.execute("DELETE FROM tool_call_traces WHERE chat_history_id=?", (chat_history_id,))
        conn.commit()
    finally:
        conn.close()


def migrate_trace_user(old_user_id: str, new_user_id: str) -> int:
    conn = get_conn()
    try:
        init_tool_trace_schema(conn)
        cursor = conn.execute(
            "UPDATE tool_call_traces SET user_id=? WHERE user_id=?", (new_user_id, old_user_id)
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _decode_row(row: dict[str, Any]) -> dict[str, Any]:
    for key in ("arguments_summary", "artifact_ids"):
        try:
            row[key] = json.loads(row.get(key) or ("{}" if key == "arguments_summary" else "[]"))
        except json.JSONDecodeError:
            pass
    row["retryable"] = bool(row.get("retryable"))
    return row
