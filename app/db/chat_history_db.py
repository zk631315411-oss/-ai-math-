"""chat_history 表 CRUD — Phase 2 扩展：支持页码标记、持久化问答。"""
import uuid
import json
from datetime import datetime
from typing import List, Optional
from app.db.connection import get_conn


def _uid():
    return str(uuid.uuid4())


def get_chat_history(user_id: str, limit: int = 50,
                     page_number: Optional[int] = None,
                     chat_id: Optional[str] = None) -> List[dict]:
    conn = get_conn()
    try:
        cursor = conn.cursor()
        if chat_id:
            cursor.execute("SELECT * FROM chat_history WHERE id=?", (chat_id,))
        elif page_number is not None:
            cursor.execute("""
                SELECT * FROM chat_history
                WHERE user_id=? AND page_number=?
                ORDER BY created_at ASC LIMIT ?
            """, (user_id, page_number, limit))
        else:
            cursor.execute("""
                SELECT * FROM chat_history
                WHERE user_id=?
                ORDER BY created_at DESC LIMIT ?
            """, (user_id, limit))

        from app.db.visualization_db import decorate_chat_history
        return decorate_chat_history(conn, cursor.fetchall())
    finally:
        conn.close()


def save_chat_history(user_id: str, question: str, answer: Optional[str] = None,
                      page_number: Optional[int] = None,
                      marker_y_ratio: Optional[float] = None,
                      marker_type: str = "screenshot",
                      thumbnail: Optional[str] = None,
                      crop_bbox: Optional[str] = None,
                      screenshot_context_id: Optional[str] = None,
                      sources: Optional[str] = None,
                      knowledge_points: Optional[str] = None,
                      thinking: Optional[str] = None,
                      follow_ups: str = "[]") -> str:
    chat_id = _uid()
    conn = get_conn()
    conn.execute("""
        INSERT INTO chat_history (id, user_id, question, answer, page_number,
                                  marker_y_ratio, marker_type, thumbnail, sources, knowledge_points,
                                  thinking, follow_ups, crop_bbox, screenshot_context_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (chat_id, user_id, question, answer or '', page_number, marker_y_ratio,
          marker_type, thumbnail, sources, knowledge_points, thinking or '', follow_ups,
          crop_bbox, screenshot_context_id))
    conn.commit()
    conn.close()
    return chat_id


def update_chat_answer(
    chat_id: str,
    answer: Optional[str] = None,
    thinking: Optional[str] = None,
    follow_ups: Optional[str] = None,
    screenshot_context_id: Optional[str] = None,
    thumbnail: Optional[str] = None,
    crop_bbox: Optional[str] = None,
):
    conn = get_conn()
    sets = []
    params = []
    if answer is not None:
        sets.append("answer=?")
        params.append(answer)
    if thinking is not None:
        sets.append("thinking=?")
        params.append(thinking)
    if follow_ups is not None:
        sets.append("follow_ups=?")
        params.append(follow_ups)
    if screenshot_context_id is not None:
        sets.append("screenshot_context_id=?")
        params.append(screenshot_context_id)
    if thumbnail is not None:
        sets.append("thumbnail=?")
        params.append(thumbnail)
    if crop_bbox is not None:
        sets.append("crop_bbox=?")
        params.append(crop_bbox)
    if sets:
        params.append(chat_id)
        conn.execute(f"UPDATE chat_history SET {', '.join(sets)} WHERE id=?", params)
        conn.commit()
    conn.close()


def delete_chat_history(chat_id: str):
    from app.db.visualization_db import delete_visualizations_for_chat
    from app.services.visualization.storage import schedule_delete_objects

    object_keys = delete_visualizations_for_chat(chat_id)
    from app.db.tool_trace_db import delete_traces_for_chat
    delete_traces_for_chat(chat_id)
    conn = get_conn()
    conn.execute("DELETE FROM chat_history WHERE id=?", (chat_id,))
    conn.commit()
    conn.close()
    schedule_delete_objects(object_keys)


def migrate_user_id(old_user_id: str, new_user_id: str) -> int:
    """匿名→登录后迁移 chat_history 记录到新账号。返回迁移条数。"""
    conn = get_conn()
    cursor = conn.execute(
        "UPDATE chat_history SET user_id=? WHERE user_id=?",
        (new_user_id, old_user_id)
    )
    count = cursor.rowcount
    conn.commit()
    conn.close()
    from app.db.visualization_db import migrate_visualization_user
    migrate_visualization_user(old_user_id, new_user_id)
    from app.db.tool_trace_db import migrate_trace_user
    migrate_trace_user(old_user_id, new_user_id)
    return count
