"""Read-only Neo4j preflight for canonical textbook practice assets."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import config
from app.textbooks import TEXTBOOKS


TARGET_SCOPES = {
    "matrix_rank_and_system": {
        "textbook_id": "gaodai_shang",
        "chapter_prefix": "gaodai_shang:C03",
        "concept_aliases": [
            {"aliases": ["矩阵的秩", "矩阵秩"], "search_terms": ["矩阵", "秩"]},
            {"label": "极大线性无关组", "aliases": ["极大线性无关组求取"], "search_terms": ["极大线性无关组"]},
            {"label": "线性方程组", "aliases": ["线性方程组解的个数判定定理"], "search_terms": ["线性方程组"]},
        ],
    },
    "linear_independence_proof": {
        "textbook_id": "gaodai_shang",
        "chapter_prefix": "gaodai_shang:C03",
        "concept_aliases": [
            {"label": "线性无关", "aliases": ["线性无关", "线性相关与线性无关"], "search_terms": ["线性无关"]},
            {"label": "线性组合", "aliases": ["线性组合"], "search_terms": ["线性组合"]},
            {"label": "齐次线性方程组", "aliases": ["线性无关的齐次线性方程组判定"], "search_terms": ["齐次线性方程组"]},
        ],
    },
    "limit_calculation_concept_misuse": {
        "textbook_id": "gaoshu_shang",
        "chapter_prefix": "gaoshu_shang:C01",
        "concept_aliases": [
            {"aliases": ["函数极限", "函数的极限"], "search_terms": ["函数极限"]},
            {"label": "极限运算法则", "aliases": ["极限的四则运算法则"], "search_terms": ["运算法则"]},
            {"label": "极限运算法则的适用条件", "aliases": ["复合函数极限代换法适用条件"], "search_terms": ["适用条件"]},
        ],
    },
}


def _database() -> str | None:
    value = os.getenv("NEO4J_DATABASE", "neo4j").strip()
    return None if value in {"", "neo4j", "default"} else value


def _batch() -> str:
    return os.getenv("KG_IMPORT_BATCH", "").strip()


def run_preflight() -> dict[str, Any]:
    report: dict[str, Any] = {
        "uri": config.NEO4J_URI,
        "database": _database() or "neo4j",
        "import_batch": _batch() or None,
        "status": "blocked",
        "errors": [],
        "warnings": [],
        "textbooks": {},
        "cases": {},
    }
    if not config.NEO4J_PASSWORD:
        report["errors"].append("NEO4J_PASSWORD is not configured")
        return report

    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(
        config.NEO4J_URI,
        auth=(config.NEO4J_USER, config.NEO4J_PASSWORD),
        connection_timeout=2.0,
        max_connection_pool_size=2,
    )
    try:
        driver.verify_connectivity()
        with driver.session(database=_database(), default_access_mode="READ") as session:
            batches = session.run(
                "MATCH (n:KGNode) WHERE n.import_batch IS NOT NULL "
                "RETURN n.import_batch AS batch, count(*) AS count ORDER BY count DESC"
            ).data()
            report["available_import_batches"] = batches
            if not _batch():
                report["warnings"].append(
                    "KG_IMPORT_BATCH is empty; checks include every import batch"
                )

            for spec in TEXTBOOKS.values():
                prefix = f"{spec.neo4j_prefix}:"
                row = session.run(
                    """
                    MATCH (n:KGNode)
                    WHERE coalesce(n.section_node_id, n.source_code, '') STARTS WITH $prefix
                      AND ($batch = '' OR n.import_batch = $batch)
                    RETURN count(DISTINCT n) AS node_count,
                           collect(DISTINCT substring(coalesce(n.section_node_id, n.source_code, ''), 0, size($prefix) + 3))[0..20] AS chapters
                    """,
                    prefix=prefix,
                    batch=_batch(),
                ).single()
                data = dict(row) if row else {"node_count": 0, "chapters": []}
                report["textbooks"][spec.id.value] = data
                if not data["node_count"]:
                    report["errors"].append(f"no KG nodes found for {spec.id.value}")

            for case_name, scope in TARGET_SCOPES.items():
                concepts = []
                resolved_ids = []
                for concept_spec in scope["concept_aliases"]:
                    aliases = concept_spec["aliases"]
                    rows = session.run(
                        """
                        MATCH (n:KGNode)
                        WHERE n.name IN $aliases
                          AND coalesce(n.section_node_id, n.source_code, '') STARTS WITH $chapter_prefix
                          AND ($batch = '' OR n.import_batch = $batch)
                        RETURN DISTINCT n.node_id AS node_id, n.name AS name,
                               n.section_node_id AS section_node_id, n.source_code AS source_code
                        ORDER BY n.node_id
                        """,
                        aliases=aliases,
                        chapter_prefix=scope["chapter_prefix"],
                        batch=_batch(),
                    ).data()
                    status = "verified" if len(rows) == 1 else ("missing" if not rows else "ambiguous")
                    suggestions = []
                    if status != "verified":
                        suggestions = session.run(
                            """
                            MATCH (n:KGNode)
                            WHERE any(term IN $terms WHERE n.name CONTAINS term)
                              AND coalesce(n.section_node_id, n.source_code, '') STARTS WITH $chapter_prefix
                              AND ($batch = '' OR n.import_batch = $batch)
                            RETURN DISTINCT n.node_id AS node_id, n.name AS name, n.type AS type,
                                   n.section_node_id AS section_node_id, n.source_code AS source_code
                            ORDER BY n.section_node_id, n.type, n.name
                            LIMIT 100
                            """,
                            terms=concept_spec["search_terms"],
                            chapter_prefix=scope["chapter_prefix"],
                            batch=_batch(),
                        ).data()
                    concepts.append({
                        "requested_concept": concept_spec.get("label", aliases[0]),
                        "aliases": aliases,
                        "status": status,
                        "matches": rows,
                        "suggestions": suggestions,
                    })
                    if status == "verified":
                        resolved_ids.append(rows[0]["node_id"])
                    else:
                        report["errors"].append(
                            f"{case_name}: {aliases[0]} mapping is {status}"
                        )
                relation_count = 0
                if resolved_ids:
                    row = session.run(
                        """
                        MATCH (a:KGNode)-[r]-(b:KGNode)
                        WHERE a.node_id IN $node_ids
                          AND coalesce(b.section_node_id, b.source_code, '') STARTS WITH $book_prefix
                          AND ($batch = '' OR b.import_batch = $batch)
                        RETURN count(DISTINCT [a.node_id, type(r), b.node_id]) AS relation_count
                        """,
                        node_ids=resolved_ids,
                        book_prefix=f"{scope['textbook_id']}:",
                        batch=_batch(),
                    ).single()
                    relation_count = int(row["relation_count"] if row else 0)
                if resolved_ids and relation_count == 0:
                    report["errors"].append(f"{case_name}: resolved concepts have no scoped one-hop relations")
                report["cases"][case_name] = {
                    "textbook_id": scope["textbook_id"],
                    "chapter_prefix": scope["chapter_prefix"],
                    "concepts": concepts,
                    "one_hop_relation_count": relation_count,
                }
    except Exception as exc:
        report["errors"].append(f"Neo4j preflight failed: {type(exc).__name__}: {exc}")
    finally:
        driver.close()

    report["status"] = "ready" if not report["errors"] else "blocked"
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=ROOT / "data/practice/neo4j-preflight-report.json")
    args = parser.parse_args()
    report = run_preflight()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
