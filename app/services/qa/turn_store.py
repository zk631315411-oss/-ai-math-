"""QA 过程记录存储。

P0 会写入专门的 qa_turn_records 表，同时兼容写旧的 chat_logs/chat_history。
chat_logs 继续供现有诊断 worker 消费；qa_turn_records 保存更完整的上下文快照。
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app.services.qa.contracts import QATurnRecord


def ensure_qa_turn_records_table() -> None:
    """确保 QA 事实记录表存在。

    这里也会在 app.db.connection.init_db 中创建；此函数用于单测或局部调用兜底。
    """

    from app.db.connection import get_conn

    conn = get_conn()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS qa_turn_records (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                chat_id TEXT,
                marker_id TEXT,
                input_type TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                textbook_id TEXT,
                page_number INTEGER,
                sequence_id TEXT,
                section_node_id TEXT,
                chapter_name TEXT,
                sources TEXT,
                context_snapshot TEXT,
                messages_snapshot TEXT,
                model_name TEXT,
                prompt_preview TEXT,
                image_hash TEXT,
                crop_bbox TEXT,
                screenshot_context_id TEXT,
                latency_ms INTEGER,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE qa_turn_records ADD COLUMN marker_id TEXT")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE qa_turn_records ADD COLUMN apprenticeship_level TEXT")
        except Exception:
            pass
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_qa_turn_records_marker
            ON qa_turn_records(marker_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_qa_turn_records_user_time
            ON qa_turn_records(user_id, created_at)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_qa_turn_records_sequence
            ON qa_turn_records(sequence_id)
        """)
        conn.commit()
    finally:
        conn.close()


def save_turn_record(
    record: QATurnRecord,
    *,
    write_chat_log: bool = True,
    update_chat_history: bool = True,
) -> bool:
    """保存一轮 QA 记录。

    兼容写说明：
    - qa_turn_records：完整结构化上下文，给 QA 模块和后续认知诊断消费。
    - chat_logs：旧诊断 worker 仍然依赖，暂时继续写。
    - chat_history：前端已创建 chat_id 时，在 SSE 完成后补 answer/thinking。
    """

    ensure_qa_turn_records_table()
    saved = _save_qa_turn_record(record)

    if write_chat_log and record.user_id and record.sequence_id:
        try:
            from app.db.chat_log_db import save_chat_log

            save_chat_log(
                user_id=record.user_id,
                sequence_id=record.sequence_id,
                question=record.question,
                answer=record.answer or None,
                sources=_json_dumps(_chat_log_sources(record)),
            )
        except Exception as exc:
            print(f"[qa_turn_records] chat_logs 兼容写失败: {exc}")

    if update_chat_history and record.chat_id and record.user_id:
        try:
            from app.db.chat_history_db import update_chat_answer

            update_chat_answer(
                record.chat_id,
                answer=record.answer,
                thinking="",
                screenshot_context_id=record.screenshot_context_id,
            )
        except Exception as exc:
            print(f"[qa_turn_records] chat_history 更新失败: {exc}")

    return saved


def _save_qa_turn_record(record: QATurnRecord) -> bool:
    from app.db.connection import get_conn

    created_at = record.created_at or datetime.utcnow().isoformat()
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT OR REPLACE INTO qa_turn_records (
                id, user_id, chat_id, marker_id, apprenticeship_level, input_type, question, answer,
                textbook_id, page_number, sequence_id, section_node_id, chapter_name,
                sources, context_snapshot, messages_snapshot, model_name, prompt_preview,
                image_hash, crop_bbox, screenshot_context_id, latency_ms, error, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.turn_id,
                record.user_id,
                record.chat_id,
                record.marker_id,
                record.apprenticeship_level,
                record.input_type,
                record.question,
                record.answer,
                record.textbook_id,
                record.page_number,
                record.sequence_id,
                record.section_node_id,
                record.chapter_name,
                _json_dumps(record.sources),
                _json_dumps(_sanitize_context(record.context_snapshot)),
                _json_dumps(_sanitize_context(record.messages_snapshot)),
                record.model_name,
                record.prompt_preview,
                record.image_hash,
                _json_dumps(record.crop_bbox),
                record.screenshot_context_id,
                record.latency_ms,
                record.error,
                created_at,
            ),
        )
        conn.commit()
        return True
    except Exception as exc:
        print(f"[qa_turn_records] 写入失败: {exc}")
        return False
    finally:
        conn.close()


def _chat_log_sources(record: QATurnRecord) -> dict[str, Any]:
    return {
        "sources": record.sources,
        "qa_turn_id": record.turn_id,
        "input_type": record.input_type,
        "textbook_id": record.textbook_id,
        "page_number": record.page_number,
        "marker_id": record.marker_id,
        "section_node_id": record.section_node_id,
        "screenshot_context_id": record.screenshot_context_id,
    }


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _sanitize_context(value: Any) -> Any:
    """保留可复现上下文，避免把超大 base64 图片直接塞进主记录。"""

    if isinstance(value, dict):
        return {k: _sanitize_context(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_context(v) for v in value]
    if isinstance(value, str):
        if value.startswith("data:image") and len(value) > 1024:
            digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()
            return f"[image_data_url omitted sha256={digest} length={len(value)}]"
        if len(value) > 20000:
            digest = hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()
            return value[:20000] + f"\n...[truncated sha256={digest} length={len(value)}]"
    return value
