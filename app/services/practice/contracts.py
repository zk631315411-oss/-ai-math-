"""Small, explicit contracts shared by the practice API and workers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Verdict = Literal["correct", "partial", "incorrect", "ungradable"]
DraftStatus = Literal["queued", "running", "ready", "partial", "failed", "stale", "cancelled"]
SessionStatus = Literal["active", "completed", "inconclusive", "abandoned"]
BranchRole = Literal["diagnostic", "remedial", "verify", "advance"]


@dataclass(frozen=True)
class PracticeContext:
    user_id: str
    turn_id: str
    tree_id: str = ""
    node_id: str = ""
    textbook_id: str = ""
    page_number: int | None = None
    sequence_id: str = ""
    chapter_name: str = ""
    question: str = ""
    history: list[dict[str, str]] = field(default_factory=list)
    concept_ids: list[str] = field(default_factory=list)
    concept_names: list[str] = field(default_factory=list)
    page_excerpt: str = ""
    sources: list[dict[str, Any]] = field(default_factory=list)
    student_stage: int | None = None
    evidence_quote: str = ""
    intervention_goal: str = ""

    def snapshot(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "tree_id": self.tree_id,
            "node_id": self.node_id,
            "textbook_id": self.textbook_id,
            "page_number": self.page_number,
            "sequence_id": self.sequence_id,
            "chapter_name": self.chapter_name,
            "question": self.question,
            "history": self.history[-3:],
            "concept_ids": self.concept_ids,
            "concept_names": self.concept_names,
            "page_excerpt": self.page_excerpt[:2400],
            "sources": self.sources[:8],
            "student_stage": self.student_stage,
            "evidence_quote": self.evidence_quote,
            "intervention_goal": self.intervention_goal,
        }


@dataclass(frozen=True)
class GradeResult:
    verdict: Verdict
    evidence_quotes: list[str] = field(default_factory=list)
    rubric_findings: list[dict[str, Any]] = field(default_factory=list)
    feedback: str = ""
    error_analysis: dict[str, Any] = field(default_factory=dict)
