"""为 QA 回答模块构造学生认知状态摘要。"""

from __future__ import annotations

from app.services.diagnosis.contracts import TurnGrounding, WeakPrerequisite


def _get_stage_map(user_id: str, names: list[str]) -> dict[str, int | None]:
    if not names:
        return {}
    try:
        from app.db.knowledge_stages_db import get_stages_batch

        rows = get_stages_batch(user_id, names)
        return {row["concept_name"]: row.get("stage") for row in rows}
    except Exception:
        return {name: None for name in names}


def _average_stage(stages) -> int | None:
    values = [stage for stage in stages if isinstance(stage, int)]
    if not values:
        return None
    return round(sum(values) / len(values))


def _recent_pattern_hint(weak_prereqs: list[WeakPrerequisite]) -> str:
    if weak_prereqs:
        names = "、".join(gap.name for gap in weak_prereqs[:3])
        return f"可能反复依赖支撑知识：{names}"
    return ""


def _breakpoint_hint(grounding: TurnGrounding, weak_prereqs: list[WeakPrerequisite]) -> str:
    if weak_prereqs:
        return f"可能卡在前置/支撑概念：{weak_prereqs[0].name}"
    if grounding.related_concepts:
        return f"可能需要围绕当前核心概念 {grounding.related_concepts[0].name} 建立联系"
    return ""


def _policy_hint(weak_prereqs: list[WeakPrerequisite]) -> str:
    if weak_prereqs:
        return "先用 1-2 句话补足前置，再回到当前问题。"
    return "围绕当前页问题直接讲解，并用一个小问题确认理解。"

