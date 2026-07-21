from __future__ import annotations


def get_whitelist(textbook_id: str, sequence_id: str) -> dict:
    """Query the v4.4 textbook KG for the current answer-scope whitelist."""
    try:
        from app.db.kg_v44 import nodes_for_section, nodes_up_to_chapter

        chapter_num = _chapter_num(sequence_id)
        textbook_ids = _v44_textbook_ids(textbook_id)
        current_nodes = nodes_for_section(_v44_section_id(textbook_id, sequence_id), limit=60)
        prior_nodes = nodes_up_to_chapter(textbook_ids, chapter_num, limit=120)

        current_names = _unique_names(current_nodes, limit=35)
        prior_names = _unique_names(prior_nodes, limit=60)
        micro_names = _unique_names([*current_nodes, *prior_nodes], limit=80)

        return {
            "macro": f"允许使用{_subject_name(textbook_id)}教材第1章到第{chapter_num}章已经出现的概念、定理、公式和方法。",
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


def _v44_textbook_ids(textbook_id: str) -> list[str]:
    current = _v44_textbook_id(textbook_id)
    if current == "gaodai_xia":
        return ["gaodai_shang", "gaodai_xia"]
    if current == "gaoshu_xia":
        return ["gaoshu_shang", "gaoshu_xia"]
    return [current]


def _subject_name(textbook_id: str) -> str:
    value = textbook_id or ""
    lowered = value.lower()
    if "高数" in value or "高等数学" in value or "gaoshu" in lowered:
        return "高等数学"
    return "高等代数"


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


def _fallback_whitelist(sequence_id: str) -> dict:
    chapter_num = _chapter_num(sequence_id)
    return {
        "macro": f"允许使用本教材第1章到第{chapter_num}章已经出现的常规概念和定理。",
        "micro": "",
    }
