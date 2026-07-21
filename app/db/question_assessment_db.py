import json
from typing import List
from app.db.connection import get_conn


def save_question_assessment(
    user_id: str,
    question_id: str,
    mt_coverage: int = 0, mt_radius: int = 0, mt_technical: int = 0,
    lr_coverage: int = 0, lr_radius: int = 0, lr_technical: int = 0,
    so_coverage: int = 0, so_radius: int = 0, so_technical: int = 0,
    mr_coverage: int = 0, mr_radius: int = 0, mr_technical: int = 0,
    ps_coverage: int = 0, ps_radius: int = 0, ps_technical: int = 0,
    overall_score: float = 0.0,
    weak_points: List[str] = None,
    sequence_id: str = "",
    summary: str = "",
    assessment_id: str = None,
) -> str:
    """保存单次提问的维度评估"""
    import uuid

    conn = get_conn()
    cursor = conn.cursor()

    assessment_id = assessment_id or str(uuid.uuid4())
    weak_str = json.dumps(weak_points, ensure_ascii=False) if weak_points else "[]"

    if overall_score == 0.0:
        total = (mt_coverage + mt_radius + mt_technical + lr_coverage + lr_radius + lr_technical +
                 so_coverage + so_radius + so_technical + mr_coverage + mr_radius + mr_technical +
                 ps_coverage + ps_radius + ps_technical)
        overall_score = total / 15.0 if total > 0 else 0.0

    cursor.execute("""
        INSERT INTO question_assessments (
            id, user_id, question_id,
            mt_coverage, mt_radius, mt_technical,
            lr_coverage, lr_radius, lr_technical,
            so_coverage, so_radius, so_technical,
            mr_coverage, mr_radius, mr_technical,
            ps_coverage, ps_radius, ps_technical,
            overall_score, weak_points, sequence_id, summary
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        assessment_id, user_id, question_id,
        mt_coverage, mt_radius, mt_technical,
        lr_coverage, lr_radius, lr_technical,
        so_coverage, so_radius, so_technical,
        mr_coverage, mr_radius, mr_technical,
        ps_coverage, ps_radius, ps_technical,
        overall_score, weak_str, sequence_id or "", summary or "",
    ))

    conn.commit()
    conn.close()
    return assessment_id


def get_question_assessments(user_id: str, limit: int = 50) -> List[dict]:
    """获取用户的诊断评估历史（diagnostic类型）"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM question_assessments
        WHERE user_id = ? AND question_id = 'diagnostic'
        ORDER BY created_at DESC
        LIMIT ?
    """, (user_id, limit))

    rows = cursor.fetchall()
    conn.close()

    result = []
    for row in rows:
        r = dict(row)
        deltas = []
        for prefix, dim_name in [
            ("mt", "mathematical_thinking"), ("lr", "logical_reasoning"),
            ("so", "symbolic_operation"), ("mr", "multi_representation"),
            ("ps", "problem_solving")
        ]:
            cov = r.get(f"{prefix}_coverage", 0)
            rad = r.get(f"{prefix}_radius", 0)
            tech = r.get(f"{prefix}_technical", 0)
            if cov or rad or tech:
                deltas.append({
                    "dimension": dim_name,
                    "delta": {"coverage": cov, "radius": rad, "technical": tech},
                    "evidence": ""
                })

        result.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "sequence_id": r.get("sequence_id") or "",
            "dimension_deltas": deltas,
            "weak_concepts": json.loads(r.get("weak_points") or "[]"),
            "summary": r.get("summary") or "",
            "created_at": r.get("created_at"),
        })

    return result


def save_diagnostic_assessment(
    assessment_id: str,
    user_id: str,
    dimension_deltas: list,
    weak_concepts: list,
    summary: str,
    sequence_id: str = "",
) -> bool:
    """兼容保存诊断评估（适配 diagnostic_worker 调用方签名）。
    将 dimension_deltas 格式展平为 15 维度字段后写入 question_assessments。
    """
    delta_map = {d.get("dimension"): d.get("delta", {}) for d in dimension_deltas}

    def g(dim_prefix, sub):
        d = delta_map.get(dim_prefix, {})
        return d.get(sub, 0)

    return save_question_assessment(
        user_id=user_id,
        question_id="diagnostic",
        mt_coverage=g("mt", "coverage"), mt_radius=g("mt", "radius"), mt_technical=g("mt", "technical"),
        lr_coverage=g("lr", "coverage"), lr_radius=g("lr", "radius"), lr_technical=g("lr", "technical"),
        so_coverage=g("so", "coverage"), so_radius=g("so", "radius"), so_technical=g("so", "technical"),
        mr_coverage=g("mr", "coverage"), mr_radius=g("mr", "radius"), mr_technical=g("mr", "technical"),
        ps_coverage=g("ps", "coverage"), ps_radius=g("ps", "radius"), ps_technical=g("ps", "technical"),
        weak_points=weak_concepts,
        sequence_id=sequence_id,
        summary=summary,
        assessment_id=assessment_id,
    )
