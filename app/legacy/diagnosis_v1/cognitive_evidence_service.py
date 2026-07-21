"""构造并保存认知证据。"""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, replace
from datetime import datetime

from app.services.diagnosis.contracts import CognitiveEvidence


def persist_evidence_items(evidence_items: list[CognitiveEvidence], max_items_per_concept: int = 20) -> None:
    """把证据追加到 `knowledge_stages.evidence`。

    该函数不直接改变 stage，只轻微提高 confidence，并为后续诊断保留原话。
    """

    if not evidence_items:
        return

    from app.db.connection import get_conn

    conn = get_conn()
    now = datetime.utcnow().isoformat()
    try:
        with conn:
            for evidence in evidence_items:
                row = conn.execute(
                    "SELECT id, stage, confidence, evidence FROM knowledge_stages WHERE user_id=? AND concept_name=?",
                    (evidence.user_id, evidence.concept_name),
                ).fetchone()

                if row:
                    ks_id = row["id"]
                    stage_before = row["stage"]
                    confidence = row["confidence"] if row["confidence"] is not None else 0.3
                    existing = _loads_evidence(row["evidence"])
                else:
                    ks_id = str(uuid.uuid4())
                    stage_before = None
                    confidence = 0.3
                    existing = []
                    conn.execute(
                        """INSERT OR IGNORE INTO knowledge_stages
                           (id, user_id, concept_name, stage, confidence, evidence, last_updated)
                           VALUES (?, ?, ?, NULL, ?, '[]', ?)""",
                        (ks_id, evidence.user_id, evidence.concept_name, confidence, now),
                    )

                enriched = replace(
                    evidence,
                    stage_before=evidence.stage_before if evidence.stage_before is not None else stage_before,
                    stage_after=evidence.stage_after if evidence.stage_after is not None else stage_before,
                )
                existing.append(_compact_evidence(enriched))
                existing = existing[-max_items_per_concept:]
                confidence = max(0.0, min(1.0, confidence + (evidence.confidence_delta or 0.0)))

                conn.execute(
                    """UPDATE knowledge_stages
                       SET evidence=?, confidence=?, last_updated=CURRENT_TIMESTAMP
                       WHERE id=?""",
                    (json.dumps(existing, ensure_ascii=False), confidence, ks_id),
                )
    finally:
        conn.close()


def _loads_evidence(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return value if isinstance(value, list) else []
    except Exception:
        return []


def _compact_evidence(evidence: CognitiveEvidence) -> dict:
    data = asdict(evidence)
    data["created_at"] = datetime.utcnow().isoformat()
    return data


def _summarize(answer: str, limit: int = 180) -> str:
    text = " ".join((answer or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."
