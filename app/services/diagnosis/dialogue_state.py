"""Shadow ordinal Bayesian state for conversation-based diagnosis.

This module intentionally does not read or write ``knowledge_stages``.  It is
an auditable, opt-in shadow consumer of validated QA stage evidence.
"""

from __future__ import annotations

import json
import math
import uuid
from typing import Any

from app.config import config
from app.db.connection import get_conn


STAGES = tuple(range(6))
DEFAULT_MODEL_VERSION = "ordinal-bayes-v1"
STRENGTH_WEIGHTS = {"certain": 1.0, "probable": 0.5, "hypothesis": 0.0}
ASSISTANCE_WEIGHTS = {
    "fading": 1.0,
    "scaffolding": 0.7,
    "coaching": 0.5,
    "modeling": 0.25,
    "unknown": 0.5,
}


def dialogue_state_mode() -> str:
    mode = (config.DIALOGUE_STATE_MODE or "shadow").lower()
    return mode if mode in {"off", "shadow"} else "shadow"


def model_version() -> str:
    return config.DIALOGUE_STATE_MODEL_VERSION or DEFAULT_MODEL_VERSION


def project_pending_dialogue_states(limit: int = 100, user_id: str | None = None) -> int:
    """Project pending QA stage evidence exactly once in event order."""
    if dialogue_state_mode() == "off":
        return 0
    conn = get_conn()
    try:
        user_filter = " AND e.user_id=?" if user_id else ""
        params: list[Any] = []
        if user_id:
            params.append(user_id)
        params.append(model_version())
        params.append(limit)
        rows = conn.execute(
            f"""
            SELECT e.*
            FROM diagnostic_evidence e
            WHERE e.source_type='qa_turn'
              AND e.observation_type='stage'
              {user_filter}
              AND NOT EXISTS (
                SELECT 1 FROM dialogue_state_projection_log p
                WHERE p.evidence_id=e.id AND p.model_version=?
              )
            ORDER BY e.created_at ASC, e.id ASC
            LIMIT ?
            """,
            params,
        ).fetchall()
        evidence = [dict(row) for row in rows]
    finally:
        conn.close()

    count = 0
    for row in evidence:
        if project_dialogue_evidence(row):
            count += 1
    return count


def project_dialogue_evidence(evidence: dict[str, Any]) -> bool:
    """Apply one evidence row, including an auditable abstention decision."""
    if dialogue_state_mode() == "off":
        return False

    version = model_version()
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        processed = _project_dialogue_evidence(conn, evidence, version)
        conn.commit()
        return processed
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def replay_dialogue_states(user_id: str | None = None) -> int:
    """Rebuild each user's model version atomically in chronological order."""
    if dialogue_state_mode() == "off":
        return 0
    version = model_version()
    users = [user_id] if user_id else _dialogue_state_users(version)
    return sum(_replay_user_dialogue_states(item, version) for item in users)


def _dialogue_state_users(version: str) -> list[str]:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT user_id FROM diagnostic_evidence
            WHERE source_type='qa_turn' AND observation_type='stage'
            UNION
            SELECT user_id FROM dialogue_knowledge_states WHERE model_version=?
            UNION
            SELECT user_id FROM dialogue_state_projection_log WHERE model_version=?
            ORDER BY user_id
            """,
            (version, version),
        ).fetchall()
        return [row["user_id"] for row in rows if row["user_id"]]
    finally:
        conn.close()


def _replay_user_dialogue_states(user_id: str, version: str) -> int:
    conn = get_conn()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "DELETE FROM dialogue_state_projection_log WHERE model_version=? AND user_id=?",
            (version, user_id),
        )
        conn.execute(
            "DELETE FROM dialogue_knowledge_states WHERE model_version=? AND user_id=?",
            (version, user_id),
        )
        rows = conn.execute(
            """
            SELECT * FROM diagnostic_evidence
            WHERE source_type='qa_turn' AND observation_type='stage' AND user_id=?
            ORDER BY created_at ASC, id ASC
            """,
            (user_id,),
        ).fetchall()
        count = sum(
            _project_dialogue_evidence(conn, dict(row), version) for row in rows
        )
        conn.commit()
        return count
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _project_dialogue_evidence(conn, evidence: dict[str, Any], version: str) -> bool:
    existing = conn.execute(
        """
        SELECT 1 FROM dialogue_state_projection_log
        WHERE evidence_id=? AND model_version=?
        """,
        (evidence["id"], version),
    ).fetchone()
    if existing:
        return False

    payload, payload_valid = _decode_payload(evidence.get("payload"))
    concept_id = str(payload.get("concept_id") or evidence.get("concept_name") or "").strip()
    concept_name = str(evidence.get("concept_name") or concept_id).strip()
    before = _get_distribution(conn, evidence.get("user_id") or "", concept_id, version)
    decision, reason = _decision(evidence, payload, concept_id, payload_valid=payload_valid)

    if decision != "accepted":
        _write_log(
            conn,
            evidence=evidence,
            concept_id=concept_id,
            before=before,
            likelihood=[1.0] * len(STAGES),
            after=before,
            effective_weight=0.0,
            action=f"{decision}:{reason}",
            version=version,
        )
        return True

    observed_stage = int(evidence["observed_stage"])
    likelihood = _likelihood(observed_stage, evidence["direction"])
    strength_weight = STRENGTH_WEIGHTS[evidence["strength"]]
    support_level = str(evidence.get("support_level") or "unknown").lower()
    assistance_weight = ASSISTANCE_WEIGHTS[support_level]
    effective_weight = strength_weight * assistance_weight
    after = _update(before, likelihood, effective_weight)
    map_stage = min(stage for stage in STAGES if after[stage] == max(after))
    expected_stage = sum(stage * after[stage] for stage in STAGES)
    confidence = _confidence(after)

    conn.execute(
        """
        INSERT INTO dialogue_knowledge_states (
            user_id, concept_id, concept_name, probabilities_json,
            map_stage, expected_stage, confidence, evidence_count,
            last_evidence_id, model_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        ON CONFLICT(user_id, concept_id, model_version) DO UPDATE SET
            concept_name=excluded.concept_name,
            probabilities_json=excluded.probabilities_json,
            map_stage=excluded.map_stage,
            expected_stage=excluded.expected_stage,
            confidence=excluded.confidence,
            evidence_count=dialogue_knowledge_states.evidence_count + 1,
            last_evidence_id=excluded.last_evidence_id,
            updated_at=CURRENT_TIMESTAMP
        """,
        (
            evidence["user_id"], concept_id, concept_name, _dump_distribution(after),
            map_stage, expected_stage, confidence, evidence["id"], version,
        ),
    )
    _write_log(
        conn,
        evidence=evidence,
        concept_id=concept_id,
        before=before,
        likelihood=likelihood,
        after=after,
        effective_weight=effective_weight,
        action="accepted",
        version=version,
    )
    return True


def get_dialogue_state(user_id: str, concept_id: str) -> dict[str, Any] | None:
    conn = get_conn()
    try:
        row = conn.execute(
            """
            SELECT * FROM dialogue_knowledge_states
            WHERE user_id=? AND concept_id=? AND model_version=?
            """,
            (user_id, concept_id, model_version()),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["probabilities"] = _payload(result.pop("probabilities_json"))
        return result
    finally:
        conn.close()


def _decision(
    evidence: dict[str, Any],
    payload: dict[str, Any],
    concept_id: str,
    *,
    payload_valid: bool = True,
) -> tuple[str, str]:
    if not payload_valid:
        return "rejected", "invalid_payload"
    if evidence.get("source_type") != "qa_turn" or evidence.get("observation_type") != "stage":
        return "rejected", "non_qa_stage"
    if not evidence.get("user_id") or not concept_id or not evidence.get("concept_name"):
        return "rejected", "missing_concept"
    if evidence.get("direction") not in {"positive", "negative"}:
        return "rejected", "invalid_direction"
    try:
        stage = int(evidence.get("observed_stage"))
    except (TypeError, ValueError):
        return "rejected", "invalid_stage"
    if stage not in STAGES:
        return "rejected", "invalid_stage"

    projection_role = payload.get("projection_role", "primary")
    behavior = str(evidence.get("behavior") or "").lower()
    strength = str(evidence.get("strength") or "").lower()
    support = str(evidence.get("support_level") or "unknown").lower()
    if projection_role not in {"primary", "supporting"}:
        return "rejected", "invalid_projection_role"
    if behavior not in {
        "question_only", "self_report", "definition_recall", "solution_attempt",
        "explanation", "proof", "counterexample", "transfer",
    }:
        return "rejected", "invalid_behavior"
    if strength not in STRENGTH_WEIGHTS:
        return "rejected", "invalid_strength"
    if support not in ASSISTANCE_WEIGHTS:
        return "rejected", "invalid_support_level"
    try:
        overlap = float(payload.get("assistant_overlap") or 0.0)
    except (TypeError, ValueError):
        return "rejected", "invalid_assistant_overlap"
    if not math.isfinite(overlap) or not 0.0 <= overlap <= 1.0:
        return "rejected", "invalid_assistant_overlap"
    action = payload.get("dialogue_state_action")
    reason = payload.get("dialogue_state_reason")
    rationale = payload.get("dialogue_state_rationale")
    if action is not None and action not in {"accepted", "abstained"}:
        return "rejected", "invalid_dialogue_state_action"
    if action is not None and reason not in {
        "independent_evidence", "ai_dependent", "question_only",
        "self_report", "insufficient_context",
    }:
        return "rejected", "invalid_dialogue_state_reason"
    if action is not None and (not isinstance(rationale, str) or not rationale.strip()):
        return "rejected", "invalid_dialogue_state_rationale"
    if action == "accepted" and (reason != "independent_evidence" or strength == "hypothesis"):
        return "rejected", "contradictory_model_decision"
    if action == "abstained" and reason == "independent_evidence":
        return "rejected", "contradictory_model_decision"
    if projection_role == "supporting":
        return "abstained", "supporting_evidence"
    if action is None:
        return "abstained", "legacy_missing_decision"
    if action == "accepted":
        return "accepted", reason
    return "abstained", reason


def _likelihood(observed_stage: int, direction: str) -> list[float]:
    values = []
    for stage in STAGES:
        if direction == "positive":
            distance = (
                max(observed_stage - stage, 0) / 0.75
                + max(stage - observed_stage, 0) / 2.0
            )
        else:
            distance = (
                max(stage - observed_stage, 0) / 0.75
                + max(observed_stage - stage, 0) / 2.0
            )
        values.append(math.exp(-distance))
    return values


def _update(prior: list[float], likelihood: list[float], weight: float) -> list[float]:
    weighted = [p * (l ** weight) for p, l in zip(prior, likelihood)]
    total = sum(weighted)
    if not math.isfinite(total) or total <= 0:
        return list(prior)
    return [value / total for value in weighted]


def _get_distribution(conn, user_id: str, concept_id: str, version: str) -> list[float]:
    row = conn.execute(
        """
        SELECT probabilities_json FROM dialogue_knowledge_states
        WHERE user_id=? AND concept_id=? AND model_version=?
        """,
        (user_id, concept_id, version),
    ).fetchone()
    if not row:
        return [1.0 / len(STAGES)] * len(STAGES)
    raw = _payload(row["probabilities_json"])
    values = raw if isinstance(raw, list) else raw.get("values")
    if not isinstance(values, list) or len(values) != len(STAGES):
        return [1.0 / len(STAGES)] * len(STAGES)
    try:
        values = [float(value) for value in values]
    except (TypeError, ValueError):
        return [1.0 / len(STAGES)] * len(STAGES)
    total = sum(values)
    if total <= 0 or not all(math.isfinite(value) and value >= 0 for value in values):
        return [1.0 / len(STAGES)] * len(STAGES)
    return [value / total for value in values]


def _confidence(values: list[float]) -> float:
    entropy = -sum(value * math.log(value) for value in values if value > 0)
    return max(0.0, min(1.0, 1.0 - entropy / math.log(len(STAGES))))


def _dump_distribution(values: list[float]) -> str:
    return json.dumps([round(float(value), 12) for value in values], ensure_ascii=False)


def _payload(raw: Any) -> Any:
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


def _decode_payload(raw: Any) -> tuple[dict[str, Any], bool]:
    if isinstance(raw, dict):
        return raw, True
    if not isinstance(raw, str):
        return {}, False
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}, False
    return (value, True) if isinstance(value, dict) else ({}, False)


def _write_log(
    conn,
    *,
    evidence: dict[str, Any],
    concept_id: str,
    before: list[float],
    likelihood: list[float],
    after: list[float],
    effective_weight: float,
    action: str,
    version: str,
) -> None:
    conn.execute(
        """
        INSERT INTO dialogue_state_projection_log (
            id, evidence_id, user_id, concept_id, before_distribution,
            likelihood, after_distribution, effective_weight, action, model_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            evidence["id"],
            evidence.get("user_id") or "",
            concept_id,
            _dump_distribution(before),
            _dump_distribution(likelihood),
            _dump_distribution(after),
            effective_weight,
            action,
            version,
        ),
    )
