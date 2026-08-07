from __future__ import annotations

from functools import lru_cache

from app.textbooks import cumulative_textbook_ids, section_node_id, subject_display_name

# 白名单缓存，最多缓存 64 个不同的 (textbook_id, sequence_id) 组合
@lru_cache(maxsize=64)
def _cached_whitelist(textbook_id: str, sequence_id: str) -> tuple:
    result = _compute_whitelist(textbook_id, sequence_id)
    # 缓存需要返回可 hash 类型，把 dict 转成 tuple of tuples
    return (
        ("macro", result["macro"]),
        ("micro", result["micro"]),
        ("current", tuple(result.get("current", []))),
        ("prior", tuple(result.get("prior", []))),
    )


def get_whitelist(textbook_id: str, sequence_id: str) -> dict:
    cached = _cached_whitelist(textbook_id, sequence_id)
    return {
        "macro": _cached_value(cached, "macro"),
        "micro": _cached_value(cached, "micro"),
        "current": list(_cached_value(cached, "current") or []),
        "prior": list(_cached_value(cached, "prior") or []),
    }


def _cached_value(cached: tuple, key: str) -> str | tuple:
    for k, v in cached:
        if k == key:
            return v
    return ""


def _compute_whitelist(textbook_id: str, sequence_id: str) -> dict:
    """Query the v4.4 textbook KG for the current answer-scope whitelist."""
    textbook_ids = cumulative_textbook_ids(textbook_id)
    try:
        from app.db.kg_v44 import nodes_for_section, nodes_up_to_chapter

        chapter_num = _chapter_num(sequence_id)
        current_nodes = nodes_for_section(section_node_id(textbook_id, sequence_id), limit=60)
        prior_nodes = nodes_up_to_chapter(textbook_ids, chapter_num, limit=120)

        current_names = _unique_names(current_nodes, limit=35)
        prior_names = _unique_names(prior_nodes, limit=60)
        micro_names = _unique_names([*current_nodes, *prior_nodes], limit=80)

        return {
            "macro": f"允许使用{subject_display_name(textbook_id)}教材第1章到第{chapter_num}章已经出现的概念、定理、公式和方法。",
            "micro": "、".join(micro_names)
            if micro_names
            else "允许使用本章涉及的核心概念、定理、公式和方法。",
            "current": current_names,
            "prior": prior_names,
        }
    except Exception as e:
        print(f"[get_whitelist] v4.4 KG query failed, using fallback: {e}")
        return _fallback_whitelist(sequence_id)


def _chapter_num(sequence_id: str) -> int:
    try:
        for part in (sequence_id or "").split("-"):
            if part.startswith("C"):
                return int(part[1:])
    except Exception:
        pass
    return 1


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


def _fallback_whitelist(sequence_id: str) -> dict:
    chapter_num = _chapter_num(sequence_id)
    return {
        "macro": f"允许使用本教材第1章到第{chapter_num}章已经出现的常规概念和定理。",
        "micro": "",
    }
