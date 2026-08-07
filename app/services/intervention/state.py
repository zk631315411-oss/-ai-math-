"""Build stable diagnosis snapshots and QA-facing student state."""

from __future__ import annotations

import json

from app.db.connection import get_conn
from app.db.diagnosis_v2_db import save_signals
from app.services.diagnosis.contracts import DiagnosticSignal, StudentStateSummary, WeakPrerequisite
from app.services.intervention import repository as repo


PRACTICE_REQUEST_MARKERS = (
    "\u51fa\u9898", "\u7ec3\u4e60", "\u7c7b\u4f3c\u9898", "\u53d8\u5f0f\u9898",
)


def publish_snapshot(source_type: str, source_id: str) -> dict | None:
    source = _load_source(source_type, source_id)
    if not source:
        return None
    signals = repo.list_signals_for_source(source_type, source_id)
    if not signals:
        save_signals(_fallback_signals(source))
        signals = repo.list_signals_for_source(source_type, source_id)
    state_payload = _state_payload(source["user_id"], source["concept_ids"], source["prerequisite_ids"], signals)
    snapshot = repo.create_snapshot(
        user_id=source["user_id"], source_type=source_type, source_id=source_id,
        tree_id=source["tree_id"], node_id=source["node_id"],
        textbook_id=source["textbook_id"], sequence_id=source["sequence_id"],
        concept_ids=source["concept_ids"], state_payload=state_payload,
        signal_ids=[item["id"] for item in signals],
    )
    from app.services.intervention.worker import intervention_worker
    intervention_worker.enqueue_snapshot(snapshot["id"])
    return snapshot


def load_student_state(user_id: str, *, tree_id: str = "", node_id: str = "",
                       sequence_id: str = "", concept_ids: list[str] | None = None,
                       prerequisite_ids: list[str] | None = None) -> StudentStateSummary:
    snapshot = repo.latest_snapshot(
        user_id, tree_id=tree_id, node_id=node_id, sequence_id=sequence_id,
        concept_ids=concept_ids or [],
    )
    payload = snapshot.get("state_payload", {}) if snapshot else _state_payload(
        user_id, concept_ids or [], prerequisite_ids or [], [],
    )
    weak = [
        WeakPrerequisite(
            name=str(item.get("name") or ""), stage=item.get("stage"),
            evidence=str(item.get("evidence") or ""), confidence=item.get("confidence"),
        )
        for item in payload.get("weak_prerequisites", []) if isinstance(item, dict)
    ]
    return StudentStateSummary(
        user_id=user_id,
        current_section_stage=payload.get("current_section_stage"),
        related_concept_stages=payload.get("related_concept_stages", {}),
        weak_prerequisites=weak,
        recent_pattern=str(payload.get("recent_pattern") or ""),
        likely_breakpoint=str(payload.get("likely_breakpoint") or ""),
        teaching_policy_hint=str(payload.get("teaching_policy_hint") or ""),
        raw={"snapshot_id": snapshot.get("id") if snapshot else None, **payload},
    )


def _load_source(source_type: str, source_id: str) -> dict | None:
    conn = get_conn()
    try:
        if source_type == "qa_turn":
            row = conn.execute("SELECT * FROM qa_turn_records WHERE id=?", (source_id,)).fetchone()
            if not row:
                return None
            item = dict(row)
            context = _loads(item.get("context_snapshot"), {})
            grounding = context.get("grounding", {}) if isinstance(context, dict) else {}
            input_context = context.get("input_context", {}) if isinstance(context, dict) else {}
            related = grounding.get("related_concepts", []) or []
            prereqs = grounding.get("prerequisite_concepts", []) or []
            return {
                "user_id": item["user_id"], "source_type": source_type, "source_id": source_id,
                "student_text": item.get("question") or "", "tree_id": input_context.get("tree_id") or "",
                "node_id": input_context.get("node_id") or "", "textbook_id": item.get("textbook_id") or "",
                "sequence_id": item.get("sequence_id") or "",
                "concept_ids": _concept_values(related), "prerequisite_ids": _concept_values(prereqs),
            }
        row = conn.execute(
            """SELECT p.*,i.textbook_id,i.sequence_id,i.concept_ids,d.tree_id,d.node_id,d.context_snapshot
               FROM practice_attempts p JOIN exercise_items i ON i.id=p.item_id
               JOIN practice_drafts d ON d.id=p.draft_id WHERE p.id=?""",
            (source_id,),
        ).fetchone()
        if row:
            item = dict(row)
            context = _loads(item.get("context_snapshot"), {})
            return {
                "user_id": item["user_id"], "source_type": source_type, "source_id": source_id,
                "student_text": item.get("student_answer") or "", "tree_id": item.get("tree_id") or "",
                "node_id": item.get("node_id") or "", "textbook_id": item.get("textbook_id") or "",
                "sequence_id": item.get("sequence_id") or "",
                "concept_ids": _loads(item.get("concept_ids"), []),
                "prerequisite_ids": context.get("prerequisite_concept_ids", []) or [],
            }
        legacy = conn.execute("SELECT * FROM exercise_attempts WHERE id=?", (source_id,)).fetchone()
        if not legacy:
            return None
        item = dict(legacy)
        return {
            "user_id": item["user_id"], "source_type": source_type, "source_id": source_id,
            "student_text": item.get("student_answer") or "", "tree_id": "", "node_id": "",
            "textbook_id": "", "sequence_id": item.get("sequence_id") or "",
            "concept_ids": [item.get("target_concept")] if item.get("target_concept") else [],
            "prerequisite_ids": [],
        }
    finally:
        conn.close()


def _state_payload(user_id: str, concept_ids: list[str], prerequisite_ids: list[str],
                   signals: list[dict]) -> dict:
    names = list(dict.fromkeys([*concept_ids, *prerequisite_ids]))
    stages: dict[str, int | None] = {name: None for name in names}
    confidences: dict[str, float | None] = {name: None for name in names}
    conn = get_conn()
    try:
        if names:
            placeholders = ",".join("?" for _ in names)
            rows = conn.execute(
                f"SELECT concept_name,stage,confidence FROM knowledge_stages WHERE user_id=? AND concept_name IN ({placeholders})",
                [user_id, *names],
            ).fetchall()
            for row in rows:
                stages[row["concept_name"]] = row["stage"]
                confidences[row["concept_name"]] = row["confidence"]
    finally:
        conn.close()
    known = [stages[name] for name in concept_ids if stages.get(name) is not None]
    current_stage = round(sum(known) / len(known)) if known else None
    weak = [
        {"name": name, "stage": stages.get(name), "confidence": confidences.get(name), "evidence": "diagnosis_v2"}
        for name in prerequisite_ids if stages.get(name) is not None and int(stages[name]) <= 2
    ]
    strongest = max(signals, key=lambda item: float(item.get("confidence") or 0), default={})
    return {
        "current_section_stage": current_stage,
        "related_concept_stages": {name: stages.get(name) for name in concept_ids},
        "weak_prerequisites": weak,
        "recent_pattern": strongest.get("signal_type", ""),
        "likely_breakpoint": strongest.get("rationale") or strongest.get("student_quote", ""),
        "teaching_policy_hint": "use_evidence_bounded_directive" if strongest else "",
    }


def _fallback_signals(source: dict) -> list[DiagnosticSignal]:
    text = source.get("student_text") or ""
    if source["source_type"] == "qa_turn" and any(marker in text for marker in PRACTICE_REQUEST_MARKERS):
        return [DiagnosticSignal(
            source_type="qa_turn", source_id=source["source_id"], user_id=source["user_id"],
            sequence_id=source["sequence_id"], signal_type="practice_request",
            concept_ids=source["concept_ids"][:3], student_quote=text[:500], confidence=0.7,
            strength="probable", rationale="The student explicitly requested practice.",
        )]
    return []


def _concept_values(items: list) -> list[str]:
    result = []
    for item in items:
        if isinstance(item, dict):
            value = item.get("node_id") or item.get("name")
        else:
            value = getattr(item, "node_id", None) or getattr(item, "name", None)
        if value:
            result.append(str(value))
    return list(dict.fromkeys(result))[:12]


def _loads(value, default):
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, json.JSONDecodeError):
        return default
