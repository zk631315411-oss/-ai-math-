from __future__ import annotations

from contextlib import contextmanager
import socket
import time
from typing import Iterable
from urllib.parse import urlparse

from app.config import config


CORE_LABELS = {"Concept", "Theorem", "Formula", "Method", "ProblemClass"}
SUPPORT_REL_TYPES = [
    "SUPERIOR",
    "PART_OF",
    "USES",
    "GETS",
    "DERIVES",
    "HAS_PROPERTY",
    "EQUATIVE",
    "REFERS_TO",
]
_KG_AVAILABILITY_CACHE = {
    "checked_at": 0.0,
    "available": None,
}


def _import_batch() -> str:
    import os

    return os.getenv("KG_IMPORT_BATCH", "")


def _database() -> str | None:
    import os

    database = os.getenv("NEO4J_DATABASE", "neo4j")
    return None if database in {"", "neo4j", "default"} else database


@contextmanager
def _session():
    if not _kg_may_be_available():
        raise ConnectionError(f"Neo4j unavailable: {config.NEO4J_URI}")

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        connection_timeout=1.0,
    )
    try:
        with driver.session(database=_database()) as session:
            yield session
    finally:
        driver.close()


def _kg_may_be_available(ttl_seconds: float = 15.0, timeout_seconds: float = 0.35) -> bool:
    """Fast preflight so QA can degrade quickly when local Neo4j is down."""

    now = time.monotonic()
    cached = _KG_AVAILABILITY_CACHE["available"]
    if cached is not None and now - _KG_AVAILABILITY_CACHE["checked_at"] < ttl_seconds:
        return bool(cached)

    parsed = urlparse(config.NEO4J_URI)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 7687

    try:
        with socket.create_connection((host, port), timeout=timeout_seconds):
            available = True
    except OSError:
        available = False

    _KG_AVAILABILITY_CACHE["checked_at"] = now
    _KG_AVAILABILITY_CACHE["available"] = available
    return available


def _batch_clause(alias: str = "n") -> str:
    return f"AND (${alias}_batch = '' OR {alias}.import_batch = ${alias}_batch)"


def _book_id_from_section(section_node_id: str) -> str:
    value = (section_node_id or "").strip()
    return value.split(":", 1)[0] if ":" in value else ""


def _book_prefix(book_id: str) -> str:
    book_id = (book_id or "").strip()
    return f"{book_id}:" if book_id else ""


def _node_map(row) -> dict:
    return {
        "node_id": row.get("node_id"),
        "name": row.get("name"),
        "type": row.get("type"),
        "chapter": row.get("chapter"),
        "section": row.get("section"),
        "section_node_id": row.get("section_node_id"),
        "source_code": row.get("source_code"),
        "evidence_span": row.get("evidence_span"),
    }


def _node_rel_map(row) -> dict:
    data = _node_map(row)
    data.update(
        {
            "source_node_id": row.get("source_node_id"),
            "source_name": row.get("source_name"),
            "rel_type": row.get("rel_type"),
            "direction": row.get("direction"),
            "rel_rank": row.get("rel_rank"),
        }
    )
    return data


def _list_value(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    text = str(value).strip()
    return [text] if text else []


def _rule_case_map(row) -> dict:
    return {
        "owner_node_id": row.get("owner_node_id"),
        "owner_name": row.get("owner_name"),
        "owner_type": row.get("owner_type"),
        "rule_case": row.get("rule_case"),
        "applies_to": _list_value(row.get("applies_to")),
        "condition_logic": row.get("condition_logic"),
        "conditions": _list_value(row.get("conditions")),
        "outcomes": _list_value(row.get("outcomes")),
        "source_code": row.get("source_code"),
        "evidence_span": row.get("evidence_span"),
    }


def find_node(name: str, labels: Iterable[str] | None = None) -> dict | None:
    name = (name or "").strip()
    if not name:
        return None
    label_filter = list(labels or CORE_LABELS)
    with _session() as session:
        record = session.run(
            """
            MATCH (n:KGNode)
            WHERE ($n_batch = '' OR n.import_batch = $n_batch)
              AND n.type IN $types
              AND n.name = $name
            RETURN n.node_id AS node_id, n.name AS name, n.type AS type,
                   n.chapter AS chapter, n.section AS section,
                   n.section_node_id AS section_node_id,
                   n.source_code AS source_code, n.evidence_span AS evidence_span
            LIMIT 1
            """,
            n_batch=_import_batch(),
            types=label_filter,
            name=name,
        ).single()
        if not record:
            record = session.run(
                """
                MATCH (n:KGNode)
                WHERE ($n_batch = '' OR n.import_batch = $n_batch)
                  AND n.type IN $types
                  AND (n.name CONTAINS $name OR $name CONTAINS n.name)
                RETURN n.node_id AS node_id, n.name AS name, n.type AS type,
                       n.chapter AS chapter, n.section AS section,
                       n.section_node_id AS section_node_id,
                       n.source_code AS source_code, n.evidence_span AS evidence_span
                ORDER BY size(n.name) DESC
                LIMIT 1
                """,
                n_batch=_import_batch(),
                types=label_filter,
                name=name,
            ).single()
        return _node_map(record) if record else None


def search_nodes_in_book(
    book_id: str,
    query: str,
    *,
    current_section_node_id: str = "",
    labels: Iterable[str] | None = None,
    limit: int = 12,
) -> list[dict]:
    query_text = (query or "").strip()
    if not query_text:
        return []
    label_filter = list(labels or CORE_LABELS)
    chapter_prefix = ":".join((current_section_node_id or "").split(":")[:2])
    if chapter_prefix:
        chapter_prefix += ":"
    with _session() as session:
        rows = session.run(
            """
            MATCH (n:KGNode)
            WHERE ($n_batch = '' OR n.import_batch = $n_batch)
              AND n.type IN $types
              AND ($book_prefix = '' OR coalesce(n.section_node_id, n.source_code, '') STARTS WITH $book_prefix)
              AND size(coalesce(n.name, '')) >= 2
              AND (
                n.name CONTAINS $query_text
                OR $query_text CONTAINS n.name
                OR any(alias IN coalesce(n.aliases, []) WHERE alias CONTAINS $query_text OR $query_text CONTAINS alias)
              )
            RETURN DISTINCT n.node_id AS node_id, n.name AS name, n.type AS type,
                   n.chapter AS chapter, n.section AS section,
                   n.section_node_id AS section_node_id,
                   n.source_code AS source_code, n.evidence_span AS evidence_span,
                   CASE
                     WHEN $current_section_node_id <> '' AND coalesce(n.section_node_id, n.source_code, '') STARTS WITH $current_section_node_id THEN 0
                     WHEN $chapter_prefix <> '' AND coalesce(n.section_node_id, n.source_code, '') STARTS WITH $chapter_prefix THEN 1
                     ELSE 2
                   END AS scope_rank
            ORDER BY scope_rank, size(n.name) DESC, n.name
            LIMIT $limit
            """,
            n_batch=_import_batch(),
            types=label_filter,
            book_prefix=_book_prefix(book_id),
            query_text=query_text,
            current_section_node_id=current_section_node_id,
            chapter_prefix=chapter_prefix,
            limit=limit,
        )
        return [_node_map(row) | {"scope_rank": row.get("scope_rank")} for row in rows]


def nodes_for_section(section_node_id: str, limit: int = 40) -> list[dict]:
    section_node_id = (section_node_id or "").strip()
    if not section_node_id:
        return []
    with _session() as session:
        rows = session.run(
            """
            MATCH (g:KGNode:KnowledgeGroup)-[:HAS_MEMBER]->(n:KGNode)
            WHERE ($g_batch = '' OR g.import_batch = $g_batch)
              AND ($n_batch = '' OR n.import_batch = $n_batch)
              AND g.section_node_id STARTS WITH $section_node_id
              AND n.type IN $types
            RETURN DISTINCT n.node_id AS node_id, n.name AS name, n.type AS type,
                   n.chapter AS chapter, n.section AS section,
                   n.section_node_id AS section_node_id,
                   n.source_code AS source_code, n.evidence_span AS evidence_span
            ORDER BY n.type, n.name
            LIMIT $limit
            """,
            g_batch=_import_batch(),
            n_batch=_import_batch(),
            section_node_id=section_node_id,
            types=list(CORE_LABELS),
            limit=limit,
        )
        return [_node_map(row) for row in rows]


def relations_between_nodes(node_ids: list[str]) -> list[dict]:
    """Return directed semantic relations whose two endpoints are both candidates."""

    node_ids = list(dict.fromkeys(node_id for node_id in node_ids if node_id))
    if not node_ids:
        return []
    with _session() as session:
        rows = session.run(
            """
            MATCH (source:KGNode)-[r:PART_OF|USES|GETS]->(target:KGNode)
            WHERE source.node_id IN $node_ids AND target.node_id IN $node_ids
              AND ($source_batch = '' OR source.import_batch = $source_batch)
              AND ($target_batch = '' OR target.import_batch = $target_batch)
            RETURN DISTINCT source.node_id AS source_node_id,
                   source.name AS source_name,
                   type(r) AS rel_type,
                   target.node_id AS target_node_id,
                   target.name AS target_name
            ORDER BY source.name, rel_type, target.name
            """,
            node_ids=node_ids,
            source_batch=_import_batch(),
            target_batch=_import_batch(),
        )
        return [dict(row) for row in rows]


def nodes_up_to_chapter(textbook_ids: list[str], chapter_num: int, limit: int = 120) -> list[dict]:
    if chapter_num <= 0:
        return []
    chapter_prefixes = [f"{tid}:C{i:02d}" for tid in textbook_ids for i in range(1, chapter_num + 1)]
    with _session() as session:
        rows = session.run(
            """
            MATCH (n:KGNode)
            WHERE ($n_batch = '' OR n.import_batch = $n_batch)
              AND n.type IN $types
              AND any(prefix IN $prefixes WHERE n.section_node_id STARTS WITH prefix)
            RETURN DISTINCT n.node_id AS node_id, n.name AS name, n.type AS type,
                   n.chapter AS chapter, n.section AS section,
                   n.section_node_id AS section_node_id,
                   n.source_code AS source_code, n.evidence_span AS evidence_span
            ORDER BY n.section_node_id, n.type, n.name
            LIMIT $limit
            """,
            n_batch=_import_batch(),
            types=["Concept", "Theorem", "Formula"],
            prefixes=chapter_prefixes,
            limit=limit,
        )
        return [_node_map(row) for row in rows]


def related_nodes(name: str, limit: int = 5) -> tuple[list[dict], list[dict]]:
    node = find_node(name)
    if not node:
        return [], []
    with _session() as session:
        support_rows = session.run(
            """
            MATCH (n:KGNode {node_id: $node_id})
            CALL (n) {
              MATCH (n)-[r:USES|SUPERIOR|PART_OF]->(m:KGNode)
              RETURN m, type(r) AS rel_type,
                     CASE type(r)
                       WHEN 'USES' THEN 0
                       WHEN 'SUPERIOR' THEN 3
                       WHEN 'PART_OF' THEN 4
                       ELSE 9
                     END AS rel_rank
              UNION
              WITH n
              MATCH (m:KGNode)-[r:GETS|DERIVES|HAS_PROPERTY]->(n)
              RETURN m, type(r) AS rel_type,
                     CASE type(r)
                       WHEN 'GETS' THEN 1
                       WHEN 'DERIVES' THEN 2
                       WHEN 'HAS_PROPERTY' THEN 5
                       ELSE 9
                     END AS rel_rank
              UNION
              WITH n
              MATCH (n)-[r:EQUATIVE]-(m:KGNode)
              RETURN m, type(r) AS rel_type, 6 AS rel_rank
            }
            WITH m, rel_type, rel_rank
            WHERE ($m_batch = '' OR m.import_batch = $m_batch)
              AND m.type IN $types
              AND m.node_id <> $node_id
            RETURN DISTINCT m.node_id AS node_id, m.name AS name, m.type AS type,
                   m.chapter AS chapter, m.section AS section,
                   m.section_node_id AS section_node_id,
                   m.source_code AS source_code, m.evidence_span AS evidence_span,
                   rel_type AS rel_type, rel_rank AS rel_rank
            ORDER BY rel_rank, m.name
            LIMIT $limit
            """,
            node_id=node["node_id"],
            m_batch=_import_batch(),
            types=list(CORE_LABELS),
            limit=limit,
        )
        support = [_node_map(row) for row in support_rows]

        extension_rows = session.run(
            """
            MATCH (n:KGNode {node_id: $node_id})
            CALL (n) {
              MATCH (m:KGNode)-[r:USES]->(n)
              RETURN m, type(r) AS rel_type, 0 AS rel_rank
              UNION
              WITH n
              MATCH (n)-[r:GETS|DERIVES|HAS_PROPERTY]->(m:KGNode)
              RETURN m, type(r) AS rel_type,
                     CASE type(r)
                       WHEN 'GETS' THEN 1
                       WHEN 'DERIVES' THEN 2
                       WHEN 'HAS_PROPERTY' THEN 3
                       ELSE 9
                     END AS rel_rank
              UNION
              WITH n
              MATCH (m:KGNode)-[r:SUPERIOR|PART_OF]->(n)
              RETURN m, type(r) AS rel_type,
                     CASE type(r)
                       WHEN 'SUPERIOR' THEN 4
                       WHEN 'PART_OF' THEN 5
                       ELSE 9
                     END AS rel_rank
            }
            WITH m, rel_type, rel_rank
            WHERE ($m_batch = '' OR m.import_batch = $m_batch)
              AND m.type IN $types
              AND m.node_id <> $node_id
            RETURN DISTINCT m.node_id AS node_id, m.name AS name, m.type AS type,
                   m.chapter AS chapter, m.section AS section,
                   m.section_node_id AS section_node_id,
                   m.source_code AS source_code, m.evidence_span AS evidence_span,
                   rel_type AS rel_type, rel_rank AS rel_rank
            ORDER BY rel_rank, m.name
            LIMIT $limit
            """,
            node_id=node["node_id"],
            m_batch=_import_batch(),
            types=list(CORE_LABELS),
            limit=limit,
        )
        extensions = [_node_map(row) for row in extension_rows]
    return support, extensions


def relation_neighbors_for_nodes(node_ids: list[str], book_id: str, limit: int = 24) -> list[dict]:
    node_ids = [node_id for node_id in node_ids if node_id]
    if not node_ids:
        return []
    with _session() as session:
        rows = session.run(
            """
            MATCH (n:KGNode)
            WHERE n.node_id IN $node_ids
            CALL (n) {
              MATCH (n)-[r:USES|SUPERIOR|PART_OF]->(m:KGNode)
              RETURN m, type(r) AS rel_type, 'out' AS direction,
                     CASE type(r)
                       WHEN 'USES' THEN 0
                       WHEN 'SUPERIOR' THEN 3
                       WHEN 'PART_OF' THEN 4
                       ELSE 9
                     END AS rel_rank
              UNION
              WITH n
              MATCH (m:KGNode)-[r:GETS|DERIVES|HAS_PROPERTY]->(n)
              RETURN m, type(r) AS rel_type, 'in' AS direction,
                     CASE type(r)
                       WHEN 'GETS' THEN 1
                       WHEN 'DERIVES' THEN 2
                       WHEN 'HAS_PROPERTY' THEN 5
                       ELSE 9
                     END AS rel_rank
              UNION
              WITH n
              MATCH (n)-[r:EQUATIVE]-(m:KGNode)
              RETURN m, type(r) AS rel_type, 'both' AS direction, 6 AS rel_rank
              UNION
              WITH n
              MATCH (n)-[r:GETS|DERIVES|HAS_PROPERTY]->(m:KGNode)
              RETURN m, type(r) AS rel_type, 'out' AS direction,
                     CASE type(r)
                       WHEN 'GETS' THEN 7
                       WHEN 'DERIVES' THEN 8
                       WHEN 'HAS_PROPERTY' THEN 9
                       ELSE 10
                     END AS rel_rank
            }
            WITH n, m, rel_type, direction, rel_rank
            WHERE ($m_batch = '' OR m.import_batch = $m_batch)
              AND m.type IN $types
              AND ($book_prefix = '' OR coalesce(m.section_node_id, m.source_code, '') STARTS WITH $book_prefix)
              AND NOT m.node_id IN $node_ids
            RETURN DISTINCT n.node_id AS source_node_id, n.name AS source_name,
                   m.node_id AS node_id, m.name AS name, m.type AS type,
                   m.chapter AS chapter, m.section AS section,
                   m.section_node_id AS section_node_id,
                   m.source_code AS source_code, m.evidence_span AS evidence_span,
                   rel_type, direction, rel_rank
            ORDER BY rel_rank, m.name
            LIMIT $limit
            """,
            node_ids=node_ids,
            m_batch=_import_batch(),
            types=list(CORE_LABELS),
            book_prefix=_book_prefix(book_id),
            limit=limit,
        )
        return [_node_rel_map(row) for row in rows]


def rule_cases_for_nodes(node_ids: list[str], book_id: str, limit: int = 5) -> list[dict]:
    node_ids = [node_id for node_id in node_ids if node_id]
    if not node_ids:
        return []
    with _session() as session:
        rows = session.run(
            """
            MATCH (owner:KGNode)-[:HAS_RULE_CASE]->(r:RuleCase)
            WHERE owner.node_id IN $node_ids
              AND ($owner_batch = '' OR owner.import_batch = $owner_batch)
              AND ($rule_batch = '' OR r.import_batch = $rule_batch)
              AND ($book_prefix = '' OR coalesce(owner.section_node_id, owner.source_code, r.source_code, '') STARTS WITH $book_prefix)
            OPTIONAL MATCH (r)-[condition_rel]->(c:ConditionExpression)
            WHERE type(condition_rel) IN ['HAS_CONDITION', 'HAS_CONDITION_AND', 'HAS_CONDITION_OR']
              AND ($condition_batch = '' OR c.import_batch = $condition_batch)
            OPTIONAL MATCH (r)-[outcome_rel]->(o:Outcome)
            WHERE type(outcome_rel) IN ['HAS_OUTCOME', 'HAS_OUTCOME_AND', 'HAS_OUTCOME_OR']
              AND ($outcome_batch = '' OR o.import_batch = $outcome_batch)
            RETURN owner.node_id AS owner_node_id,
                   owner.name AS owner_name,
                   owner.type AS owner_type,
                   r.name AS rule_case,
                   r.applies_to AS applies_to,
                   r.condition_logic AS condition_logic,
                   collect(DISTINCT c.name) AS conditions,
                   collect(DISTINCT o.name) AS outcomes,
                   r.source_code AS source_code,
                   r.evidence_span AS evidence_span
            ORDER BY owner.name, rule_case
            LIMIT $limit
            """,
            node_ids=node_ids,
            owner_batch=_import_batch(),
            rule_batch=_import_batch(),
            condition_batch=_import_batch(),
            outcome_batch=_import_batch(),
            book_prefix=_book_prefix(book_id),
            limit=limit,
        )
        return [_rule_case_map(row) for row in rows]


def get_rule_cases_for_node(concept_name: str, limit: int = 5) -> list[dict]:
    """按概念名查询规则案例。

    先通过概念名查找节点，再查询该节点关联的规则案例。
    返回规则案例列表，每条包含条件、结论、适用对象等。
    """
    node = find_node(concept_name)
    if not node or not node.get("node_id"):
        return []
    node_id = node["node_id"]
    book_id = _book_id_from_section(node.get("section_node_id") or node.get("source_code") or "")
    return rule_cases_for_nodes([node_id], book_id, limit=limit)


def prerequisite_candidates_for_section(section_node_id: str, limit: int = 12) -> list[str]:
    nodes = nodes_for_section(section_node_id, limit=20)
    if not nodes:
        return []
    book_id = _book_id_from_section(section_node_id)
    with _session() as session:
        rows = session.run(
            """
            MATCH (n:KGNode)-[r]-(m:KGNode)
            WHERE n.node_id IN $node_ids
              AND type(r) IN $rel_types
              AND ($m_batch = '' OR m.import_batch = $m_batch)
              AND m.type IN $types
              AND ($book_prefix = '' OR coalesce(m.section_node_id, m.source_code, '') STARTS WITH $book_prefix)
              AND NOT m.node_id IN $node_ids
            RETURN DISTINCT m.name AS name
            ORDER BY m.name
            LIMIT $limit
            """,
            node_ids=[n["node_id"] for n in nodes],
            rel_types=SUPPORT_REL_TYPES,
            m_batch=_import_batch(),
            types=list(CORE_LABELS),
            book_prefix=_book_prefix(book_id),
            limit=limit,
        )
        return [row["name"] for row in rows if row["name"]]
