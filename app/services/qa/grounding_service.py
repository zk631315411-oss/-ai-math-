"""把用户提问定位到教材页和 KG 节点。"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache
import re

from app.services.diagnosis.contracts import (
    EvidenceSpan,
    KGContext,
    KGNodeRef,
    KGRelationRef,
    RuleCaseRef,
    TurnGrounding,
)


DEFAULT_SEQUENCE_ID = "V1-C00-S00"


def ground_text_turn(
    textbook_id: str,
    page_number: int | None,
    question: str = "",
    *,
    excerpt_chars: int = 2400,
) -> TurnGrounding:
    """构造文字提问的定位结果。

    只读：不更新学生状态、不写诊断数据。
    """

    textbook_id = textbook_id or "高代上-丘维声"
    if not page_number:
        return TurnGrounding(
            textbook_id=textbook_id,
            page_number=None,
            sequence_id=DEFAULT_SEQUENCE_ID,
            section_node_id=_section_node_id(textbook_id, DEFAULT_SEQUENCE_ID),
            confidence=0.0,
            raw={"reason": "missing_page_number", "question": question},
        )

    from app.db.textbook_section_db import get_page_context

    page_context = get_page_context(textbook_id, page_number)
    if not page_context or "error" in page_context:
        return TurnGrounding(
            textbook_id=textbook_id,
            page_number=page_number,
            sequence_id=DEFAULT_SEQUENCE_ID,
            section_node_id=_section_node_id(textbook_id, DEFAULT_SEQUENCE_ID),
            confidence=0.0,
            raw={"page_context": page_context, "question": question},
        )

    sequence_id = page_context.get("sequence_id") or DEFAULT_SEQUENCE_ID
    section_node_id = _section_node_id(textbook_id, sequence_id)
    current_lookup_page = int(page_context.get("section_lookup_page") or page_number or 0)
    book_id = _v44_textbook_id(textbook_id)
    content = page_context.get("content") or ""
    current_node_rows = _safe_node_rows_for_section(section_node_id)
    question_match_rows = _safe_question_node_rows(book_id, question, section_node_id)
    seed_rows = _merge_node_rows(current_node_rows[:10], question_match_rows[:8], limit=14)
    relation_rows = _safe_relation_neighbors(
        [str(row.get("node_id") or "") for row in seed_rows],
        book_id,
    )
    current_nodes = [_to_node_ref(row) for row in current_node_rows]
    question_nodes = [
        _to_node_ref(row)
        for row in question_match_rows
        if _scope_for_row(row, section_node_id, textbook_id, current_lookup_page) != "lookahead"
    ]
    related_nodes = _merge_node_refs(current_nodes, question_nodes, limit=40)

    support_rows = [
        row
        for row in relation_rows
        if _scope_for_row(row, section_node_id, textbook_id, current_lookup_page) != "lookahead"
    ]
    lookahead_rows = [
        *_lookahead_rows(question_match_rows, section_node_id, textbook_id, current_lookup_page),
        *_lookahead_rows(relation_rows, section_node_id, textbook_id, current_lookup_page),
    ]
    rule_seed_rows = _merge_node_rows(
        [
            row
            for row in seed_rows
            if _scope_for_row(row, section_node_id, textbook_id, current_lookup_page) != "lookahead"
        ],
        support_rows,
        limit=24,
    )
    rule_case_rows = _safe_rule_cases(
        [str(row.get("node_id") or "") for row in rule_seed_rows],
        book_id,
    )
    rule_case_rows = _rank_rule_case_rows(
        rule_case_rows,
        question=question,
        current_node_rows=current_node_rows,
        question_match_rows=question_match_rows,
        support_rows=support_rows,
        section_node_id=section_node_id,
        textbook_id=textbook_id,
        current_lookup_page=current_lookup_page,
    )
    prereq_nodes = [_to_node_ref(row) for row in _unique_node_rows(support_rows, limit=12)]
    if not prereq_nodes:
        prereq_nodes = _safe_prerequisite_nodes(section_node_id)

    rule_cases = [_to_rule_case_ref(row) for row in rule_case_rows]
    kg_context = _build_kg_context(
        book_id=book_id,
        section_node_id=section_node_id,
        current_node_rows=current_node_rows,
        question_match_rows=question_match_rows,
        relation_rows=relation_rows,
        lookahead_rows=lookahead_rows,
        rule_case_rows=rule_case_rows,
        textbook_id=textbook_id,
        current_lookup_page=current_lookup_page,
    )
    evidence_spans = [
        EvidenceSpan(
            source_code=node.source_code,
            text=node.evidence_span or "",
            node_name=node.name,
        )
        for node in related_nodes
        if node.evidence_span
    ]
    evidence_spans.extend(
        EvidenceSpan(
            source_code=case.source_code,
            text=case.evidence_span or "",
            node_name=f"{case.owner_name or '规则'} / {case.name}",
        )
        for case in rule_cases
        if case.evidence_span
    )
    evidence_spans = evidence_spans[:8]

    return TurnGrounding(
        textbook_id=textbook_id,
        page_number=page_number,
        sequence_id=sequence_id,
        section_node_id=section_node_id,
        chapter_name=page_context.get("chapter_name") or "",
        page_span=(page_context.get("start_page"), page_context.get("end_page")),
        content_excerpt=_excerpt(content, excerpt_chars),
        related_concepts=related_nodes,
        prerequisite_concepts=prereq_nodes,
        rule_cases=rule_cases,
        kg_context=kg_context,
        evidence_spans=evidence_spans,
        confidence=0.75 if related_nodes else 0.55,
        raw={
            "page_context": page_context,
            "question": question,
            "kg_context": asdict(kg_context),
        },
    )


def _safe_node_rows_for_section(section_node_id: str, limit: int = 40) -> list[dict]:
    try:
        from app.db.kg_v44 import nodes_for_section

        return nodes_for_section(section_node_id, limit=limit)
    except Exception:
        return []


def _safe_question_node_rows(
    book_id: str,
    question: str,
    section_node_id: str,
    limit: int = 12,
) -> list[dict]:
    try:
        from app.db.kg_v44 import search_nodes_in_book

        return search_nodes_in_book(
            book_id,
            question,
            current_section_node_id=section_node_id,
            limit=limit,
        )
    except Exception:
        return []


def _safe_relation_neighbors(node_ids: list[str], book_id: str, limit: int = 24) -> list[dict]:
    node_ids = [node_id for node_id in node_ids if node_id]
    if not node_ids:
        return []
    try:
        from app.db.kg_v44 import relation_neighbors_for_nodes

        return relation_neighbors_for_nodes(node_ids, book_id, limit=limit)
    except Exception:
        return []


def _safe_rule_cases(node_ids: list[str], book_id: str, limit: int = 5) -> list[dict]:
    node_ids = [node_id for node_id in node_ids if node_id]
    if not node_ids:
        return []
    try:
        from app.db.kg_v44 import rule_cases_for_nodes

        return rule_cases_for_nodes(node_ids, book_id, limit=limit)
    except Exception:
        return []


def _safe_prerequisite_nodes(section_node_id: str, limit: int = 12) -> list[KGNodeRef]:
    try:
        from app.db.kg_v44 import prerequisite_candidates_for_section

        names = prerequisite_candidates_for_section(section_node_id, limit=limit)
        return [KGNodeRef(name=name) for name in names]
    except Exception:
        return []


def _to_node_ref(row: dict) -> KGNodeRef:
    return KGNodeRef(
        name=str(row.get("name") or ""),
        node_id=row.get("node_id"),
        node_type=row.get("type"),
        section_node_id=row.get("section_node_id"),
        source_code=row.get("source_code"),
        evidence_span=row.get("evidence_span"),
    )


def _to_rule_case_ref(row: dict) -> RuleCaseRef:
    return RuleCaseRef(
        name=str(row.get("rule_case") or ""),
        owner_name=row.get("owner_name"),
        owner_type=row.get("owner_type"),
        applies_to=_as_list(row.get("applies_to")),
        condition_logic=row.get("condition_logic"),
        conditions=_as_list(row.get("conditions")),
        outcomes=_as_list(row.get("outcomes")),
        source_code=row.get("source_code"),
        evidence_span=row.get("evidence_span"),
    )


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    text = str(value).strip()
    return [text] if text else []


def _section_node_id(textbook_id: str, sequence_id: str) -> str:
    tid = _v44_textbook_id(textbook_id)
    parts = (sequence_id or "").split("-")
    chapter = next((part for part in parts if part.startswith("C")), "C00")
    section = next((part for part in parts if part.startswith("S")), "S00")
    return f"{tid}:{chapter}:{section}"


def _v44_textbook_id(textbook_id: str) -> str:
    value = textbook_id or ""
    lowered = value.lower()
    is_gaoshu = "高数" in value or "高等数学" in value or "gaoshu" in lowered
    is_volume_2 = "下" in value or "xia" in lowered or "vol2" in lowered
    if is_gaoshu:
        return "gaoshu_xia" if is_volume_2 else "gaoshu_shang"
    return "gaodai_xia" if is_volume_2 else "gaodai_shang"


def _merge_node_refs(*groups: list[KGNodeRef], limit: int) -> list[KGNodeRef]:
    result: list[KGNodeRef] = []
    seen: set[str] = set()
    for group in groups:
        for node in group:
            key = node.node_id or node.name
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(node)
            if len(result) >= limit:
                return result
    return result


def _merge_node_rows(*groups: list[dict], limit: int) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for group in groups:
        for row in group:
            key = str(row.get("node_id") or row.get("name") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(row)
            if len(result) >= limit:
                return result
    return result


def _unique_node_rows(rows: list[dict], limit: int) -> list[dict]:
    return _merge_node_rows(rows, limit=limit)


def _lookahead_rows(
    rows: list[dict],
    current_section_node_id: str,
    textbook_id: str,
    current_lookup_page: int | None,
) -> list[dict]:
    return [
        row
        for row in rows
        if _scope_for_row(row, current_section_node_id, textbook_id, current_lookup_page) == "lookahead"
    ]


def _scope_for_row(
    row: dict,
    current_section_node_id: str,
    textbook_id: str = "",
    current_lookup_page: int | None = None,
) -> str:
    source = str(row.get("section_node_id") or row.get("source_code") or "")
    if textbook_id and current_lookup_page:
        source_pages = _source_section_pages(textbook_id, source)
        if source_pages and source_pages[0] > current_lookup_page:
            return "lookahead"
    if current_section_node_id and source.startswith(current_section_node_id):
        return "current"
    source_order = _section_order(source)
    current_order = _section_order(current_section_node_id)
    if source_order and current_order and source_order > current_order:
        return "lookahead"
    return "allowed"


def _section_order(section_code: str) -> tuple[int, int] | None:
    if not section_code:
        return None
    parts = section_code.split(":")
    chapter = next((part for part in parts if part.startswith("C") and part[1:].isdigit()), "")
    section = next((part for part in parts if part.startswith("S") and part[1:].isdigit()), "")
    if not chapter:
        return None
    return (int(chapter[1:]), int(section[1:]) if section else 0)


def _build_kg_context(
    *,
    book_id: str,
    section_node_id: str,
    current_node_rows: list[dict],
    question_match_rows: list[dict],
    relation_rows: list[dict],
    lookahead_rows: list[dict],
    rule_case_rows: list[dict],
    textbook_id: str,
    current_lookup_page: int | None,
) -> KGContext:
    return KGContext(
        book_id=book_id,
        allowed_until=section_node_id,
        current_nodes=[
            _node_context(row, section_node_id, textbook_id, current_lookup_page)
            for row in _unique_node_rows(current_node_rows, limit=12)
        ],
        question_matches=[
            _node_context(row, section_node_id, textbook_id, current_lookup_page)
            for row in _unique_node_rows(question_match_rows, limit=10)
        ],
        support_nodes=[
            _node_context(row, section_node_id, textbook_id, current_lookup_page) for row in _unique_node_rows(
                [
                    row
                    for row in relation_rows
                    if _scope_for_row(row, section_node_id, textbook_id, current_lookup_page) != "lookahead"
                ],
                limit=10,
            )
        ],
        lookahead_nodes=[
            _node_context(row, section_node_id, textbook_id, current_lookup_page)
            for row in _unique_node_rows(lookahead_rows, limit=8)
        ],
        relations=[
            _relation_context(row, section_node_id, textbook_id, current_lookup_page)
            for row in relation_rows[:16]
        ],
        rule_cases=[_rule_case_context(row) for row in rule_case_rows[:5]],
    )


def _node_context(
    row: dict,
    current_section_node_id: str,
    textbook_id: str,
    current_lookup_page: int | None,
) -> KGNodeRef:
    return KGNodeRef(
        name=str(row.get("name") or ""),
        node_id=row.get("node_id"),
        node_type=row.get("type"),
        section_node_id=row.get("section_node_id"),
        source_code=row.get("source_code"),
        evidence_span=_trim(row.get("evidence_span"), 360),
        scope=_scope_for_row(row, current_section_node_id, textbook_id, current_lookup_page),
        source_name=row.get("source_name"),
        rel_type=row.get("rel_type"),
    )


def _relation_context(
    row: dict,
    current_section_node_id: str,
    textbook_id: str,
    current_lookup_page: int | None,
) -> KGRelationRef:
    return KGRelationRef(
        source_name=str(row.get("source_name") or ""),
        target_name=str(row.get("name") or ""),
        rel_type=str(row.get("rel_type") or ""),
        direction=row.get("direction"),
        target_type=row.get("type"),
        scope=_scope_for_row(row, current_section_node_id, textbook_id, current_lookup_page),
    )


def _rule_case_context(row: dict) -> RuleCaseRef:
    return RuleCaseRef(
        name=str(row.get("rule_case") or ""),
        owner_name=row.get("owner_name"),
        owner_type=row.get("owner_type"),
        applies_to=_as_list(row.get("applies_to")),
        condition_logic=row.get("condition_logic"),
        conditions=_as_list(row.get("conditions"))[:6],
        outcomes=_as_list(row.get("outcomes"))[:6],
        source_code=row.get("source_code"),
        evidence_span=_trim(row.get("evidence_span"), 480),
    )


def _rank_rule_case_rows(
    rows: list[dict],
    *,
    question: str,
    current_node_rows: list[dict],
    question_match_rows: list[dict],
    support_rows: list[dict],
    section_node_id: str,
    textbook_id: str,
    current_lookup_page: int | None,
) -> list[dict]:
    owner_rank: dict[str, int] = {}
    for rank, group in ((0, current_node_rows), (1, question_match_rows), (2, support_rows)):
        for row in group:
            node_id = str(row.get("node_id") or "")
            if node_id:
                owner_rank[node_id] = min(owner_rank.get(node_id, rank), rank)

    def sort_key(row: dict) -> tuple[int, int, int, str]:
        owner_node_id = str(row.get("owner_node_id") or "")
        source_rank = owner_rank.get(owner_node_id, 9)
        scope = _scope_for_row(row, section_node_id, textbook_id, current_lookup_page)
        scope_rank = {"current": 0, "allowed": 1, "lookahead": 9}.get(scope, 5)
        relevance = _rule_case_relevance_score(row, question)
        return (scope_rank, source_rank, -relevance, str(row.get("rule_case") or ""))

    return sorted(rows, key=sort_key)


def _rule_case_relevance_score(row: dict, question: str) -> int:
    row_text = " ".join(
        [
            str(row.get("owner_name") or ""),
            str(row.get("rule_case") or ""),
            " ".join(_as_list(row.get("applies_to"))),
            " ".join(_as_list(row.get("conditions"))),
            " ".join(_as_list(row.get("outcomes"))),
            str(row.get("evidence_span") or ""),
        ]
    )
    score = 0
    for term in _question_terms(question):
        if term and term in row_text:
            score += len(term)
    return score


def _question_terms(question: str) -> list[str]:
    text = re.sub(r"[\s，。！？、；：,.!?;:()\[\]{}（）【】]+", "", question or "")
    for stop_word in ("什么", "时候", "为什么", "怎么", "如何", "是否", "可以", "需要"):
        text = text.replace(stop_word, "")
    if len(text) < 3:
        return [text] if text else []
    terms: set[str] = set()
    for size in (6, 5, 4, 3):
        for idx in range(0, max(0, len(text) - size + 1)):
            terms.add(text[idx : idx + size])
    return sorted(terms, key=lambda item: (-len(item), item))


@lru_cache(maxsize=512)
def _source_section_pages(textbook_id: str, source_code: str) -> tuple[int, int] | None:
    chapter_section = _chapter_section_from_source(source_code)
    if not chapter_section:
        return None
    chapter, section = chapter_section
    sequence_like = f"%-{chapter}-{section}"
    try:
        from app.db.connection import get_conn

        conn = get_conn()
        try:
            row = conn.execute(
                """
                SELECT MIN(start_page) AS start_page, MAX(end_page) AS end_page
                FROM textbook_sections
                WHERE textbook_id=? AND sequence_id LIKE ?
                """,
                (textbook_id, sequence_like),
            ).fetchone()
        finally:
            conn.close()
        if not row or row["start_page"] is None:
            return None
        return int(row["start_page"]), int(row["end_page"])
    except Exception:
        return None


def _chapter_section_from_source(source_code: str) -> tuple[str, str] | None:
    parts = (source_code or "").split(":")
    chapter = next((part for part in parts if re.fullmatch(r"C\d{2}", part)), "")
    section = next((part for part in parts if re.fullmatch(r"S\d{2}", part)), "")
    if not chapter or not section:
        return None
    return chapter, section


def _trim(value: str | None, limit: int) -> str:
    text = (value or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _excerpt(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n..."
