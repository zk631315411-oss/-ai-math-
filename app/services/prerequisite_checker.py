"""Prerequisite/support-gap detection for the v4.4 textbook KG.

The v4.4 graph does not use the old PREREQUISITE_OF/TEACH_IN structure.
For tutoring, we treat neighboring support nodes around the current section
as "possible missing support knowledge" and then check the user's stage table.
"""

from app.db.knowledge_stages_db import get_stages_batch


def get_prereq_gaps(sequence_id: str, user_id: str, textbook_id: str = "") -> list[dict]:
    try:
        from app.db.kg_v44 import prerequisite_candidates_for_section

        section_node_id = _v44_section_id(textbook_id, sequence_id)
        prereq_names = prerequisite_candidates_for_section(section_node_id, limit=12)
    except Exception:
        prereq_names = []

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


def _v44_section_id(textbook_id: str, sequence_id: str) -> str:
    tid = _v44_textbook_id(textbook_id)
    parts = (sequence_id or "").split("-")
    chapter = next((p for p in parts if p.startswith("C")), "C01")
    section = next((p for p in parts if p.startswith("S")), "S01")
    unit = next((p for p in parts if p.startswith("U")), "")
    base = f"{tid}:{chapter}:{section}"
    return f"{base}:{unit}" if unit else base


def _v44_textbook_id(textbook_id: str) -> str:
    value = textbook_id or ""
    lowered = value.lower()
    is_gaoshu = "高数" in value or "高等数学" in value or "gaoshu" in lowered
    if is_gaoshu:
        return "gaoshu_xia" if _is_volume_2(value) else "gaoshu_shang"
    return "gaodai_xia" if _is_volume_2(value) else "gaodai_shang"


def _is_volume_2(textbook_id: str) -> bool:
    value = textbook_id or ""
    return "下" in value or "xia" in value.lower() or "vol2" in value.lower()


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
