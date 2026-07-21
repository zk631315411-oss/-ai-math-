import uuid
from typing import List
from app.db.connection import get_conn


def update_knowledge_stats(user_id: str, topic: str) -> dict:
    """Update user knowledge stats. Returns (consecutive_turns, total_asks)."""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, consecutive_turns, total_asks FROM user_knowledge_stats
        WHERE user_id = ? AND topic = ?
    """, (user_id, topic))
    row = cursor.fetchone()

    if row:
        new_consecutive = row["consecutive_turns"] + 1
        new_total = row["total_asks"] + 1
        cursor.execute("""
            UPDATE user_knowledge_stats
            SET consecutive_turns = ?, total_asks = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (new_consecutive, new_total, row["id"]))
    else:
        new_consecutive = 1
        new_total = 1
        cursor.execute("""
            INSERT INTO user_knowledge_stats (id, user_id, topic, consecutive_turns, total_asks)
            VALUES (?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), user_id, topic, new_consecutive, new_total))

    conn.commit()
    conn.close()
    return {"consecutive_turns": new_consecutive, "total_asks": new_total}


def reset_consecutive_turns(user_id: str, topic: str) -> None:
    """当用户切换到不同topic时，重置该topic的连续轮数为1"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE user_knowledge_stats
        SET consecutive_turns = 1
        WHERE user_id = ? AND topic = ?
    """, (user_id, topic))

    conn.commit()
    conn.close()


def get_knowledge_stats(user_id: str) -> List[dict]:
    """获取用户所有知识点的统计"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT topic, consecutive_turns, total_asks, updated_at
        FROM user_knowledge_stats
        WHERE user_id = ?
        ORDER BY total_asks DESC
    """, (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "topic": row["topic"],
            "consecutive_turns": row["consecutive_turns"],
            "total_asks": row["total_asks"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


