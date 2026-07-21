"""单轮 QA 的教学策略决策。"""

from __future__ import annotations

from app.services.diagnosis.contracts import StudentStateSummary, TutorPolicy


def decide_tutor_policy(
    student_state: StudentStateSummary,
    teaching_mode: str = "socratic",
    socratic_submode: str = "unclassified",
) -> TutorPolicy:
    """基于学生状态摘要给出保守的教学策略。"""

    weak_count = len(student_state.weak_prerequisites)
    stage = student_state.current_section_stage
    likely_breakpoint = student_state.likely_breakpoint or ""

    review_prereq = weak_count > 0
    explain_rules = any(keyword in likely_breakpoint for keyword in ["条件", "公式", "定理", "判定"])
    allow_full = teaching_mode == "direct"

    if stage is None or stage <= 1:
        depth = "normal"
        ask_guiding = teaching_mode != "direct"
        rationale = "学生当前概念阶段偏低，先补直观含义和关键前置。"
    elif stage <= 3:
        depth = "normal"
        ask_guiding = teaching_mode == "socratic"
        rationale = "学生已有基础理解，适合边讲边确认关键步骤。"
    else:
        depth = "brief"
        ask_guiding = True
        rationale = "学生阶段较高，减少铺垫，更多用问题推动迁移。"

    return TutorPolicy(
        mode=teaching_mode or "socratic",
        submode=socratic_submode or "unclassified",
        should_review_prerequisites=review_prereq,
        should_ask_guiding_question=ask_guiding,
        should_explain_rule_conditions=explain_rules,
        allow_full_solution=allow_full,
        answer_depth=depth,
        rationale=rationale,
    )

