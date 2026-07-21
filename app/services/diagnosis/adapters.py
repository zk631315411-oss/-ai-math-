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
    previous = get_previous_qa_turn(current)
    sequence_id = current.get("sequence_id") or ""
    textbook_id = current.get("textbook_id") or ""
    history_answer = _last_assistant_text(current.get("context_snapshot") or {})
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
        previous_ai_answer=(previous or {}).get("answer") or history_answer,
        previous_apprenticeship_level=(previous or {}).get("apprenticeship_level"),
        kg_candidates=[node.name for node in kg_nodes],
        kg_candidate_nodes=kg_nodes,
        kg_candidate_relations=kg_relations,
        behavior_hints=detect_qa_behavior_hints(current.get("question") or ""),
        created_at=current.get("created_at"),
        context_snapshot=current.get("context_snapshot") or {},
    )


def adapt_exercise_attempt(row: dict) -> ExerciseEvidenceInput:
    attempt = unpack_exercise_attempt(row)
    return ExerciseEvidenceInput(
        attempt_id=attempt["id"],
        exercise_id=attempt["exercise_id"],
        user_id=attempt["user_id"],
        sequence_id=attempt.get("sequence_id") or "",
        target_concept=attempt.get("target_concept") or "",
        target_stage=attempt.get("target_stage"),
        difficulty=attempt.get("difficulty") or "",
        question=attempt.get("question") or "",
        student_answer=attempt.get("student_answer") or "",
        correct_answer=attempt.get("correct_answer") or "",
        is_correct=bool(attempt.get("is_correct")),
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


def _last_assistant_text(context_snapshot: dict) -> str:
    history = context_snapshot.get("history") if isinstance(context_snapshot, dict) else None
    if not isinstance(history, list):
        return ""
    for item in reversed(history):
        if not isinstance(item, dict):
            continue
        value = item.get("assistant") or item.get("answer")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
