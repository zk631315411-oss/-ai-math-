import uuid
from typing import List
from app.db.connection import get_conn


def save_chat_log(user_id: str, sequence_id: str, question: str,
                  answer: str = None, sources: str = None) -> bool:
    """写入 chat_logs，is_analyzed=0"""
    conn = get_conn()
    cursor = conn.cursor()
    log_id = str(uuid.uuid4())
    try:
        cursor.execute("""
            INSERT INTO chat_logs (id, user_id, sequence_id, question, answer, sources, is_analyzed)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (log_id, user_id, sequence_id, question, answer, sources))
        conn.commit()
        conn.close()
        print(f"[chat_logs] 写入成功: user={user_id[:12]}... seq={sequence_id} q={question[:30]}")
        return True
    except Exception as e:
        print(f"[chat_logs] 写入失败: {e}")
        conn.close()
        return False


def get_unanalyzed_chat_logs(user_id: str, limit: int = 10) -> List[dict]:
    """取出未分析的记录（供诊断Worker使用）"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, sequence_id, question, answer, sources, is_analyzed, created_at
        FROM chat_logs
        WHERE user_id = ? AND is_analyzed = 0
        ORDER BY created_at ASC
        LIMIT ?
    """, (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def mark_chat_logs_analyzed(ids: List[str]) -> int:
    """批量标记为已分析"""
    if not ids:
        return 0
    conn = get_conn()
    cursor = conn.cursor()
    placeholders = ','.join('?' * len(ids))
    cursor.execute(f"""
        UPDATE chat_logs SET is_analyzed = 1
        WHERE id IN ({placeholders})
    """, ids)
    conn.commit()
    affected = cursor.rowcount
    conn.close()
    return affected


def group_chat_logs_by_sequence_id(logs: List[dict]) -> dict:
    """按 sequence_id 分组（供诊断批量处理使用）"""
    grouped = {}
    for log in logs:
        sid = log.get("sequence_id")
        if sid not in grouped:
            grouped[sid] = []
        grouped[sid].append(log)
    return grouped


def get_users_with_unanalyzed_logs(min_count: int = 1) -> List[str]:
    """获取有未分析日志的用户ID列表（供诊断Worker扫描）"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT user_id, COUNT(*) as cnt FROM chat_logs
        WHERE is_analyzed = 0
        GROUP BY user_id
        HAVING cnt >= ?
    """, (min_count,))
    rows = cursor.fetchall()
    conn.close()
    return [row["user_id"] for row in rows]
