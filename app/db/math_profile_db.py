import json
from typing import List, Optional
from datetime import datetime
from app.db.connection import get_conn


def save_math_profile(
    user_id: str,
    grade: str = None,
    mt_coverage: int = -1, mt_radius: int = -1, mt_technical: int = -1,
    lr_coverage: int = -1, lr_radius: int = -1, lr_technical: int = -1,
    so_coverage: int = -1, so_radius: int = -1, so_technical: int = -1,
    mr_coverage: int = -1, mr_radius: int = -1, mr_technical: int = -1,
    ps_coverage: int = -1, ps_radius: int = -1, ps_technical: int = -1,
    weak_points: List[str] = None,
    insight_cache: str = None,
) -> bool:
    """保存或更新数学素养画像"""
    conn = get_conn()
    cursor = conn.cursor()

    weak_str = json.dumps(weak_points, ensure_ascii=False) if weak_points else "[]"

    cursor.execute("SELECT user_id FROM math_profiles WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None

    if not exists:
        cursor.execute("""
            INSERT INTO math_profiles (
                user_id, grade,
                mt_coverage, mt_radius, mt_technical,
                lr_coverage, lr_radius, lr_technical,
                so_coverage, so_radius, so_technical,
                mr_coverage, mr_radius, mr_technical,
                ps_coverage, ps_radius, ps_technical,
                weak_points
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, grade or "",
            mt_coverage, mt_radius, mt_technical,
            lr_coverage, lr_radius, lr_technical,
            so_coverage, so_radius, so_technical,
            mr_coverage, mr_radius, mr_technical,
            ps_coverage, ps_radius, ps_technical,
            weak_str
        ))
    else:
        cursor.execute("""
            UPDATE math_profiles SET
                grade = COALESCE(?, grade),
                mt_coverage = CASE WHEN ? >= 0 THEN ? ELSE mt_coverage END,
                mt_radius = CASE WHEN ? >= 0 THEN ? ELSE mt_radius END,
                mt_technical = CASE WHEN ? >= 0 THEN ? ELSE mt_technical END,
                lr_coverage = CASE WHEN ? >= 0 THEN ? ELSE lr_coverage END,
                lr_radius = CASE WHEN ? >= 0 THEN ? ELSE lr_radius END,
                lr_technical = CASE WHEN ? >= 0 THEN ? ELSE lr_technical END,
                so_coverage = CASE WHEN ? >= 0 THEN ? ELSE so_coverage END,
                so_radius = CASE WHEN ? >= 0 THEN ? ELSE so_radius END,
                so_technical = CASE WHEN ? >= 0 THEN ? ELSE so_technical END,
                mr_coverage = CASE WHEN ? >= 0 THEN ? ELSE mr_coverage END,
                mr_radius = CASE WHEN ? >= 0 THEN ? ELSE mr_radius END,
                mr_technical = CASE WHEN ? >= 0 THEN ? ELSE mr_technical END,
                ps_coverage = CASE WHEN ? >= 0 THEN ? ELSE ps_coverage END,
                ps_radius = CASE WHEN ? >= 0 THEN ? ELSE ps_radius END,
                ps_technical = CASE WHEN ? >= 0 THEN ? ELSE ps_technical END,
                weak_points = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (
            grade, mt_coverage, mt_coverage, mt_radius, mt_radius, mt_technical, mt_technical,
            lr_coverage, lr_coverage, lr_radius, lr_radius, lr_technical, lr_technical,
            so_coverage, so_coverage, so_radius, so_radius, so_technical, so_technical,
            mr_coverage, mr_coverage, mr_radius, mr_radius, mr_technical, mr_technical,
            ps_coverage, ps_coverage, ps_radius, ps_radius, ps_technical, ps_technical,
            weak_str, user_id
        ))

    if insight_cache is not None:
        cursor.execute(
            "UPDATE math_profiles SET insight_cache = ?, insight_generated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
            (insight_cache, user_id)
        )

    conn.commit()
    conn.close()
    return True


def get_math_profile(user_id: str) -> Optional[dict]:
    """获取数学素养画像"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM math_profiles WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    dims = {
        "mathematical_thinking": {"coverage": row["mt_coverage"], "radius": row["mt_radius"], "technical": row["mt_technical"]},
        "logical_reasoning": {"coverage": row["lr_coverage"], "radius": row["lr_radius"], "technical": row["lr_technical"]},
        "symbolic_operation": {"coverage": row["so_coverage"], "radius": row["so_radius"], "technical": row["so_technical"]},
        "multi_representation": {"coverage": row["mr_coverage"], "radius": row["mr_radius"], "technical": row["mr_technical"]},
        "problem_solving": {"coverage": row["ps_coverage"], "radius": row["ps_radius"], "technical": row["ps_technical"]},
    }
    total = sum(
        (s["coverage"] + s["radius"] + s["technical"]) / 3.0
        for s in dims.values()
    )
    return {
        "user_id": row["user_id"],
        "grade": row["grade"] or "",
        "dimensions": dims,
        "overall_average": round(total / 5.0, 2) if total > 0 else 0.0,
        "weak_points": json.loads(row["weak_points"] or "[]"),
        "latest_diagnostic_report": json.loads(row["latest_diagnostic_report"] or "{}"),
        "last_diagnosed_at": row["last_diagnosed_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_last_diagnosed_at(user_id: str) -> Optional[datetime]:
    """获取用户上次诊断时间"""
    conn = get_conn()
    cursor = conn.cursor()

    cursor.execute("SELECT last_diagnosed_at FROM math_profiles WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()

    if not row or not row["last_diagnosed_at"]:
        return None

    return datetime.fromisoformat(row["last_diagnosed_at"])


def update_diagnostic_report(user_id: str, diagnostic_report: dict, dimension_scores: dict = None) -> bool:
    """更新用户的诊断报告（微观+宏观双写）"""
    conn = get_conn()
    cursor = conn.cursor()

    report_json = json.dumps(diagnostic_report, ensure_ascii=False)

    cursor.execute("SELECT user_id FROM math_profiles WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None

    if not exists:
        mt = dimension_scores.get("mathematical_thinking", {}) if dimension_scores else {}
        lr = dimension_scores.get("logical_reasoning", {}) if dimension_scores else {}
        so = dimension_scores.get("symbolic_operation", {}) if dimension_scores else {}
        mr = dimension_scores.get("multi_representation", {}) if dimension_scores else {}
        ps = dimension_scores.get("problem_solving", {}) if dimension_scores else {}

        cursor.execute("""
            INSERT INTO math_profiles (
                user_id, latest_diagnostic_report, last_diagnosed_at,
                mt_coverage, mt_radius, mt_technical,
                lr_coverage, lr_radius, lr_technical,
                so_coverage, so_radius, so_technical,
                mr_coverage, mr_radius, mr_technical,
                ps_coverage, ps_radius, ps_technical
            ) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, report_json,
            mt.get("coverage", 0), mt.get("radius", 0), mt.get("technical", 0),
            lr.get("coverage", 0), lr.get("radius", 0), lr.get("technical", 0),
            so.get("coverage", 0), so.get("radius", 0), so.get("technical", 0),
            mr.get("coverage", 0), mr.get("radius", 0), mr.get("technical", 0),
            ps.get("coverage", 0), ps.get("radius", 0), ps.get("technical", 0)
        ))
    elif dimension_scores:
        cursor.execute("""
            SELECT mt_coverage, mt_radius, mt_technical,
                   lr_coverage, lr_radius, lr_technical,
                   so_coverage, so_radius, so_technical,
                   mr_coverage, mr_radius, mr_technical,
                   ps_coverage, ps_radius, ps_technical
            FROM math_profiles WHERE user_id = ?
        """, (user_id,))
        cur = cursor.fetchone()
        def _add(dim_full, rubric, col_val):
            delta = dimension_scores.get(dim_full, {}).get(rubric, 0) if dimension_scores else 0
            base = col_val if col_val is not None and col_val >= 0 else 0
            return max(0, min(3, base + delta))
        mt = {k: _add("mathematical_thinking", k, cur[f"mt_{k}"]) for k in ("coverage","radius","technical")}
        lr = {k: _add("logical_reasoning", k, cur[f"lr_{k}"]) for k in ("coverage","radius","technical")}
        so = {k: _add("symbolic_operation", k, cur[f"so_{k}"]) for k in ("coverage","radius","technical")}
        mr = {k: _add("multi_representation", k, cur[f"mr_{k}"]) for k in ("coverage","radius","technical")}
        ps = {k: _add("problem_solving", k, cur[f"ps_{k}"]) for k in ("coverage","radius","technical")}
        cursor.execute("""
            UPDATE math_profiles SET
                latest_diagnostic_report = ?,
                last_diagnosed_at = CURRENT_TIMESTAMP,
                mt_coverage = ?, mt_radius = ?, mt_technical = ?,
                lr_coverage = ?, lr_radius = ?, lr_technical = ?,
                so_coverage = ?, so_radius = ?, so_technical = ?,
                mr_coverage = ?, mr_radius = ?, mr_technical = ?,
                ps_coverage = ?, ps_radius = ?, ps_technical = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (
            report_json,
            mt.get("coverage", 0), mt.get("radius", 0), mt.get("technical", 0),
            lr.get("coverage", 0), lr.get("radius", 0), lr.get("technical", 0),
            so.get("coverage", 0), so.get("radius", 0), so.get("technical", 0),
            mr.get("coverage", 0), mr.get("radius", 0), mr.get("technical", 0),
            ps.get("coverage", 0), ps.get("radius", 0), ps.get("technical", 0),
            user_id
        ))
    else:
        cursor.execute("""
            UPDATE math_profiles SET
                latest_diagnostic_report = ?,
                last_diagnosed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        """, (report_json, user_id))

    conn.commit()
    conn.close()
    return True


def save_textbook_preference(user_id: str, textbook_id: str, page_number: int) -> bool:
    """保存用户教材和页码偏好"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE math_profiles
        SET last_textbook_id = ?, last_page_number = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
    """, (textbook_id, page_number, user_id))
    conn.commit()
    if cursor.rowcount == 0:
        try:
            cursor.execute("""
                INSERT INTO math_profiles (user_id, last_textbook_id, last_page_number)
                VALUES (?, ?, ?)
            """, (user_id, textbook_id, page_number))
            conn.commit()
        except Exception:
            pass
    conn.close()
    return True


def get_textbook_preference(user_id: str) -> Optional[dict]:
    """获取用户教材和页码偏好"""
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT last_textbook_id, last_page_number FROM math_profiles WHERE user_id = ?
    """, (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "textbook_id": row["last_textbook_id"] or "gaodai_shang",
            "page_number": row["last_page_number"] if row["last_page_number"] else 1
        }
    return None
