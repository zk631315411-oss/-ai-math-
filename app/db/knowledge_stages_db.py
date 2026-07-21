import uuid
import json
from app.db.connection import get_conn


def _to_uuid():
    return str(uuid.uuid4())


def get_stage(user_id: str, concept_name: str) -> int | None:
    """读路径防竞态：先聚合 pending 表，再查 canonical 表。"""
    conn = get_conn()

    # canonical
    row = conn.execute(
        "SELECT stage FROM knowledge_stages WHERE user_id=? AND concept_name=?",
        (user_id, concept_name),
    ).fetchone()
    base = row["stage"] if row and row["stage"] is not None else None

    # pending（按时间升序）
    pendings = conn.execute(
        """SELECT delta_value, override_stage
           FROM pending_stage_updates
           WHERE user_id=? AND concept_name=?
           ORDER BY created_at ASC""",
        (user_id, concept_name),
    ).fetchall()

    conn.close()

    if not pendings:
        return base

    stage = base if base is not None else 0
    for p in pendings:
        if p["override_stage"] is not None:
            stage = p["override_stage"]
        if p["delta_value"] is not None:
            stage += p["delta_value"]
        stage = max(0, min(5, stage))
    return stage


def get_stages_batch(user_id: str, concepts: list[str]) -> list[dict]:
    """批量查询：返回 [{concept_name, stage, confidence}]。"""
    if not concepts:
        return []
    results = []
    for name in concepts:
        stage = get_stage(user_id, name)
        results.append({"concept_name": name, "stage": stage})
    return results


def update_stage(user_id: str, concept_name: str, delta: int | None = None,
                 override: int | None = None, confidence_adj: float = 0,
                 source: str = ""):
    """写入 pending 队列（非 canonical 表），Worker 每分钟消费。"""
    conn = get_conn()
    conn.execute(
        """INSERT INTO pending_stage_updates
           (user_id, concept_name, delta_value, override_stage, confidence_adjustment, source)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (user_id, concept_name, delta, override, confidence_adj, source),
    )
    conn.commit()
    conn.close()


def get_stages_summary(user_id: str) -> dict:
    """返回 {stage_distribution: {0: n, 1: n, ...}, total, avg_stage}。"""
    conn = get_conn()
    rows = conn.execute(
        "SELECT stage FROM knowledge_stages WHERE user_id=? AND stage IS NOT NULL",
        (user_id,),
    ).fetchall()
    conn.close()

    dist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    stages = []
    for r in rows:
        s = r["stage"]
        if s is not None and 0 <= s <= 5:
            dist[s] += 1
            stages.append(s)

    return {
        "distribution": dist,
        "total": len(stages),
        "avg_stage": round(sum(stages) / len(stages), 2) if stages else 0,
    }


def get_user_avg_stage(user_id: str) -> int | None:
    """返回用户所有概念的平均 stage（整数），无数据时返回 None。
    用于 get_stage(chapter_name) 查不到时的兜底——chapter_name 和 Neo4j 概念名不在同一命名空间。"""
    conn = get_conn()
    row = conn.execute(
        "SELECT AVG(CAST(stage AS REAL)) FROM knowledge_stages WHERE user_id=? AND stage IS NOT NULL",
        (user_id,),
    ).fetchone()
    conn.close()
    avg = row[0]
    return round(avg) if avg is not None else None


def consume_pending(user_id: str):
    """Worker 内部调用：消费 pending 队列，写入 canonical 表（在一个事务内）。"""
    conn = get_conn()
    pendings = conn.execute(
        """SELECT id, concept_name, delta_value, override_stage, confidence_adjustment
           FROM pending_stage_updates
           WHERE user_id=?
           ORDER BY created_at ASC""",
        (user_id,),
    ).fetchall()

    if not pendings:
        conn.close()
        return

    with conn:  # 单个事务
        for p in pendings:
            row = conn.execute(
                "SELECT id, stage, confidence FROM knowledge_stages WHERE user_id=? AND concept_name=?",
                (user_id, p["concept_name"]),
            ).fetchone()

            if row:
                cur_stage = row["stage"] if row["stage"] is not None else 0
                cur_conf = row["confidence"]
                ks_id = row["id"]
            else:
                cur_stage = 0
                cur_conf = 0.3
                ks_id = _to_uuid()
                conn.execute(
                    "INSERT OR IGNORE INTO knowledge_stages(id, user_id, concept_name, stage, confidence) VALUES (?,?,?,?,?)",
                    (ks_id, user_id, p["concept_name"], 0, 0.3),
                )

            if p["override_stage"] is not None:
                cur_stage = p["override_stage"]
            if p["delta_value"] is not None:
                cur_stage += p["delta_value"]
            cur_stage = max(0, min(5, cur_stage))
            cur_conf = max(0, min(1, cur_conf + (p["confidence_adjustment"] or 0)))

            conn.execute(
                "UPDATE knowledge_stages SET stage=?, confidence=?, last_updated=CURRENT_TIMESTAMP WHERE id=?",
                (cur_stage, cur_conf, ks_id),
            )

        # 原子删除已消费行（同一事务）
        pending_ids = [p["id"] for p in pendings]
        for pid in pending_ids:
            conn.execute("DELETE FROM pending_stage_updates WHERE id=?", (pid,))

    conn.close()
