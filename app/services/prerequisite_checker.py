"""Prerequisite/support-gap detection for the v4.4 textbook KG.

The v4.4 graph does not use the old PREREQUISITE_OF/TEACH_IN structure.
For tutoring, we treat neighboring support nodes around the current section
as "possible missing support knowledge" and then check the user's stage table.
"""

from functools import lru_cache

from app.db.knowledge_stages_db import get_stages_batch
from app.textbooks import section_node_id


# 前置候选缓存，最多缓存 64 个不同的 section_node_id
@lru_cache(maxsize=64)
def _cached_prereq_candidates(section_node_id: str) -> tuple:
    try:
        from app.db.kg_v44 import prerequisite_candidates_for_section

        names = prerequisite_candidates_for_section(section_node_id, limit=12)
        return tuple(names)
    except Exception:
        return ()


def get_prereq_gaps(sequence_id: str, user_id: str, textbook_id: str = "") -> list[dict]:
    current_section_id = section_node_id(textbook_id, sequence_id)
    prereq_names = list(_cached_prereq_candidates(current_section_id))

    if not prereq_names:
        return []

    stages = get_stages_batch(user_id, prereq_names)
    gaps = []
    for stage_row in stages:
        stage = stage_row["stage"]
        gaps.append(
            {
                "name": stage_row["concept_name"],
                "stage": stage,
                "is_gap": stage is None or stage <= 2,
            }
        )
    return gaps


async def get_prerequisite_chain(topic: str) -> list[str]:
    """Compatibility wrapper for older async tests/callers.

    In v4.4 this returns nearby support/extension knowledge instead of a
    strict prerequisite chain.
    """
    try:
        from app.db.kg_v44 import related_nodes

        support_nodes, extension_nodes = related_nodes(topic, limit=8)
        return _unique_names([*support_nodes, *extension_nodes], limit=10)
    except Exception:
        return []


async def check_gaps(user_id: str, topic: str) -> list[dict]:
    """Compatibility wrapper: check whether support nodes for topic are weak."""
    chain = await get_prerequisite_chain(topic)
    if not chain:
        return []

    stages = get_stages_batch(user_id, chain)
    gaps = []
    for row in stages:
        stage = row["stage"]
        gaps.append(
            {
                "name": row["concept_name"],
                "stage": stage,
                "is_gap": stage is None or stage <= 2,
            }
        )
    return gaps


def build_prereq_prompt_block(gaps: list[dict]) -> str:
    gap_names = [g["name"] for g in gaps if g["is_gap"]]
    if not gap_names:
        return ""

    shown = gap_names[:8]
    suffix = "等" if len(gap_names) > 8 else ""
    return (
        "\n## 前置/支撑知识提醒\n"
        f"系统从教材知识图谱中发现，学生可能还需要补强：{', '.join(shown)}{suffix}。\n"
        "请在讲解中优先：\n"
        "1. 用1-2句话简要回顾这些支撑知识；\n"
        "2. 用一个简单问题确认学生是否理解。\n"
    )


def _unique_names(nodes: list[dict], limit: int) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for node in nodes:
        name = str(node.get("name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names
