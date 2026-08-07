"""Shared diagnosis lookups plus V2 compatibility entrypoints."""

from __future__ import annotations

import json
import re
from typing import Any

from app.textbooks import canonical_textbook_id, section_node_id
from app.services.diagnosis.contracts import (
    CognitiveEvidence,
    DiagnosticCard,
    KGStageNode,
    KGStageRelation,
)


def get_concepts_by_sequence_id(sequence_id: str, textbook_id: str = "") -> list[str]:
    nodes, _ = get_stage_candidates_by_sequence_id(sequence_id, textbook_id)
    return [node.name for node in nodes]


def get_stage_candidates_by_sequence_id(
    sequence_id: str,
    textbook_id: str = "",
) -> tuple[list[KGStageNode], list[KGStageRelation]]:
    if not textbook_id:
        return [], []
    canonical = canonical_textbook_id(textbook_id)
    try:
        from app.db.kg_v44 import nodes_for_section, relations_between_nodes

        node_rows = nodes_for_section(section_node_id(canonical, sequence_id), limit=60)
        nodes: list[KGStageNode] = []
        seen_names: set[str] = set()
        for row in node_rows:
            name = str(row.get("name") or "").strip()
            node_id = str(row.get("node_id") or "")
            if not name or not node_id or name in seen_names:
                continue
            seen_names.add(name)
            nodes.append(KGStageNode(
                node_id=node_id,
                name=name,
                node_type=str(row.get("type") or ""),
            ))
            if len(nodes) >= 40:
                break
        try:
            relation_rows = relations_between_nodes([node.node_id for node in nodes])
        except Exception as exc:
            print(f"[CognitiveDiagnosis] candidate relation lookup failed: {exc}")
            relation_rows = []
        relations = [
            KGStageRelation(
                source_node_id=str(row.get("source_node_id") or ""),
                source_name=str(row.get("source_name") or ""),
                rel_type=str(row.get("rel_type") or ""),
                target_node_id=str(row.get("target_node_id") or ""),
                target_name=str(row.get("target_name") or ""),
            )
            for row in relation_rows
            if row.get("source_node_id") and row.get("target_node_id")
        ]
        return nodes, relations
    except Exception as exc:
        print(f"[CognitiveDiagnosis] get_stage_candidates_by_sequence_id failed: {exc}")
        return [], []


def get_prerequisite_chain(topic: str) -> list[str]:
    try:
        from app.db.kg_v44 import related_nodes

        support_nodes, extension_nodes = related_nodes(topic, limit=8)
        return _unique_names([*support_nodes, *extension_nodes], limit=10)
    except Exception as exc:
        print(f"[CognitiveDiagnosis] related_nodes failed: {exc}")
        return []


def get_user_recent_chats(user_id: str, topic: str, limit: int = 5) -> list[dict]:
    try:
        from app.db.chat_history_db import get_chat_history

        chats = get_chat_history(user_id, limit=100)
        relevant = [
            chat for chat in chats
            if topic in chat.get("question", "") or topic in chat.get("answer", "")
        ]
        selected = (relevant or chats)[:limit]
        return [
            {"question": chat.get("question", ""), "answer": chat.get("answer", "")}
            for chat in selected
        ]
    except Exception as exc:
        print(f"[CognitiveDiagnosis] get_user_recent_chats failed: {exc}")
        return []


async def run_diagnostic_pipeline(
    user_id: str,
    topic: str = "",
    sequence_id: str = "",
    textbook_id: str = "",
    **_: object,
) -> bool:
    from app.services.diagnostic_worker import run_diagnostic_batch

    return await run_diagnostic_batch(user_id)


async def trigger_diagnostic_if_needed(
    user_id: str,
    topic: str = "",
    sequence_id: str = "",
    textbook_id: str = "",
) -> None:
    from app.services.diagnostic_worker import run_diagnostic_batch

    await run_diagnostic_batch(user_id)


def should_trigger_diagnostic(
    user_id: str,
    topic: str = "",
    consecutive_turns: int = 0,
    total_asks: int = 0,
) -> bool:
    from app.services.diagnostic_worker import should_trigger_diagnostic_batch

    return should_trigger_diagnostic_batch(user_id)


def save_diagnostic_result(**_: object) -> None:
    raise RuntimeError("V2 禁止直接保存混合诊断结果；请通过证据账本和投影器更新画像")


def extract_dimension_scores(_: dict) -> dict:
    return {}


def validate_concept_ids(diagnostic_data: dict[str, Any], kg_candidates: list[str]) -> bool:
    """Legacy output validator retained for imports and historical tests."""

    if not kg_candidates:
        return not (
            diagnostic_data.get("weak_concepts") or diagnostic_data.get("concept_stages")
        )
    allowed = set(kg_candidates)
    weak = diagnostic_data.get("weak_concepts") or []
    stages = diagnostic_data.get("concept_stages") or []
    return all(item in allowed for item in weak) and all(
        isinstance(item, dict) and item.get("name") in allowed for item in stages
    )


def parse_diagnostic_json(raw_output: str) -> dict[str, Any] | None:
    if not raw_output:
        return None
    try:
        value = json.loads(raw_output)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw_output)
        if not match:
            return None
        try:
            value = json.loads(match.group())
        except json.JSONDecodeError:
            return None
    return value if isinstance(value, dict) else None


def build_minimal_diagnostic_card(evidence: CognitiveEvidence, stage: int | None = None) -> DiagnosticCard:
    return DiagnosticCard(
        concept_name=evidence.concept_name,
        stage=stage,
        title=f"{evidence.concept_name} 的当前状态",
        evidence_quote=evidence.quote,
        diagnosis=evidence.diagnosis,
        textbook_id=evidence.textbook_id,
        sequence_id=evidence.sequence_id,
        source_code=evidence.source_code,
        evidence_span=evidence.evidence_span,
        recommended_action="结合后续独立作答继续验证长期状态。",
    )


def _unique_names(nodes: list[Any], limit: int) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        if isinstance(node, dict):
            name = str(node.get("name") or node.get("title") or "").strip()
        else:
            name = str(getattr(node, "name", "") or "").strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
            if len(names) >= limit:
                break
    return names
