"""Deterministic Stage and 15-dimension projection for diagnosis V2."""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime

from app.config import config
from app.db.connection import get_conn


PROJECTION_VERSION = "v2"
DIMENSION_COLUMNS = {
    "mt": "mt", "lr": "lr", "so": "so", "mr": "mr", "ps": "ps",
}


def diagnosis_mode() -> str:
    mode = (config.DIAGNOSIS_V2_MODE or "shadow").lower()
    return mode if mode in {"shadow", "stage_only", "full"} else "shadow"


def project_pending_stage_evidence(limit: int = 100) -> int:
    if diagnosis_mode() == "shadow":
        return 0
    from app.db.diagnosis_v2_db import list_unprojected_stage_evidence

    count = 0
    for evidence in list_unprojected_stage_evidence(limit):
        if project_stage_evidence(evidence):
            count += 1
    return count


def project_stage_evidence(evidence: dict) -> bool:
    """Project one evidence exactly once; only this function changes V2 Stage."""

    if diagnosis_mode() == "shadow":
        return False
    conn = get_conn()
    try:
        with conn:
            existing = conn.execute(
                """
                SELECT 1 FROM state_projection_log
                WHERE evidence_id=? AND projection_type='stage' AND projection_version=?
                """,
                (evidence["id"], PROJECTION_VERSION),
            ).fetchone()
            if existing:
                return False

            row = conn.execute(
                "SELECT id, stage, confidence FROM knowledge_stages WHERE user_id=? AND concept_name=?",
                (evidence["user_id"], evidence["concept_name"]),
            ).fetchone()
            before = {
                "stage": row["stage"] if row else None,
                "confidence": float(row["confidence"] if row and row["confidence"] is not None else 0.3),
            }
            after = dict(before)
            action = "record_only"
            observed = int(evidence["observed_stage"])
            strength = evidence["strength"]
            direction = evidence["direction"]
            try:
                payload = json.loads(evidence.get("payload") or "{}")
            except (TypeError, json.JSONDecodeError):
                payload = {}
            projection_role = payload.get("projection_role", "primary")

            if projection_role == "supporting":
                action = "suppressed"
            elif strength == "certain":
                if before["stage"] is None and direction == "positive":
                    after = {"stage": observed, "confidence": 0.6}
                    action = "initialize"
                elif direction == "positive" and observed > before["stage"]:
                    after = {"stage": observed, "confidence": min(1.0, before["confidence"] + 0.15)}
                    action = "promote"
                elif direction == "positive" and observed == before["stage"]:
                    after["confidence"] = min(1.0, before["confidence"] + 0.1)
                    action = "confirm"
                elif direction == "negative" and before["stage"] is not None and observed < before["stage"]:
                    if _negative_projection_count(conn, evidence) >= 2:
                        after = {"stage": max(0, before["stage"] - 1), "confidence": 0.5}
                        action = "demote"
                    else:
                        after["confidence"] = max(0.0, before["confidence"] - 0.15)
                        action = "conflict"
            elif strength == "probable" and before["stage"] is not None:
                consistent = (
                    direction == "positive" and observed == before["stage"]
                ) or (
                    direction == "negative" and observed < before["stage"]
                )
                if consistent and direction == "positive":
                    after["confidence"] = min(1.0, before["confidence"] + 0.05)
                    action = "probable_confirm"

            if projection_role == "supporting":
                pass
            elif row:
                conn.execute(
                    """
                    UPDATE knowledge_stages SET stage=?, confidence=?, projection_version=?,
                        last_updated=CURRENT_TIMESTAMP WHERE id=?
                    """,
                    (after["stage"], after["confidence"], PROJECTION_VERSION, row["id"]),
                )
            elif after["stage"] is not None:
                conn.execute(
                    """
                    INSERT INTO knowledge_stages (
                        id, user_id, concept_name, stage, confidence, evidence,
                        baseline_version, projection_version
                    ) VALUES (?, ?, ?, ?, ?, '[]', 'v2', ?)
                    """,
                    (
                        str(uuid.uuid4()), evidence["user_id"], evidence["concept_name"],
                        after["stage"], after["confidence"], PROJECTION_VERSION,
                    ),
                )

            after["action"] = action
            projection_key = f"{evidence['user_id']}:{evidence['concept_name']}"
            conn.execute(
                """
                INSERT INTO state_projection_log (
                    id, evidence_id, projection_type, projection_key, before_value,
                    after_value, projection_version
                ) VALUES (?, ?, 'stage', ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()), evidence["id"], projection_key,
                    json.dumps(before, ensure_ascii=False),
                    json.dumps(after, ensure_ascii=False), PROJECTION_VERSION,
                ),
            )
        return True
    finally:
        conn.close()


def _negative_projection_count(conn, evidence: dict) -> int:
    projection_key = f"{evidence['user_id']}:{evidence['concept_name']}"
    last = conn.execute(
        """
        SELECT rowid AS projection_rowid FROM state_projection_log
        WHERE projection_type='stage' AND projection_key=? AND projection_version=?
          AND json_extract(after_value, '$.action')='demote'
        ORDER BY rowid DESC LIMIT 1
        """,
        (projection_key, PROJECTION_VERSION),
    ).fetchone()
    params: list[object] = [evidence["user_id"], evidence["concept_name"]]
    time_filter = ""
    if last:
        time_filter = " AND p.rowid > ?"
        params.append(last["projection_rowid"])
    row = conn.execute(
        f"""
        SELECT COUNT(DISTINCT e.source_type || ':' || e.source_id) AS n
        FROM diagnostic_evidence e
        JOIN state_projection_log p ON p.evidence_id=e.id
        WHERE e.user_id=? AND e.concept_name=? AND e.observation_type='stage'
          AND e.direction='negative' AND e.strength='certain'
          AND p.projection_type='stage' AND p.projection_version='v2'{time_filter}
          AND COALESCE(json_extract(p.after_value, '$.action'), '') <> 'suppressed'
        """,
        params,
    ).fetchone()
    # Current evidence is not projected yet; add it to the prior distinct events.
    return int(row["n"] or 0) + 1


def close_ready_dimension_windows() -> int:
    if diagnosis_mode() != "full":
        return 0
    conn = get_conn()
    closed = 0
    try:
        groups = conn.execute(
            """
            SELECT user_id, sequence_id
            FROM diagnostic_evidence
            WHERE observation_type='dimension' AND window_id IS NULL
              AND strength IN ('certain','probable') AND sequence_id <> ''
            GROUP BY user_id, sequence_id
            HAVING COUNT(DISTINCT source_type || ':' || source_id) >= 5
            """
        ).fetchall()
        for group in groups:
            if _close_one_dimension_window(conn, group["user_id"], group["sequence_id"]):
                closed += 1
        return closed
    finally:
        conn.close()


def _close_one_dimension_window(conn, user_id: str, sequence_id: str) -> bool:
    event_rows = conn.execute(
        """
        SELECT source_type, source_id, MIN(created_at) AS first_seen
        FROM diagnostic_evidence
        WHERE user_id=? AND sequence_id=? AND observation_type='dimension'
          AND window_id IS NULL AND strength IN ('certain','probable')
        GROUP BY source_type, source_id ORDER BY first_seen ASC LIMIT 5
        """,
        (user_id, sequence_id),
    ).fetchall()
    if len(event_rows) < 5:
        return False
    source_keys = [f"{row['source_type']}:{row['source_id']}" for row in event_rows]
    clauses = " OR ".join("(source_type=? AND source_id=?)" for _ in event_rows)
    params: list[str] = [user_id, sequence_id]
    for row in event_rows:
        params.extend([row["source_type"], row["source_id"]])
    evidence_rows = conn.execute(
        f"""
        SELECT * FROM diagnostic_evidence
        WHERE user_id=? AND sequence_id=? AND observation_type='dimension'
          AND window_id IS NULL AND strength IN ('certain','probable') AND ({clauses})
        ORDER BY created_at ASC
        """,
        params,
    ).fetchall()
    if not evidence_rows:
        return False

    window_id = str(uuid.uuid4())
    result = _aggregate_dimensions([dict(row) for row in evidence_rows])
    with conn:
        conn.execute(
            """
            INSERT INTO dimension_windows (
                id, user_id, sequence_id, status, event_count, member_source_ids,
                member_evidence_ids, result, projection_version, closed_at
            ) VALUES (?, ?, ?, 'closed', 5, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                window_id, user_id, sequence_id,
                json.dumps(source_keys, ensure_ascii=False),
                json.dumps([row["id"] for row in evidence_rows], ensure_ascii=False),
                json.dumps(result, ensure_ascii=False), PROJECTION_VERSION,
            ),
        )
        conn.executemany(
            "UPDATE diagnostic_evidence SET window_id=? WHERE id=?",
            [(window_id, row["id"]) for row in evidence_rows],
        )
        _apply_dimension_result(conn, window_id, user_id, sequence_id, result)
    return True


def _aggregate_dimensions(rows: list[dict]) -> dict:
    grouped: dict[tuple[str, str], list[tuple[str, float]]] = defaultdict(list)
    for row in rows:
        weight = 1.0 if row["strength"] == "certain" else 0.5
        grouped[(row["dimension"], row["facet"])].append((row["direction"], weight))
    changes: dict[str, dict[str, int]] = defaultdict(dict)
    details = {}
    for (dimension, facet), observations in grouped.items():
        counts = Counter(direction for direction, _ in observations)
        weights = Counter()
        for direction, weight in observations:
            weights[direction] += weight
        change = 0
        if len(observations) >= 3:
            direction, winning_weight = weights.most_common(1)[0]
            total_weight = sum(weights.values())
            if winning_weight >= 2.0 and winning_weight / total_weight >= 2 / 3:
                change = 1 if direction == "positive" else -1
        changes[dimension][facet] = change
        details[f"{dimension}.{facet}"] = {
            "count": len(observations),
            "counts": dict(counts),
            "weights": dict(weights),
            "change": change,
        }
    return {"changes": dict(changes), "details": details}


def _apply_dimension_result(conn, window_id: str, user_id: str, sequence_id: str, result: dict) -> None:
    row = conn.execute("SELECT * FROM math_profiles WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        conn.execute(
            """
            INSERT INTO math_profiles (user_id, baseline_version, projection_version)
            VALUES (?, 'v2', ?)
            """,
            (user_id, PROJECTION_VERSION),
        )
        row = conn.execute("SELECT * FROM math_profiles WHERE user_id=?", (user_id,)).fetchone()
    before, after = {}, {}
    assignments, values = [], []
    for dimension, facets in result.get("changes", {}).items():
        prefix = DIMENSION_COLUMNS.get(dimension)
        if not prefix:
            continue
        for facet, delta in facets.items():
            column = f"{prefix}_{facet}"
            old = int(row[column] or 0)
            new = max(0, min(3, old + int(delta)))
            before[column], after[column] = old, new
            assignments.append(f"{column}=?")
            values.append(new)
    if assignments:
        values.extend([PROJECTION_VERSION, user_id])
        conn.execute(
            f"UPDATE math_profiles SET {', '.join(assignments)}, projection_version=?, "
            "last_diagnosed_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
            values,
        )
    conn.execute(
        """
        INSERT INTO state_projection_log (
            id, window_id, projection_type, projection_key, before_value,
            after_value, projection_version
        ) VALUES (?, ?, 'dimension', ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()), window_id, sequence_id,
            json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
            PROJECTION_VERSION,
        ),
    )
    _save_dimension_assessment(conn, window_id, user_id, sequence_id, result)


def _save_dimension_assessment(conn, window_id: str, user_id: str, sequence_id: str, result: dict) -> None:
    changes = result.get("changes", {})
    values = {}
    for dim in DIMENSION_COLUMNS:
        for facet in ("coverage", "radius", "technical"):
            values[f"{dim}_{facet}"] = int(changes.get(dim, {}).get(facet, 0))
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    conn.execute(
        f"""
        INSERT OR IGNORE INTO question_assessments (
            id, user_id, question_id, {columns}, overall_score,
            weak_points, sequence_id, summary
        ) VALUES (?, ?, 'diagnostic', {placeholders}, 0, '[]', ?, ?)
        """,
        [window_id, user_id, *values.values(), sequence_id, "V2同章节五事件素养聚合"],
    )
