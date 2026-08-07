"""Source-specific adapters for diagnosis V2."""

from __future__ import annotations

import re

from app.db.diagnosis_v2_db import get_previous_qa_turn, unpack_exercise_attempt, unpack_qa_row
from app.services.diagnosis.contracts import (
    ExerciseEvidenceInput,
    KGStageNode,
    KGStageRelation,
    LearningBehavior,
    QAEvidenceInput,
)
from app.services.diagnosis.diagnosis_service import get_stage_candidates_by_sequence_id


def adapt_qa_turn(row: dict) -> QAEvidenceInput:
    current = unpack_qa_row(row)
    sequence_id = current.get("sequence_id") or ""
    textbook_id = current.get("textbook_id") or ""
    context_snapshot = current.get("context_snapshot") or {}
    recent_history = _normalize_recent_history(context_snapshot)
    input_context = (
        context_snapshot.get("input_context", {})
        if isinstance(context_snapshot, dict) else {}
    )
    tree_backed = isinstance(input_context, dict) and any(
        input_context.get(field)
        for field in ("tree_id", "node_id", "fork_message_id")
    )
    previous = None if recent_history or tree_backed else get_previous_qa_turn(current)
    history_answer = _last_assistant_text(recent_history)
    kg_nodes, kg_relations = (
        get_stage_candidates_by_sequence_id(sequence_id, textbook_id)
        if sequence_id else ([], [])
    )
    return QAEvidenceInput(
        turn_id=current["id"],
        user_id=current["user_id"],
        chat_id=current.get("chat_id"),
        sequence_id=sequence_id,
        textbook_id=textbook_id,
        student_text=current.get("question") or "",
        previous_ai_answer=history_answer or (previous or {}).get("answer") or "",
        previous_apprenticeship_level=(previous or {}).get("apprenticeship_level"),
        kg_candidates=[node.name for node in kg_nodes],
        kg_candidate_nodes=kg_nodes,
        kg_candidate_relations=kg_relations,
        behavior_hints=detect_qa_behavior_hints(current.get("question") or ""),
        created_at=current.get("created_at"),
        context_snapshot=context_snapshot,
        recent_history=recent_history,
    )


def adapt_exercise_attempt(row: dict) -> ExerciseEvidenceInput:
    attempt = unpack_exercise_attempt(row)
    verdict = attempt.get("verdict") or ("correct" if attempt.get("is_correct") else "incorrect")
    concept_ids = attempt.get("concept_ids") or []
    if not concept_ids and attempt.get("target_concept"):
        concept_ids = [attempt["target_concept"]]
    return ExerciseEvidenceInput(
        attempt_id=attempt["id"],
        exercise_id=attempt["exercise_id"],
        user_id=attempt["user_id"],
        sequence_id=attempt.get("sequence_id") or "",
        target_concept=attempt.get("target_concept") or "",
        target_stage=attempt.get("target_stage"),
        diagnostic_goal=attempt.get("diagnostic_goal") or "application",
        difficulty=attempt.get("difficulty") or "",
        question=attempt.get("question") or "",
        student_answer=attempt.get("student_answer") or "",
        correct_answer=attempt.get("correct_answer") or "",
        is_correct=bool(attempt.get("is_correct")),
        verdict=verdict if verdict in {"correct", "partial", "incorrect", "ungradable"} else "incorrect",
        concept_ids=concept_ids,
        hint_level=int(attempt.get("hint_level") or 0),
        grading_feedback=attempt.get("grading_feedback") or "",
        error_analysis=attempt.get("error_analysis") or {},
        grader_version=attempt.get("grader_version") or "",
        created_at=attempt.get("created_at"),
    )


def exercise_kg_context(
    event: ExerciseEvidenceInput,
) -> tuple[list[KGStageNode], list[KGStageRelation]]:
    if not event.sequence_id:
        return [], []
    return get_stage_candidates_by_sequence_id(event.sequence_id)


def exercise_kg_candidates(event: ExerciseEvidenceInput) -> list[str]:
    """Compatibility wrapper for callers that only need the concept whitelist."""

    nodes, _ = exercise_kg_context(event)
    return [node.name for node in nodes]


def detect_qa_behavior_hints(text: str) -> list[LearningBehavior]:
    """Cheap hints for the LLM; final behavior is still validated from student text."""

    normalized = " ".join((text or "").split())
    hints: list[LearningBehavior] = []
    is_question = (
        "?" in normalized
        or "？" in normalized
        or normalized.startswith(("为什么", "怎么", "如何", "什么", "能否", "是不是"))
    )
    is_request = normalized.startswith((
        "请证明", "证明一下", "帮我证明", "帮我", "请问", "给出证明", "求证", "解释一下",
    ))
    has_reasoning = any(token in normalized for token in ("因为", "所以", "因此", "由此", "可得", "故"))
    if (is_question or is_request) and not has_reasoning:
        return ["question_only"]
    if any(token in normalized for token in ("定义是", "是指", "称为")):
        hints.append("definition_recall")
    if has_reasoning or ("证明" in normalized and not is_question):
        hints.append("proof")
    if any(token in normalized for token in ("反例", "例如取", "举例")):
        hints.append("counterexample")
    if any(token in normalized for token in ("一般地", "推广", "类似地", "换成")):
        hints.append("transfer")
    if re.search(r"[=<>≤≥]|\\(?:frac|sum|int)|\d+[+\-*/]\d+", normalized):
        hints.append("solution_attempt")
    if not hints:
        hints.append("question_only" if "?" in normalized or "？" in normalized else "self_report")
    return hints


def _last_assistant_text(history: list[dict[str, str]]) -> str:
    for item in reversed(history):
        value = item.get("assistant")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_recent_history(context_snapshot: dict) -> list[dict[str, str]]:
    """Return up to three usable turns from the server-owned branch snapshot."""

    history = context_snapshot.get("history") if isinstance(context_snapshot, dict) else None
    if not isinstance(history, list):
        return []

    turns: list[dict[str, str]] = []
    pending_user = ""
    for item in history:
        if not isinstance(item, dict) or _failed_history_item(item):
            continue

        if "role" in item:
            role = str(item.get("role") or "").lower()
            content = _clean_history_text(item.get("content"))
            if role == "user" and content:
                if pending_user:
                    turns.append({"user": pending_user, "assistant": ""})
                pending_user = content
            elif role == "assistant" and content:
                if pending_user:
                    turns.append({"user": pending_user, "assistant": content})
                    pending_user = ""
                elif turns and not turns[-1]["assistant"]:
                    turns[-1]["assistant"] = content
            continue

        user = _clean_history_text(item.get("user") or item.get("question"))
        assistant = _clean_history_text(item.get("assistant") or item.get("answer"))
        if user.startswith("[用户显式引用的其他分支回答]"):
            continue
        if user or assistant:
            turns.append({"user": user, "assistant": assistant})

    if pending_user:
        turns.append({"user": pending_user, "assistant": ""})
    return turns[-3:]


def _failed_history_item(item: dict) -> bool:
    status = str(item.get("status") or "").lower()
    return bool(item.get("error")) or status in {"failed", "error", "cancelled"}


def _clean_history_text(value) -> str:
    return value.strip() if isinstance(value, str) else ""
