"""Pending Stage 聚合 Worker：每分钟消费 pending_stage_updates → knowledge_stages。

与 diagnostic_worker 并存：diagnostic 负责 LLM 诊断（重），pending 负责 stage 聚合（轻）。
"""

import asyncio

PENDING_CHECK_INTERVAL = 60  # 秒


async def pending_worker_loop():
    """每分钟扫描所有有 pending 更新的用户，消费队列写入 canonical 表。"""
    while True:
        try:
            from app.db.connection import get_conn
            from app.db.knowledge_stages_db import consume_pending

            conn = get_conn()
            users = conn.execute(
                "SELECT DISTINCT user_id FROM pending_stage_updates"
            ).fetchall()
            conn.close()

            for row in users:
                try:
                    consume_pending(row["user_id"])
                except Exception:
                    pass  # 单用户失败不影响其他

        except Exception:
            pass

        await asyncio.sleep(PENDING_CHECK_INTERVAL)
