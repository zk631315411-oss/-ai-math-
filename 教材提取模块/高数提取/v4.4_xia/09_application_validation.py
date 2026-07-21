# -*- coding: utf-8 -*-
"""
v4.4 Step 9: application-oriented validation for the imported KG.

This step does not extract, normalize, review, or import data. It asks a small
set of product-facing questions against Neo4j and records whether the current
graph can support the intended 智学助手 scenarios: lookup, tracing, learning
path, method recommendation, and rule-case based condition judgment.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
MODULE_DIR = SCRIPT_DIR.parents[1]
REPO_ROOT = SCRIPT_DIR.parents[2]
DEFAULT_OUT_DIR = SCRIPT_DIR / "中间产物" / "step9_application_validation"
ENV_PATHS = [REPO_ROOT / ".env", MODULE_DIR / ".env"]


DEFAULT_TESTS: list[dict[str, Any]] = [
    # ============== C07 向量与空间解析几何 ==============
    {
        "id": "node_vector",
        "kind": "node_lookup",
        "question": "C07：能否定位核心知识点：向量？",
        "keyword": "向量",
        "node_types": ["Concept"],
        "min_results": 1,
        "expected_terms_any": ["向量"],
    },
    {
        "id": "node_plane_normal_vector",
        "kind": "node_lookup",
        "question": "C07：能否定位核心知识点：平面的法向量？",
        "keyword": "平面的法向量",
        "node_types": ["Concept"],
        "min_results": 1,
        "expected_terms_any": ["法向量", "平面"],
    },
    {
        "id": "node_plane_point_normal_formula",
        "kind": "node_lookup",
        "question": "C07：能否定位平面的点法式方程？",
        "keyword": "平面的点法式方程",
        "node_types": ["Formula"],
        "min_results": 1,
        "expected_terms_any": ["点法式", "平面"],
    },
    {
        "id": "node_quadric_surface",
        "kind": "node_lookup",
        "question": "C07：能否定位核心知识点：二次曲面？",
        "keyword": "二次曲面",
        "node_types": ["Concept"],
        "min_results": 1,
        "expected_terms_any": ["二次曲面"],
    },
    # ============== C08 多元函数微分学 ==============
    {
        "id": "node_multivariable_function",
        "kind": "node_lookup",
        "question": "C08：能否定位核心知识点：多元函数？",
        "keyword": "多元函数",
        "node_types": ["Concept"],
        "min_results": 1,
        "expected_terms_any": ["多元函数"],
    },
    {
        "id": "node_partial_derivative",
        "kind": "node_lookup",
        "question": "C08：能否定位核心知识点：偏导数？",
        "keyword": "偏导数",
        "node_types": ["Concept", "Formula", "Theorem", "Method", "ProblemClass"],
        "min_results": 1,
        "expected_terms_any": ["偏导数", "偏导"],
    },
    {
        "id": "node_total_differential",
        "kind": "node_lookup",
        "question": "C08：能否定位核心知识点：全微分？",
        "keyword": "全微分",
        "node_types": ["Concept", "Formula", "Theorem", "Method"],
        "min_results": 1,
        "expected_terms_any": ["全微分"],
    },
    {
        "id": "node_chain_rule",
        "kind": "node_lookup",
        "question": "C08：能否定位多元复合函数偏导数链式法则？",
        "keyword": "链式法则",
        "node_types": ["Concept", "Theorem", "Method", "Formula"],
        "min_results": 1,
        "expected_terms_any": ["链式法则", "复合函数"],
    },
    # ============== C09 多元函数微分学几何应用 + 极值 ==============
    {
        "id": "node_directional_derivative",
        "kind": "node_lookup",
        "question": "C09：能否定位方向导数相关知识点？",
        "keyword": "方向导数",
        "node_types": ["Concept", "Formula", "Theorem"],
        "min_results": 1,
        "expected_terms_any": ["方向导数"],
    },
    {
        "id": "node_multivariable_extremum",
        "kind": "node_lookup",
        "question": "C09：能否定位核心知识点：多元函数的极值？",
        "keyword": "多元函数的极值",
        "node_types": ["Concept"],
        "min_results": 1,
        "expected_terms_any": ["多元函数", "极值"],
    },
    {
        "id": "node_lagrange_multiplier_method",
        "kind": "node_lookup",
        "question": "C09：能否定位拉格朗日乘数法？",
        "keyword": "拉格朗日乘数法",
        "node_types": ["Method"],
        "min_results": 1,
        "expected_terms_any": ["拉格朗日乘数法", "拉格朗日"],
    },
    {
        "id": "node_extremum_sufficient_condition",
        "kind": "node_lookup",
        "question": "C09：能否定位二阶偏导数判别极值的充分条件？",
        "keyword": "二阶偏导数判别极值的充分条件",
        "node_types": ["Theorem"],
        "min_results": 1,
        "expected_terms_any": ["二阶偏导数", "极值", "充分条件"],
        "semantic_fallback": True,
        "semantic_search_terms": ["二阶偏导数", "极值", "充分条件"],
        "min_semantic_score": 3,
    },
    # ============== C10 重积分 + 曲线曲面积分 ==============
    {
        "id": "node_double_integral",
        "kind": "node_lookup",
        "question": "C10：能否定位核心知识点：二重积分？",
        "keyword": "二重积分",
        "node_types": ["Concept", "Formula", "Theorem", "Method", "ProblemClass"],
        "min_results": 1,
        "expected_terms_any": ["二重积分"],
    },
    {
        "id": "node_triple_integral",
        "kind": "node_lookup",
        "question": "C10：能否定位核心知识点：三重积分？",
        "keyword": "三重积分",
        "node_types": ["Concept", "Formula", "Theorem"],
        "min_results": 1,
        "expected_terms_any": ["三重积分"],
    },
    {
        "id": "node_arc_length_integral",
        "kind": "node_lookup",
        "question": "C10：能否定位对弧长的曲线积分？",
        "keyword": "对弧长的曲线积分",
        "node_types": ["Concept", "Formula", "Theorem", "Method"],
        "min_results": 1,
        "expected_terms_any": ["对弧长", "曲线积分"],
    },
    {
        "id": "node_surface_integral",
        "kind": "node_lookup",
        "question": "C10：能否定位对面积的曲面积分？",
        "keyword": "对面积的曲面积分",
        "node_types": ["Concept", "Formula", "Theorem", "Method"],
        "min_results": 1,
        "expected_terms_any": ["对面积", "曲面积分"],
    },
    {
        "id": "node_polar_transform",
        "kind": "node_lookup",
        "question": "C10：能否定位极坐标变换方法？",
        "keyword": "极坐标变换",
        "node_types": ["Method", "Concept", "Formula"],
        "min_results": 1,
        "expected_terms_any": ["极坐标"],
    },
    # ============== 邻域（neighborhood）==============
    {
        "id": "neighborhood_directional_derivative",
        "kind": "neighborhood",
        "question": "C09：学生学方向导数时，能否找到偏导数、方向、可微等邻近支撑知识？",
        "anchor": "方向导数",
        "anchor_types": ["Concept", "Formula", "Theorem"],
        "max_depth": 3,
        "min_results": 2,
        "expected_terms_any": ["偏导数", "方向", "可微", "梯度"],
    },
    {
        "id": "neighborhood_double_integral",
        "kind": "neighborhood",
        "question": "C10：学生学二重积分时，能否找到积分区域、被积函数、面积元素等邻近支撑知识？",
        "anchor": "二重积分",
        "anchor_types": ["Concept"],
        "max_depth": 3,
        "min_results": 2,
        "expected_terms_any": ["积分区域", "被积函数", "面积元素", "积分和"],
    },
    {
        "id": "neighborhood_partial_derivative",
        "kind": "neighborhood",
        "question": "C08：学生学偏导数时，能否找到全微分、多元函数、高阶偏导数等邻近支撑知识？",
        "anchor": "偏导数",
        "anchor_types": ["Concept"],
        "max_depth": 3,
        "min_results": 2,
        "expected_terms_any": ["全微分", "多元函数", "高阶偏导数", "偏导"],
    },
    # ============== 方法推荐（method_recommendation）==============
    {
        "id": "recommend_extremum_methods",
        "kind": "method_recommendation",
        "question": "C09：学生求多元函数极值时，能否推荐拉格朗日乘数法、二阶偏导数判别等工具？",
        "anchor": "多元函数的极值",
        "anchor_types": ["Concept"],
        "anchor_exact": True,
        "max_depth": 4,
        "min_results": 1,
        "expected_terms_any": ["拉格朗日乘数法", "二阶偏导数判别", "极值", "充分条件", "最值存在性"],
    },
    {
        "id": "recommend_double_integral_methods",
        "kind": "method_recommendation",
        "question": "C10：学生计算二重积分时，能否推荐二次积分、极坐标变换、换元法等工具？",
        "anchor": "二重积分",
        "anchor_types": ["Concept"],
        "anchor_exact": True,
        "max_depth": 4,
        "min_results": 2,
        "expected_terms_any": ["二次积分", "极坐标", "换元", "累次积分"],
    },
    {
        "id": "recommend_implicit_function_methods",
        "kind": "method_recommendation",
        "question": "C08：学生求隐函数导数时，能否推荐由方程求一元隐函数导数的方法、由方程求二元隐函数偏导数的方法等工具？",
        "anchor": "隐函数",
        "anchor_types": ["Concept"],
        "max_depth": 4,
        "min_results": 2,
        "expected_terms_any": ["隐函数", "导数", "偏导", "方法"],
    },
    # ============== 路径（path_between）==============
    {
        "id": "path_partial_derivative_to_multivariable_function",
        "kind": "path_between",
        "question": "C08 路径验证：偏导数是否能追溯到多元函数？",
        "source": "偏导数",
        "target": "多元函数",
        "source_types": ["Concept"],
        "target_types": ["Concept"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 5,
        "min_results": 1,
        "expected_terms_all": ["偏导数", "多元函数"],
    },
    {
        "id": "path_second_order_partial_to_partial",
        "kind": "path_between",
        "question": "C08 路径验证：二阶偏导数是否能追溯到偏导数（SUPERIOR 关系）？",
        "source": "二阶偏导数",
        "target": "偏导数",
        "source_types": ["Concept"],
        "target_types": ["Concept"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 2,
        "min_results": 1,
        "expected_terms_all": ["二阶偏导数", "偏导数"],
    },
    {
        "id": "path_double_integral_to_iterated_integral",
        "kind": "path_between",
        "question": "C10 路径验证：二重积分是否能连到二重积分化为二次积分？",
        "source": "二重积分",
        "target": "二重积分化为二次积分",
        "source_types": ["Concept"],
        "target_types": ["Method"],
        "source_exact": True,
        "target_exact": False,
        "max_depth": 4,
        "min_results": 1,
        "expected_terms_all": ["二重积分", "二次积分"],
    },
    # ============== 规则案例（rule_outcome）==============
    {
        "id": "rule_extremum_judgment",
        "kind": "rule_outcome",
        "question": "C09：能否回答：多元函数在什么条件下取得极值（极大值/极小值）？",
        "outcome_keywords": ["极值", "极大值", "极小值"],
        "min_results": 1,
        "expected_terms_any": ["驻点", "极值", "二阶偏导数", "AC-B"],
    },
    {
        "id": "rule_lagrange_stationary_point",
        "kind": "rule_outcome",
        "question": "C09：能否回答：条件极值问题在什么条件下转化为拉格朗日函数的驻点？",
        "outcome_keywords": ["拉格朗日", "驻点"],
        "min_results": 1,
        "expected_terms_any": ["拉格朗日", "驻点", "条件极值"],
    },
    {
        "id": "rule_double_integral_to_iterated",
        "kind": "rule_outcome",
        "question": "C10：能否回答：二重积分在什么条件下可以化为二次积分？",
        "outcome_keywords": ["二次积分", "二重积分"],
        "min_results": 1,
        "expected_terms_any": ["连续", "有界闭区域", "二次积分"],
    },
    {
        "id": "rule_vector_perpendicular",
        "kind": "rule_outcome",
        "question": "C07：能否回答：两个非零向量在什么条件下相互垂直？",
        "outcome_keywords": ["垂直", "相互垂直"],
        "min_results": 1,
        "expected_terms_any": ["数量积", "垂直", "零"],
    },
]

def load_env_value(key: str) -> str:
    if os.environ.get(key):
        return os.environ[key]
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    return ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate v4.4 KG with application-facing Neo4j tests.")
    parser.add_argument("--uri", default=load_env_value("NEO4J_URI") or "neo4j://127.0.0.1:7687")
    parser.add_argument("--user", default=load_env_value("NEO4J_USER") or "neo4j")
    parser.add_argument("--password", default=load_env_value("NEO4J_PASSWORD") or "zhang2004")
    parser.add_argument("--database", default=load_env_value("NEO4J_DATABASE") or "neo4j")
    parser.add_argument("--import-batch", default="", help="Optional import_batch filter. Empty means all imported KGNode rows.")
    parser.add_argument("--tests", type=Path, default=None, help="Optional JSON file containing a list of tests.")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--limit", type=int, default=20)
    return parser.parse_args()


def load_tests(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return DEFAULT_TESTS
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, list):
        raise ValueError("--tests must point to a JSON list")
    return data


def safe_depth(value: Any, default: int = 3) -> int:
    try:
        depth = int(value)
    except Exception:
        return default
    return max(1, min(depth, 8))


def compact_text(value: Any, limit: int = 180) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def markdown_escape(value: Any) -> str:
    return compact_text(value).replace("|", "\\|").replace("\n", " ")


def run_records(session: Any, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    result = session.run(query, **params)
    return [dict(record) for record in result]


def node_lookup(session: Any, test: dict[str, Any], import_batch: str, limit: int) -> list[dict[str, Any]]:
    query = """
    MATCH (n:KGNode)
    WHERE ($import_batch = "" OR n.import_batch = $import_batch)
      AND ($node_types = [] OR n.type IN $node_types)
    WITH n,
         coalesce(n.name, "") + " " +
         reduce(text = "", alias IN coalesce(n.aliases, []) | text + " " + coalesce(alias, "")) + " " +
         coalesce(n.description, "") + " " +
         coalesce(n.evidence_span, "") AS row_text
    WITH n, row_text,
         size([term IN $search_terms WHERE row_text CONTAINS term]) AS semantic_score
    WHERE
      (
        $exact = true AND (
          n.name = $keyword
          OR any(alias IN coalesce(n.aliases, []) WHERE alias = $keyword)
        )
      )
      OR (
        $exact = false AND (
          n.name CONTAINS $keyword
          OR any(alias IN coalesce(n.aliases, []) WHERE alias CONTAINS $keyword)
          OR ($semantic_fallback = true AND semantic_score >= $min_semantic_score)
        )
      )
    RETURN n.name AS name,
           n.type AS type,
           n.chapter AS chapter,
           n.section AS section,
           left(coalesce(n.evidence_span, ""), 240) AS evidence,
           semantic_score
    ORDER BY CASE WHEN n.name = $keyword THEN 0 ELSE 1 END,
             semantic_score DESC,
             n.type,
             n.name
    LIMIT $limit
    """
    return run_records(session, query, {
        "keyword": test.get("keyword", ""),
        "exact": bool(test.get("exact", False)),
        "node_types": test.get("node_types", []),
        "search_terms": list(dict.fromkeys([
            str(term) for term in (
                test.get("semantic_search_terms")
                or test.get("expected_terms_all", [])
                or test.get("expected_terms_any", [])
            )
            if str(term)
        ])),
        "semantic_fallback": bool(test.get("semantic_fallback", False)),
        "min_semantic_score": int(test.get("min_semantic_score") or 1),
        "import_batch": import_batch,
        "limit": int(test.get("limit") or limit),
    })


def neighborhood(session: Any, test: dict[str, Any], import_batch: str, limit: int) -> list[dict[str, Any]]:
    depth = safe_depth(test.get("max_depth"), 3)
    query = f"""
    MATCH (a:KGNode)
    WHERE ($import_batch = "" OR a.import_batch = $import_batch)
      AND ($anchor_types = [] OR a.type IN $anchor_types)
      AND (
        a.name CONTAINS $anchor
        OR any(alias IN coalesce(a.aliases, []) WHERE alias CONTAINS $anchor)
      )
    MATCH p=(a)-[*1..{depth}]-(b:KGNode)
    WHERE ($import_batch = "" OR b.import_batch = $import_batch)
    RETURN a.name AS anchor,
           b.name AS target,
           b.type AS target_type,
           [node IN nodes(p) | coalesce(node.name, "")] AS path_nodes,
           [rel IN relationships(p) | type(rel)] AS rels,
           left(coalesce(head([rel IN relationships(p) WHERE coalesce(rel.evidence_span, "") <> "" | rel.evidence_span]), ""), 240) AS evidence
    ORDER BY length(p), b.type, b.name
    LIMIT $limit
    """
    return run_records(session, query, {
        "anchor": test.get("anchor", ""),
        "anchor_types": test.get("anchor_types", []),
        "import_batch": import_batch,
        "limit": int(test.get("limit") or limit),
    })


def method_recommendation(session: Any, test: dict[str, Any], import_batch: str, limit: int) -> list[dict[str, Any]]:
    depth = max(safe_depth(test.get("max_depth"), 4), 4)
    query = f"""
    MATCH (a:KGNode)
    WHERE ($import_batch = "" OR a.import_batch = $import_batch)
      AND ($anchor_types = [] OR a.type IN $anchor_types)
      AND (
        ($anchor_exact = true AND a.name = $anchor)
        OR ($anchor_exact = false AND a.name CONTAINS $anchor)
      )
    MATCH p=(a)-[*1..{depth}]-(m:KGNode)
    WHERE ($import_batch = "" OR m.import_batch = $import_batch)
      AND m.type IN ["Method", "ProblemClass", "Formula", "Theorem"]
    WITH DISTINCT a, m, p,
         coalesce(m.name, "") + " " +
         coalesce(m.description, "") + " " +
         coalesce(m.evidence_span, "") + " " +
         reduce(text = "", node IN nodes(p) | text + " " + coalesce(node.name, "")) AS row_text
    WITH a, m, p, row_text,
         size([term IN $expected_terms_any WHERE row_text CONTAINS term]) AS expected_term_score,
         CASE m.type
           WHEN "Method" THEN 0
           WHEN "ProblemClass" THEN 1
           WHEN "Formula" THEN 2
           WHEN "Theorem" THEN 3
           ELSE 4
         END AS type_rank,
         size([rel IN relationships(p) WHERE type(rel) IN ["USES", "HAS_PROPERTY", "GETS", "DERIVES", "SUPERIOR", "PART_OF", "EQUATIVE"]]) AS semantic_edge_count,
         size([rel IN relationships(p) WHERE type(rel) IN ["HAS_MEMBER", "HAS_ANCHOR"]]) AS group_edge_count,
         length(p) AS path_length,
         CASE WHEN a.name = $anchor THEN 0 ELSE 1 END AS anchor_rank
    ORDER BY type_rank,
             expected_term_score DESC,
             anchor_rank,
             semantic_edge_count DESC,
             group_edge_count ASC,
             path_length,
             m.name
    WITH a, m, collect({{
           rels: [rel IN relationships(p) | type(rel)],
           path_nodes: [node IN nodes(p) | coalesce(node.name, "")],
           expected_term_score: expected_term_score,
           type_rank: type_rank,
           semantic_edge_count: semantic_edge_count,
           group_edge_count: group_edge_count,
           path_length: path_length,
           anchor_rank: anchor_rank
         }})[0] AS best
    RETURN a.name AS anchor,
           m.name AS recommended,
           m.type AS recommended_type,
           best.rels AS rels,
           best.path_nodes AS path_nodes,
           left(coalesce(m.evidence_span, ""), 240) AS evidence,
           best.expected_term_score AS expected_term_score,
           best.type_rank AS type_rank,
           best.semantic_edge_count AS semantic_edge_count,
           best.group_edge_count AS group_edge_count,
           best.path_length AS path_length,
           best.anchor_rank AS anchor_rank
    ORDER BY type_rank,
             expected_term_score DESC,
             anchor_rank,
             semantic_edge_count DESC,
             group_edge_count ASC,
             path_length,
             m.name
    LIMIT $limit
    """
    return run_records(session, query, {
        "anchor": test.get("anchor", ""),
        "anchor_types": test.get("anchor_types", []),
        "anchor_exact": bool(test.get("anchor_exact", False)),
        "expected_terms_any": [str(term) for term in test.get("expected_terms_any", [])],
        "import_batch": import_batch,
        "limit": int(test.get("limit") or limit),
    })


def path_between(session: Any, test: dict[str, Any], import_batch: str, limit: int) -> list[dict[str, Any]]:
    depth = safe_depth(test.get("max_depth"), 5)
    query = f"""
    MATCH (a:KGNode), (b:KGNode)
    WHERE ($import_batch = "" OR a.import_batch = $import_batch)
      AND ($import_batch = "" OR b.import_batch = $import_batch)
      AND ($source_types = [] OR a.type IN $source_types)
      AND ($target_types = [] OR b.type IN $target_types)
      AND (($source_exact = true AND a.name = $source) OR ($source_exact = false AND a.name CONTAINS $source))
      AND (($target_exact = true AND b.name = $target) OR ($target_exact = false AND b.name CONTAINS $target))
      AND a.node_id <> b.node_id
    MATCH p=shortestPath((a)-[*1..{depth}]-(b))
    RETURN a.name AS source,
           b.name AS target,
           [node IN nodes(p) | coalesce(node.name, "")] AS path_nodes,
           [rel IN relationships(p) | type(rel)] AS rels,
           length(p) AS path_length
    ORDER BY path_length, source, target
    LIMIT $limit
    """
    return run_records(session, query, {
        "source": test.get("source", ""),
        "target": test.get("target", ""),
        "source_exact": bool(test.get("source_exact", False)),
        "target_exact": bool(test.get("target_exact", False)),
        "source_types": test.get("source_types", []),
        "target_types": test.get("target_types", []),
        "import_batch": import_batch,
        "limit": int(test.get("limit") or limit),
    })


def rule_outcome(session: Any, test: dict[str, Any], import_batch: str, limit: int) -> list[dict[str, Any]]:
    query = """
    MATCH (r:RuleCase)-[:HAS_OUTCOME]->(o:Outcome)
    WHERE ($import_batch = "" OR r.import_batch = $import_batch)
      AND ($import_batch = "" OR o.import_batch = $import_batch)
      AND any(keyword IN $outcome_keywords WHERE o.name CONTAINS keyword OR r.name CONTAINS keyword)
    OPTIONAL MATCH (owner:KGNode)-[:HAS_RULE_CASE]->(r)
    OPTIONAL MATCH (r)-[condition_rel]->(c:ConditionExpression)
    WHERE type(condition_rel) IN ["HAS_CONDITION", "HAS_CONDITION_AND", "HAS_CONDITION_OR"]
    WITH r, owner, collect(DISTINCT c.name) AS conditions, collect(DISTINCT o.name) AS outcomes
    WITH r, owner, conditions, outcomes,
         coalesce(r.name, "") + " " +
         coalesce(owner.name, "") + " " +
         coalesce(r.applies_to, "") + " " +
         reduce(text = "", item IN conditions | text + " " + coalesce(item, "")) + " " +
         reduce(text = "", item IN outcomes | text + " " + coalesce(item, "")) + " " +
         coalesce(r.evidence_span, "") AS row_text
    WITH r, owner, conditions, outcomes, row_text,
         size([term IN $expected_terms_any WHERE row_text CONTAINS term]) AS any_score,
         size([term IN $expected_terms_all WHERE row_text CONTAINS term]) AS all_score
    RETURN r.name AS rule_case,
           owner.name AS owner,
           r.applies_to AS applies_to,
           r.condition_logic AS condition_logic,
           conditions,
           outcomes,
           left(coalesce(r.evidence_span, ""), 260) AS evidence,
           any_score,
           all_score
    ORDER BY all_score DESC, any_score DESC, owner, rule_case
    LIMIT $limit
    """
    outcome_keywords = test.get("outcome_keywords") or [test.get("outcome_keyword", "")]
    return run_records(session, query, {
        "outcome_keywords": [str(keyword) for keyword in outcome_keywords if str(keyword)],
        "expected_terms_any": [str(term) for term in test.get("expected_terms_any", [])],
        "expected_terms_all": [str(term) for term in test.get("expected_terms_all", [])],
        "import_batch": import_batch,
        "limit": int(test.get("limit") or limit),
    })


def rulecase_by_owner(session: Any, test: dict[str, Any], import_batch: str, limit: int) -> list[dict[str, Any]]:
    query = """
    MATCH (owner:KGNode)-[:HAS_RULE_CASE]->(r:RuleCase)
    WHERE ($import_batch = "" OR owner.import_batch = $import_batch)
      AND ($import_batch = "" OR r.import_batch = $import_batch)
      AND ($owner_types = [] OR owner.type IN $owner_types)
      AND (
        ($exact = true AND (
          owner.name = $owner
          OR any(alias IN coalesce(owner.aliases, []) WHERE alias = $owner)
        ))
        OR
        ($exact = false AND (
          owner.name CONTAINS $owner
          OR any(alias IN coalesce(owner.aliases, []) WHERE alias CONTAINS $owner)
        ))
      )
    OPTIONAL MATCH (r)-[condition_rel]->(c:ConditionExpression)
    WHERE type(condition_rel) IN ["HAS_CONDITION", "HAS_CONDITION_AND", "HAS_CONDITION_OR"]
    OPTIONAL MATCH (r)-[:HAS_OUTCOME]->(o:Outcome)
    RETURN owner.name AS owner,
           owner.type AS owner_type,
           r.name AS rule_case,
           r.applies_to AS applies_to,
           r.condition_logic AS condition_logic,
           collect(DISTINCT c.name) AS conditions,
           collect(DISTINCT o.name) AS outcomes,
           left(coalesce(r.evidence_span, ""), 300) AS evidence
    ORDER BY owner.name, rule_case
    LIMIT $limit
    """
    return run_records(session, query, {
        "owner": test.get("owner", ""),
        "exact": bool(test.get("exact", False)),
        "owner_types": test.get("owner_types", []),
        "import_batch": import_batch,
        "limit": int(test.get("limit") or limit),
    })


def rulecase_bridge(session: Any, test: dict[str, Any], import_batch: str, limit: int) -> list[dict[str, Any]]:
    query = """
    MATCH (owner:KGNode)-[:HAS_RULE_CASE]->(r:RuleCase)
    WHERE ($import_batch = "" OR owner.import_batch = $import_batch)
      AND ($import_batch = "" OR r.import_batch = $import_batch)
      AND ($owner_types = [] OR owner.type IN $owner_types)
      AND (
        ($exact = true AND (
          owner.name = $owner
          OR any(alias IN coalesce(owner.aliases, []) WHERE alias = $owner)
        ))
        OR
        ($exact = false AND (
          owner.name CONTAINS $owner
          OR any(alias IN coalesce(owner.aliases, []) WHERE alias CONTAINS $owner)
        ))
      )
    OPTIONAL MATCH (r)-[condition_rel]->(c:ConditionExpression)
    WHERE type(condition_rel) IN ["HAS_CONDITION", "HAS_CONDITION_AND", "HAS_CONDITION_OR"]
    OPTIONAL MATCH (r)-[:HAS_OUTCOME]->(o:Outcome)
    WITH owner, r,
         collect(DISTINCT c.name) AS conditions,
         collect(DISTINCT o.name) AS outcomes
    WITH owner, r, conditions, outcomes,
         coalesce(r.name, "") + " " +
         coalesce(r.applies_to, "") + " " +
         coalesce(r.evidence_span, "") + " " +
         reduce(text = "", item IN conditions | text + " " + coalesce(item, "")) + " " +
         reduce(text = "", item IN outcomes | text + " " + coalesce(item, "")) AS searchable_text
    WHERE any(keyword IN $bridge_keywords WHERE searchable_text CONTAINS keyword)
    RETURN owner.name AS owner,
           owner.type AS owner_type,
           r.name AS rule_case,
           r.applies_to AS applies_to,
           r.condition_logic AS condition_logic,
           conditions AS conditions,
           outcomes AS outcomes,
           [keyword IN $bridge_keywords WHERE searchable_text CONTAINS keyword] AS matched_bridge_keywords,
           left(coalesce(r.evidence_span, ""), 300) AS evidence
    ORDER BY size([keyword IN $bridge_keywords WHERE searchable_text CONTAINS keyword]) DESC,
             owner.name,
             rule_case
    LIMIT $limit
    """
    bridge_keywords = test.get("bridge_keywords") or [test.get("bridge_keyword", "")]
    return run_records(session, query, {
        "owner": test.get("owner", ""),
        "exact": bool(test.get("exact", False)),
        "owner_types": test.get("owner_types", []),
        "bridge_keywords": [str(keyword) for keyword in bridge_keywords if str(keyword)],
        "import_batch": import_batch,
        "limit": int(test.get("limit") or limit),
    })


def run_test(session: Any, test: dict[str, Any], import_batch: str, limit: int) -> dict[str, Any]:
    handlers = {
        "node_lookup": node_lookup,
        "neighborhood": neighborhood,
        "method_recommendation": method_recommendation,
        "path_between": path_between,
        "rule_outcome": rule_outcome,
        "rulecase_by_owner": rulecase_by_owner,
        "rulecase_bridge": rulecase_bridge,
    }
    kind = str(test.get("kind") or "")
    if kind not in handlers:
        raise ValueError(f"Unknown test kind: {kind}")
    rows = handlers[kind](session, test, import_batch, limit)
    return evaluate_test(test, rows)


def evaluate_test(test: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    min_results = int(test.get("min_results") or 1)
    result_text = json_text(rows)
    missing_all = [term for term in test.get("expected_terms_all", []) if str(term) not in result_text]
    any_terms = [str(term) for term in test.get("expected_terms_any", [])]
    matched_any = [term for term in any_terms if term in result_text]
    row_all_terms = [str(term) for term in test.get("row_expected_terms_all", [])]
    row_any_terms = [str(term) for term in test.get("row_expected_terms_any", [])]
    qualifying_rows = [
        row for row in rows
        if row_satisfies_terms(row, row_all_terms, row_any_terms)
    ]

    enough = len(rows) >= min_results
    all_ok = not missing_all
    any_ok = not any_terms or bool(matched_any)
    row_ok = not (row_all_terms or row_any_terms) or bool(qualifying_rows)

    if enough and all_ok and any_ok and row_ok:
        status = "pass"
    elif rows:
        status = "partial"
    else:
        status = "fail"

    reasons: list[str] = []
    if not enough:
        reasons.append(f"结果数不足：期望至少 {min_results}，实际 {len(rows)}")
    if missing_all:
        reasons.append("缺少必要词：" + "、".join(missing_all))
    if any_terms and not matched_any:
        reasons.append("未命中任一关键提示词：" + "、".join(any_terms))
    if not row_ok:
        parts = []
        if row_all_terms:
            parts.append("同一条结果需包含全部：" + "、".join(row_all_terms))
        if row_any_terms:
            parts.append("同一条结果需命中任一：" + "、".join(row_any_terms))
        reasons.append("没有单条结果满足行级验收条件：" + "；".join(parts))
    if not reasons:
        reasons.append("命中数量和关键提示词均满足当前验收条件")

    return {
        "id": test.get("id", ""),
        "kind": test.get("kind", ""),
        "question": test.get("question", ""),
        "status": status,
        "result_count": len(rows),
        "matched_any_terms": matched_any,
        "missing_all_terms": missing_all,
        "qualifying_row_count": len(qualifying_rows),
        "reasons": reasons,
        "rows": rows,
        "test": test,
    }


def row_satisfies_terms(row: dict[str, Any], all_terms: list[str], any_terms: list[str]) -> bool:
    if not all_terms and not any_terms:
        return True
    row_text = json_text(row)
    if any(term not in row_text for term in all_terms):
        return False
    if any_terms and not any(term in row_text for term in any_terms):
        return False
    return True


def fetch_graph_summary(session: Any, import_batch: str) -> dict[str, Any]:
    params = {"import_batch": import_batch}
    node_rows = run_records(session, """
    MATCH (n:KGNode)
    WHERE ($import_batch = "" OR n.import_batch = $import_batch)
    RETURN n.type AS type, count(n) AS count
    ORDER BY type
    """, params)
    edge_rows = run_records(session, """
    MATCH ()-[r]->()
    WHERE ($import_batch = "" OR r.import_batch = $import_batch)
    RETURN type(r) AS type, count(r) AS count
    ORDER BY type
    """, params)
    isolated = run_records(session, """
    MATCH (n:KGNode)
    WHERE ($import_batch = "" OR n.import_batch = $import_batch)
      AND NOT (n)--()
    RETURN n.type AS type, count(n) AS count
    ORDER BY type
    """, params)
    semantic_isolated = run_records(session, """
    MATCH (n:KGNode)
    WHERE ($import_batch = "" OR n.import_batch = $import_batch)
      AND NOT (n)-[:APPLIES_TO|DERIVES|GETS|HAS_CONDITION|HAS_CONDITION_AND|HAS_OUTCOME|HAS_PROPERTY|HAS_RULE_CASE|REFERS_TO|SUPERIOR|USES]-()
    RETURN n.type AS type, count(n) AS count
    ORDER BY type
    """, params)
    core_semantic_isolated = run_records(session, """
    MATCH (n:KGNode)
    WHERE ($import_batch = "" OR n.import_batch = $import_batch)
      AND n.type IN ["Concept", "Theorem", "Formula", "Method"]
      AND NOT (n)-[:APPLIES_TO|DERIVES|GETS|HAS_CONDITION|HAS_CONDITION_AND|HAS_OUTCOME|HAS_PROPERTY|HAS_RULE_CASE|REFERS_TO|SUPERIOR|USES]-()
    RETURN n.type AS type, count(n) AS count
    ORDER BY type
    """, params)
    return {
        "node_types": node_rows,
        "edge_types": edge_rows,
        "isolated_node_types": isolated,
        "semantic_isolated_node_types": semantic_isolated,
        "core_semantic_isolated_node_types": core_semantic_isolated,
        "node_total": sum(row["count"] for row in node_rows),
        "edge_total": sum(row["count"] for row in edge_rows),
        "isolated_total": sum(row["count"] for row in isolated),
        "semantic_isolated_total": sum(row["count"] for row in semantic_isolated),
        "core_semantic_isolated_total": sum(row["count"] for row in core_semantic_isolated),
    }


def write_outputs(out_dir: Path, results: list[dict[str, Any]], summary: dict[str, Any], args: argparse.Namespace) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    result_path = out_dir / "step9_application_validation_results.json"
    report_path = out_dir / "step9_application_validation_report.md"
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "database": args.database,
        "import_batch": args.import_batch,
        "summary": summary,
        "results": results,
    }
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(build_report(payload), encoding="utf-8")


def build_report(payload: dict[str, Any]) -> str:
    results = payload["results"]
    status_counts = Counter(row["status"] for row in results)
    summary = payload["summary"]
    lines = [
        "# v4.4 Step 9 应用验证报告",
        "",
        f"- generated_at: `{payload['generated_at']}`",
        f"- database: `{payload['database']}`",
        f"- import_batch: `{payload['import_batch'] or '(all KGNode)'}`",
        f"- graph_nodes: {summary['node_total']}",
        f"- graph_edges: {summary['edge_total']}",
        f"- structural_isolated_nodes: {summary['isolated_total']}",
        f"- semantic_isolated_nodes_ignoring_groups: {summary['semantic_isolated_total']}",
        f"- core_semantic_isolated_nodes_ignoring_groups: {summary['core_semantic_isolated_total']}",
        f"- tests: {len(results)}",
        f"- pass / partial / fail: {status_counts.get('pass', 0)} / {status_counts.get('partial', 0)} / {status_counts.get('fail', 0)}",
        "",
        "## 图谱结构概览",
        "",
        "### 节点类型",
    ]
    for row in summary["node_types"]:
        lines.append(f"- {row['type']}: {row['count']}")
    lines.extend(["", "### 关系类型"])
    for row in summary["edge_types"]:
        lines.append(f"- {row['type']}: {row['count']}")
    lines.extend(["", "### 孤立节点"])
    if summary["isolated_node_types"]:
        for row in summary["isolated_node_types"]:
            lines.append(f"- {row['type']}: {row['count']}")
    else:
        lines.append("- 0")

    lines.extend(["", "### 忽略知识组边后的语义孤立节点"])
    lines.append("- 口径：不把 `HAS_MEMBER`、`HAS_ANCHOR` 计为数学语义关系。")
    if summary["semantic_isolated_node_types"]:
        for row in summary["semantic_isolated_node_types"]:
            lines.append(f"- {row['type']}: {row['count']}")
    else:
        lines.append("- 0")

    lines.extend(["", "### 核心知识点语义孤立节点"])
    lines.append("- 口径：只统计 Concept、Theorem、Formula、Method，且忽略知识组边。")
    if summary["core_semantic_isolated_node_types"]:
        for row in summary["core_semantic_isolated_node_types"]:
            lines.append(f"- {row['type']}: {row['count']}")
    else:
        lines.append("- 0")

    lines.extend([
        "",
        "## 测试结果总表",
        "",
        "| ID | 任务 | 结果 | 命中数 | 判断依据 |",
        "|---|---|---:|---:|---|",
    ])
    for result in results:
        lines.append(
            f"| {markdown_escape(result['id'])} | {markdown_escape(result['question'])} | "
            f"{result['status']} | {result['result_count']} | {markdown_escape('; '.join(result['reasons']))} |"
        )

    lines.extend(["", "## 逐项结果"])
    for result in results:
        lines.extend([
            "",
            f"### {result['id']}：{result['status']}",
            "",
            f"- 问题：{result['question']}",
            f"- 类型：`{result['kind']}`",
            f"- 命中数：{result['result_count']}",
            f"- 判断依据：{'；'.join(result['reasons'])}",
        ])
        rows = result["rows"][:8]
        if not rows:
            lines.append("- 返回：无")
            continue
        lines.extend(["", "| 返回摘要 |", "|---|"])
        for row in rows:
            lines.append(f"| {markdown_escape(row)} |")

    lines.extend([
        "",
        "## 解释原则",
        "",
        "- pass：结果数量达到最低要求，并命中预设关键提示词。",
        "- partial：能返回结果，但数量或关键提示词不足，需要人工判断是否可接受。",
        "- fail：没有返回结果，说明当前图谱不能支撑该应用问题。",
        "- Step 9 只验证应用可用性，不反向修改图谱；修正应回到抽取、关系定义或审核环节。",
        "",
    ])
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    tests = load_tests(args.tests)
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.password))
    try:
        driver.verify_connectivity()
        # Bolt 6 在显式指定默认数据库时会触发路由表查找失败；
        # 当 database 为空或等于默认数据库时传 None，让 driver 走默认数据库。
        session_db = args.database if args.database and args.database not in {"neo4j", "default"} else None
        with driver.session(database=session_db) as session:
            summary = fetch_graph_summary(session, args.import_batch)
            results = [run_test(session, test, args.import_batch, args.limit) for test in tests]
    finally:
        driver.close()

    write_outputs(args.out_dir, results, summary, args)
    counts = Counter(row["status"] for row in results)
    print(f"[OK] Step 9 report -> {args.out_dir / 'step9_application_validation_report.md'}")
    print(f"[OK] Step 9 results -> {args.out_dir / 'step9_application_validation_results.json'}")
    print(json.dumps({
        "tests": len(results),
        "pass": counts.get("pass", 0),
        "partial": counts.get("partial", 0),
        "fail": counts.get("fail", 0),
        "graph_nodes": summary["node_total"],
        "graph_edges": summary["edge_total"],
        "structural_isolated_nodes": summary["isolated_total"],
        "semantic_isolated_nodes_ignoring_groups": summary["semantic_isolated_total"],
        "core_semantic_isolated_nodes_ignoring_groups": summary["core_semantic_isolated_total"],
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()

