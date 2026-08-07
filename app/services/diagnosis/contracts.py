"""QA 回答模块与认知诊断模块共享的数据契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


EvidenceSource = Literal["qa_turn", "screenshot_turn", "exercise", "hint", "diagnosis"]
EvidenceStrength = Literal["certain", "probable", "hypothesis"]
ObservationDirection = Literal["positive", "negative"]
DimensionCode = Literal["mt", "lr", "so", "mr", "ps"]
DimensionFacet = Literal["coverage", "radius", "technical"]
LearningBehavior = Literal[
    "question_only",
    "self_report",
    "definition_recall",
    "solution_attempt",
    "explanation",
    "proof",
    "counterexample",
    "transfer",
]


@dataclass(frozen=True)
class KGStageNode:
    node_id: str
    name: str
    node_type: str = ""


@dataclass(frozen=True)
class KGStageRelation:
    source_node_id: str
    source_name: str
    rel_type: str
    target_node_id: str
    target_name: str


@dataclass(frozen=True)
class QAEvidenceInput:
    """QA 专属评分输入；AI 文本只提供上下文，不能作为能力证据。"""

    turn_id: str
    user_id: str
    student_text: str
    chat_id: str | None = None
    sequence_id: str = ""
    textbook_id: str = ""
    previous_ai_answer: str = ""
    previous_apprenticeship_level: str | None = None
    kg_candidates: list[str] = field(default_factory=list)
    kg_candidate_nodes: list[KGStageNode] = field(default_factory=list)
    kg_candidate_relations: list[KGStageRelation] = field(default_factory=list)
    behavior_hints: list[LearningBehavior] = field(default_factory=list)
    created_at: str | None = None
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    recent_history: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class ExerciseEvidenceInput:
    """练习专属评分输入。"""

    attempt_id: str
    exercise_id: str
    user_id: str
    question: str
    student_answer: str
    correct_answer: str
    is_correct: bool
    verdict: Literal["correct", "partial", "incorrect", "ungradable"] = "incorrect"
    concept_ids: list[str] = field(default_factory=list)
    sequence_id: str = ""
    target_concept: str = ""
    target_stage: int | None = None
    diagnostic_goal: str = "application"
    difficulty: str = ""
    hint_level: int = 0
    grading_feedback: str = ""
    error_analysis: dict[str, Any] = field(default_factory=dict)
    grader_version: str = ""
    created_at: str | None = None


@dataclass(frozen=True)
class DiagnosticSignal:
    """An evidence-backed learning signal. It never contains an action."""

    source_type: Literal["qa_turn", "exercise_attempt"]
    source_id: str
    user_id: str
    sequence_id: str
    signal_type: Literal[
        "concept_confusion",
        "prerequisite_gap",
        "procedural_error",
        "hint_dependency",
        "practice_request",
        "insufficient_evidence",
    ]
    concept_ids: list[str]
    student_quote: str
    confidence: float
    strength: EvidenceStrength
    rationale: str = ""
    scorer_version: str = "v2"


@dataclass(frozen=True)
class StageObservation:
    source_type: Literal["qa_turn", "exercise_attempt"]
    source_id: str
    user_id: str
    sequence_id: str
    concept_name: str
    observed_stage: int
    direction: ObservationDirection
    strength: EvidenceStrength
    student_quote: str
    behavior: LearningBehavior
    support_level: str = "unknown"
    scorer_version: str = "v2"
    concept_id: str = ""
    concept_type: str = ""
    projection_role: Literal["primary", "supporting"] = "primary"
    suppressed_reason: str = ""
    assistant_overlap: float = 0.0
    dialogue_state_action: Literal["accepted", "abstained"] | None = None
    dialogue_state_reason: Literal[
        "independent_evidence",
        "ai_dependent",
        "question_only",
        "self_report",
        "insufficient_context",
    ] | None = None
    dialogue_state_rationale: str = ""


@dataclass(frozen=True)
class DimensionObservation:
    source_type: Literal["qa_turn", "exercise_attempt"]
    source_id: str
    user_id: str
    sequence_id: str
    dimension: DimensionCode
    facet: DimensionFacet
    direction: ObservationDirection
    strength: EvidenceStrength
    student_quote: str
    scorer_version: str = "v2"


@dataclass(frozen=True)
class KGNodeRef:
    """本轮问题关联到的 KG 节点。"""

    name: str
    node_id: str | None = None
    node_type: str | None = None
    section_node_id: str | None = None
    source_code: str | None = None
    evidence_span: str | None = None
    scope: Literal["current", "allowed", "lookahead"] | None = None
    source_name: str | None = None
    rel_type: str | None = None
    stage: int | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class RuleCaseRef:
    """KG 规则案例层中的条件-结论结构。"""

    name: str
    owner_name: str | None = None
    owner_type: str | None = None
    applies_to: list[str] = field(default_factory=list)
    condition_logic: str | None = None
    conditions: list[str] = field(default_factory=list)
    outcomes: list[str] = field(default_factory=list)
    source_code: str | None = None
    evidence_span: str | None = None


@dataclass(frozen=True)
class KGRelationRef:
    """KG 一跳关系引用，用于约束 QA 回答的支撑/延展方向。"""

    source_name: str
    target_name: str
    rel_type: str
    direction: str | None = None
    target_type: str | None = None
    scope: Literal["current", "allowed", "lookahead"] | None = None


@dataclass(frozen=True)
class KGContext:
    """QA 可只读使用的教材 KG 上下文。"""

    book_id: str
    allowed_until: str
    primary_source: str = "textbook_page"
    kg_role: str = "教材索引、术语边界、关系约束和规则条件参考"
    lookahead_rule: str = "后续概念只在用户明确询问联系或后续学习时点到为止，不作为当前解法依赖。"
    current_nodes: list[KGNodeRef] = field(default_factory=list)
    question_matches: list[KGNodeRef] = field(default_factory=list)
    support_nodes: list[KGNodeRef] = field(default_factory=list)
    lookahead_nodes: list[KGNodeRef] = field(default_factory=list)
    relations: list[KGRelationRef] = field(default_factory=list)
    rule_cases: list[RuleCaseRef] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceSpan:
    """可展示在诊断卡片中的教材证据。"""

    source_code: str | None
    text: str
    node_name: str | None = None


@dataclass(frozen=True)
class TurnGrounding:
    """本轮提问在教材和 KG 中的位置。"""

    textbook_id: str
    page_number: int | None
    sequence_id: str
    section_node_id: str
    chapter_name: str = ""
    page_span: tuple[int | None, int | None] = (None, None)
    content_excerpt: str = ""
    related_concepts: list[KGNodeRef] = field(default_factory=list)
    prerequisite_concepts: list[KGNodeRef] = field(default_factory=list)
    rule_cases: list[RuleCaseRef] = field(default_factory=list)
    kg_context: KGContext | None = None
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    confidence: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WeakPrerequisite:
    """可能导致学生卡住的支撑/前置概念。"""

    name: str
    stage: int | None
    evidence: str = ""
    confidence: float | None = None


@dataclass(frozen=True)
class StudentStateSummary:
    """给 QA Prompt 使用的学生状态摘要。"""

    user_id: str
    current_section_stage: int | None = None
    related_concept_stages: dict[str, int | None] = field(default_factory=dict)
    weak_prerequisites: list[WeakPrerequisite] = field(default_factory=list)
    recent_pattern: str = ""
    likely_breakpoint: str = ""
    teaching_policy_hint: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TutorPolicy:
    """单次回答的教学策略。"""

    mode: str = "socratic"
    submode: str = "unclassified"
    should_review_prerequisites: bool = False
    should_ask_guiding_question: bool = True
    should_explain_rule_conditions: bool = False
    allow_full_solution: bool = False
    answer_depth: Literal["brief", "normal", "deep"] = "normal"
    rationale: str = ""


@dataclass(frozen=True)
class CognitiveEvidence:
    """用于更新长期认知状态的证据单元。"""

    source: EvidenceSource
    user_id: str
    concept_name: str
    quote: str
    diagnosis: str
    chat_id: str | None = None
    sequence_id: str | None = None
    textbook_id: str | None = None
    source_code: str | None = None
    evidence_span: str | None = None
    stage_before: int | None = None
    stage_after: int | None = None
    confidence_delta: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DiagnosticCard:
    """未来诊断卡片 API 的数据形状。"""

    concept_name: str
    stage: int | None
    title: str
    evidence_quote: str
    diagnosis: str
    textbook_id: str | None = None
    sequence_id: str | None = None
    source_code: str | None = None
    evidence_span: str | None = None
    prerequisite_gaps: list[WeakPrerequisite] = field(default_factory=list)
    recommended_action: str = ""
