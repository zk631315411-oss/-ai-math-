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
    {
        "id": "node_function_limit",
        "kind": "node_lookup",
        "question": "能否定位核心知识点：函数极限？",
        "keyword": "函数极限",
        "node_types": ["Concept"],
        "min_results": 1,
        "expected_terms_any": ["函数极限", "极限"],
    },
    {
        "id": "node_derivative",
        "kind": "node_lookup",
        "question": "能否定位核心知识点：导数？",
        "keyword": "导数",
        "node_types": ["Concept", "Formula", "Theorem", "Method"],
        "min_results": 1,
        "expected_terms_any": ["导数"],
    },
    {
        "id": "node_definite_integral",
        "kind": "node_lookup",
        "question": "能否定位核心知识点：定积分？",
        "keyword": "定积分",
        "node_types": ["Concept", "Formula", "Theorem", "Method"],
        "min_results": 1,
        "expected_terms_any": ["定积分"],
    },
    {
        "id": "node_lhopital",
        "kind": "node_lookup",
        "question": "能否定位洛必达法则相关知识点？",
        "keyword": "洛必达",
        "node_types": ["Theorem", "Method", "Formula"],
        "min_results": 1,
        "expected_terms_any": ["洛必达", "L'Hospital", "罗必达"],
    },
    {
        "id": "node_variable_limit_integral",
        "kind": "node_lookup",
        "question": "能否定位第4章核心知识点：变限积分？",
        "keyword": "变限积分",
        "node_types": ["Concept", "Formula", "Theorem", "Method"],
        "min_results": 1,
        "expected_terms_any": ["变限积分", "积分上限函数", "变上限积分"],
    },
    {
        "id": "node_average_value",
        "kind": "node_lookup",
        "question": "能否定位第5章应用知识点：平均值？",
        "keyword": "平均值",
        "node_types": ["Concept", "Formula", "Theorem", "Method"],
        "min_results": 1,
        "expected_terms_any": ["平均值", "电流有效值", "平均功率"],
    },
    {
        "id": "node_ordinary_differential_equation",
        "kind": "node_lookup",
        "question": "能否定位第6章核心知识点：常微分方程？",
        "keyword": "常微分方程",
        "node_types": ["Concept", "Formula", "Theorem", "Method", "ProblemClass"],
        "min_results": 1,
        "expected_terms_any": ["常微分方程", "微分方程"],
    },
    {
        "id": "node_first_order_linear_ode",
        "kind": "node_lookup",
        "question": "能否定位第6章核心知识点：一阶线性微分方程？",
        "keyword": "一阶线性微分方程",
        "node_types": ["Concept", "Formula", "Theorem", "Method", "ProblemClass"],
        "min_results": 1,
        "expected_terms_all": ["一阶线性微分方程"],
    },
    {
        "id": "trace_lhopital",
        "kind": "neighborhood",
        "question": "学生不会洛必达法则时，能否找到导数、极限、不定式等邻近支撑知识？",
        "anchor": "洛必达",
        "anchor_types": ["Theorem", "Method", "Formula"],
        "max_depth": 3,
        "min_results": 2,
        "expected_terms_any": ["导数", "极限", "不定式", "函数"],
    },
    {
        "id": "recommend_integral_methods",
        "kind": "method_recommendation",
        "question": "学习积分时，能否推荐相关方法、公式或性质？",
        "anchor": "积分",
        "max_depth": 2,
        "min_results": 3,
        "expected_terms_any": ["换元", "分部", "牛顿", "莱布尼茨", "定积分"],
    },
    {
        "id": "recommend_indefinite_integral_methods",
        "kind": "method_recommendation",
        "question": "学生学习不定积分求解时，能否推荐基本积分公式、换元或分部积分等工具？",
        "anchor": "不定积分求解",
        "anchor_types": ["ProblemClass"],
        "max_depth": 2,
        "min_results": 2,
        "expected_terms_any": ["积分公式", "基本积分", "换元", "分部", "积分表"],
    },
    {
        "id": "recommend_separable_ode_methods",
        "kind": "method_recommendation",
        "question": "学生学习可分离变量微分方程时，能否推荐分离变量积分法和通积分式？",
        "anchor": "可分离变量的微分方程",
        "anchor_types": ["Concept"],
        "max_depth": 2,
        "min_results": 2,
        "expected_terms_any": ["分离变量", "通积分", "积分法", "通解"],
    },
    {
        "id": "path_derivative_to_limit",
        "kind": "path_between",
        "question": "能否从导数追溯到极限相关知识？",
        "source": "导数",
        "target": "极限",
        "source_types": ["Concept"],
        "target_types": ["Concept"],
        "max_depth": 5,
        "min_results": 1,
        "expected_terms_any": ["极限", "导数", "函数"],
    },
    {
        "id": "path_neighborhood_to_interval",
        "kind": "path_between",
        "question": "修补点验证：邻域是否能追溯到上位概念区间？",
        "source": "邻域",
        "target": "区间",
        "source_types": ["Concept"],
        "target_types": ["Concept"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 2,
        "min_results": 1,
        "expected_terms_all": ["邻域", "区间"],
    },
    {
        "id": "path_arcsin_to_inverse_trig",
        "kind": "path_between",
        "question": "修补点验证：反正弦函数是否归入反三角函数？",
        "source": "反正弦函数",
        "target": "反三角函数",
        "source_types": ["Concept"],
        "target_types": ["Concept"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 2,
        "min_results": 1,
        "expected_terms_all": ["反正弦函数", "反三角函数"],
    },
    {
        "id": "path_variable_limit_integral_hierarchy",
        "kind": "path_between",
        "question": "修补点验证：积分上限函数是否归入变限积分？",
        "source": "积分上限函数",
        "target": "变限积分",
        "source_types": ["Concept"],
        "target_types": ["Concept"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 2,
        "min_results": 1,
        "expected_terms_all": ["积分上限函数", "变限积分"],
    },
    {
        "id": "path_indefinite_integral_to_basic_table",
        "kind": "path_between",
        "question": "修补点验证：不定积分求解是否能连到基本积分表？",
        "source": "不定积分求解",
        "target": "基本积分表",
        "source_types": ["ProblemClass"],
        "target_types": ["Concept"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 2,
        "min_results": 1,
        "expected_terms_all": ["不定积分求解", "基本积分表"],
    },
    {
        "id": "path_improper_integral_to_definition_formula",
        "kind": "path_between",
        "question": "修补点验证：无穷积分计算是否能连到无穷积分定义公式？",
        "source": "无穷积分计算",
        "target": "无穷积分定义公式",
        "source_types": ["ProblemClass"],
        "target_types": ["Formula"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 2,
        "min_results": 1,
        "expected_terms_all": ["无穷积分计算", "无穷积分定义公式"],
    },
    {
        "id": "path_effective_current_to_formula",
        "kind": "path_between",
        "question": "修补点验证：电流有效值是否能连到电流有效值公式？",
        "source": "电流有效值",
        "target": "电流有效值公式",
        "source_types": ["Concept"],
        "target_types": ["Formula"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 2,
        "min_results": 1,
        "expected_terms_all": ["电流有效值", "电流有效值公式"],
    },
    {
        "id": "path_bernoulli_to_linear_ode",
        "kind": "path_between",
        "question": "第6章路径验证：伯努利方程是否能追溯到一阶线性微分方程？",
        "source": "伯努利方程",
        "target": "一阶线性微分方程",
        "source_types": ["Concept"],
        "target_types": ["Concept"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 3,
        "min_results": 1,
        "expected_terms_all": ["伯努利方程", "一阶线性微分方程"],
    },
    {
        "id": "path_euler_to_constant_coefficient_ode",
        "kind": "path_between",
        "question": "第6章路径验证：欧拉方程是否能连到常系数线性微分方程求解？",
        "source": "欧拉方程",
        "target": "n阶常系数齐线性微分方程的解法",
        "source_types": ["Concept"],
        "target_types": ["Method"],
        "source_exact": True,
        "target_exact": True,
        "max_depth": 4,
        "min_results": 1,
        "expected_terms_any": ["欧拉方程", "常系数", "变量代换"],
    },
    {
        "id": "rule_continuity",
        "kind": "rule_outcome",
        "question": "能否回答：什么时候函数连续？",
        "outcome_keywords": ["连续", "函数连续"],
        "min_results": 1,
        "expected_terms_any": ["极限", "函数", "连续"],
    },
    {
        "id": "rule_extremum",
        "kind": "rule_outcome",
        "question": "能否回答：什么时候取得极值？",
        "outcome_keywords": ["极值", "最大值", "最小值"],
        "min_results": 1,
        "expected_terms_any": ["导数", "极值", "单调"],
    },
    {
        "id": "rule_improper_integral_convergence",
        "kind": "rule_outcome",
        "question": "能否回答：反常积分什么时候收敛？",
        "outcome_keywords": ["收敛", "反常积分收敛"],
        "min_results": 1,
        "expected_terms_any": ["反常积分", "收敛", "比较"],
    },
    {
        "id": "rule_variable_limit_integral_derivative",
        "kind": "rule_outcome",
        "question": "能否回答：变上限积分什么时候可导？",
        "outcome_keywords": ["变上限积分", "可导", "导函数"],
        "min_results": 1,
        "expected_terms_all": ["可导"],
        "expected_terms_any": ["变上限积分", "积分上限"],
        "row_expected_terms_all": ["可导"],
        "row_expected_terms_any": ["变上限积分", "积分上限"],
    },
    {
        "id": "rule_effective_current",
        "kind": "rule_outcome",
        "question": "能否回答：电流有效值如何由平均功率条件得到？",
        "outcome_keywords": ["有效值", "电流有效值"],
        "min_results": 1,
        "expected_terms_all": ["电流", "有效值"],
        "expected_terms_any": ["平均功率", "功率"],
        "row_expected_terms_all": ["电流", "有效值"],
        "row_expected_terms_any": ["平均功率", "功率"],
    },
    {
        "id": "rule_separable_ode_judgment",
        "kind": "rule_outcome",
        "question": "能否回答：什么形式的一阶微分方程是可分离变量微分方程？",
        "outcome_keywords": ["可分离变量"],
        "min_results": 1,
        "expected_terms_all": ["可分离变量"],
        "expected_terms_any": ["y'=f(x)g(y)", "分离变量"],
        "row_expected_terms_all": ["可分离变量"],
        "row_expected_terms_any": ["y'=f(x)g(y)", "分离变量"],
    },
    {
        "id": "rule_bernoulli_linearization",
        "kind": "rule_outcome",
        "question": "能否回答：伯努利方程如何化为一阶线性微分方程？",
        "outcome_keywords": ["一阶线性微分方程", "伯努利方程"],
        "min_results": 1,
        "expected_terms_all": ["伯努利方程", "一阶线性微分方程"],
        "expected_terms_any": ["u = y", "y^{1-n}", "代换"],
        "row_expected_terms_all": ["伯努利方程", "一阶线性微分方程"],
        "row_expected_terms_any": ["u = y", "y^{1-n}", "代换"],
    },
    {
        "id": "rule_euler_ode_substitution",
        "kind": "rule_outcome",
        "question": "能否回答：欧拉方程在什么条件下用变量代换转成常系数线性微分方程？",
        "outcome_keywords": ["欧拉方程", "常系数线性微分方程"],
        "min_results": 1,
        "expected_terms_all": ["欧拉方程"],
        "expected_terms_any": ["x>0", "x = \\mathrm{e}^t", "t=\\ln x", "常系数线性微分方程"],
        "row_expected_terms_all": ["欧拉方程"],
        "row_expected_terms_any": ["x>0", "x = \\mathrm{e}^t", "t=\\ln x", "常系数线性微分方程"],
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
      AND (
        ($exact = true AND (
          n.name = $keyword
          OR any(alias IN coalesce(n.aliases, []) WHERE alias = $keyword)
        ))
        OR
        ($exact = false AND (
          n.name CONTAINS $keyword
          OR any(alias IN coalesce(n.aliases, []) WHERE alias CONTAINS $keyword)
        ))
      )
    RETURN n.name AS name,
           n.type AS type,
           n.chapter AS chapter,
           n.section AS section,
           left(coalesce(n.evidence_span, ""), 240) AS evidence
    ORDER BY CASE WHEN n.name = $keyword THEN 0 ELSE 1 END, n.type, n.name
    LIMIT $limit
    """
    return run_records(session, query, {
        "keyword": test.get("keyword", ""),
        "exact": bool(test.get("exact", False)),
        "node_types": test.get("node_types", []),
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
    depth = safe_depth(test.get("max_depth"), 2)
    query = f"""
    MATCH (a:KGNode)
    WHERE ($import_batch = "" OR a.import_batch = $import_batch)
      AND ($anchor_types = [] OR a.type IN $anchor_types)
      AND a.name CONTAINS $anchor
    MATCH p=(a)-[*1..{depth}]-(m:KGNode)
    WHERE ($import_batch = "" OR m.import_batch = $import_batch)
      AND m.type IN ["Method", "Formula", "Theorem"]
    RETURN DISTINCT a.name AS anchor,
           m.name AS recommended,
           m.type AS recommended_type,
           [rel IN relationships(p) | type(rel)] AS rels,
           [node IN nodes(p) | coalesce(node.name, "")] AS path_nodes,
           left(coalesce(m.evidence_span, ""), 240) AS evidence,
           size([rel IN relationships(p) WHERE type(rel) IN ["USES", "HAS_PROPERTY", "GETS", "DERIVES", "SUPERIOR", "PART_OF", "EQUATIVE"]]) AS semantic_edge_count,
           size([rel IN relationships(p) WHERE type(rel) IN ["HAS_MEMBER", "HAS_ANCHOR"]]) AS group_edge_count,
           length(p) AS path_length,
           CASE
             WHEN m.name CONTAINS "换元"
               OR m.name CONTAINS "分部"
               OR m.name CONTAINS "牛顿"
               OR m.name CONTAINS "莱布尼茨"
               OR m.name CONTAINS "洛必达"
               OR m.name CONTAINS "泰勒"
             THEN 0 ELSE 1
           END AS expected_term_rank
    ORDER BY expected_term_rank, semantic_edge_count DESC, group_edge_count ASC, path_length, m.type, m.name
    LIMIT $limit
    """
    return run_records(session, query, {
        "anchor": test.get("anchor", ""),
        "anchor_types": test.get("anchor_types", []),
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
        with driver.session(database=args.database or None) as session:
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

