"""Immutable contracts shared by diagnosis, QA, and practice."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


InterventionAction = Literal[
    "no_action", "adjust_qa", "offer_practice_entry", "prepare_practice"
]


@dataclass(frozen=True)
class DiagnosisSnapshot:
    snapshot_id: str
    user_id: str
    source_type: Literal["qa_turn", "exercise_attempt"]
    source_id: str
    tree_id: str = ""
    node_id: str = ""
    textbook_id: str = ""
    sequence_id: str = ""
    concept_ids: list[str] = field(default_factory=list)
    state_payload: dict[str, Any] = field(default_factory=dict)
    signals: list[dict[str, Any]] = field(default_factory=list)
    version: int = 1


@dataclass(frozen=True)
class TutorDirective:
    directive_id: str
    user_id: str
    action: InterventionAction
    teaching_goal: str = ""
    qa_policy: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    confidence: float = 0.0
    snapshot_id: str = ""
    source_turn_id: str = ""
    tree_id: str = ""
    node_id: str = ""
    sequence_id: str = ""
    concept_ids: list[str] = field(default_factory=list)
    context_version: str = ""
    status: str = "active"


@dataclass(frozen=True)
class PracticeCommand:
    user_id: str
    turn_id: str
    node_id: str
    target_concept_ids: list[str]
    intervention_goal: str
    trigger_kind: Literal["explicit_button", "agent_recommended", "text_request"]
    context_version: str = ""
    directive_id: str = ""
