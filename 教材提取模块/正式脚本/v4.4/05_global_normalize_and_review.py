"""
v4.3 Step 5: global normalization and review package.

This step does not write to Neo4j. It gathers explicit core nodes/edges and
ExampleFrame-derived application candidates into stable review artifacts.
Only auto-accepted items are written to the main graph candidate files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "中间产物"
DEFAULT_NODES = DEFAULT_OUTPUT_DIR / "nodes.jsonl"
DEFAULT_EDGES = DEFAULT_OUTPUT_DIR / "edges.jsonl"
DEFAULT_NODE_REVIEW = DEFAULT_OUTPUT_DIR / "node_review_queue.jsonl"
DEFAULT_EDGE_REVIEW = DEFAULT_OUTPUT_DIR / "edge_review_queue.jsonl"
DEFAULT_APP_NODES = DEFAULT_OUTPUT_DIR / "normalized_example_application_nodes.jsonl"
DEFAULT_APP_EDGES = DEFAULT_OUTPUT_DIR / "normalized_example_application_edges.jsonl"

DEFAULT_MAIN_NODES_OUT = DEFAULT_OUTPUT_DIR / "kg_main_nodes.jsonl"
DEFAULT_MAIN_EDGES_OUT = DEFAULT_OUTPUT_DIR / "kg_main_edges.jsonl"
DEFAULT_RULE_CASES_OUT = DEFAULT_OUTPUT_DIR / "kg_rule_cases.jsonl"
DEFAULT_REVIEW_NODES_OUT = DEFAULT_OUTPUT_DIR / "step5_review_nodes.jsonl"
DEFAULT_REVIEW_EDGES_OUT = DEFAULT_OUTPUT_DIR / "step5_review_edges.jsonl"
DEFAULT_REVIEW_RULE_CASES_OUT = DEFAULT_OUTPUT_DIR / "step5_review_rule_cases.jsonl"
DEFAULT_REJECTED_OUT = DEFAULT_OUTPUT_DIR / "step5_rejected_items.jsonl"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "step5_global_normalization_report.md"
DEFAULT_REVIEW_MD = DEFAULT_OUTPUT_DIR / "step5_review_checklist.md"

MAIN_NODE_TYPES = {"Concept", "Method", "Formula", "Theorem", "ProblemClass"}
MAIN_EDGE_TYPES = {"SUPERIOR", "EQUATIVE", "PART_OF", "HAS_PROPERTY", "USES", "GETS", "DERIVES"}


def add_review_warning(row: dict[str, Any], warning: str, reason: str) -> None:
    warnings = list(row.get("validation_warnings") or [])
    if warning not in warnings:
        warnings.append(warning)
    row["validation_warnings"] = warnings
    existing_reason = str(row.get("review_reason") or "").strip()
    row["review_reason"] = f"{existing_reason}；{reason}" if existing_reason else reason


def needs_step5_edge_review(edge: dict[str, Any]) -> bool:
    """Catch schema-valid edges that should not be auto-promoted to the main graph."""
    needs_review = False
    edge_type = str(edge.get("type") or "")
    source_type = str(edge.get("source_type") or "")
    target_type = str(edge.get("target_type") or "")
    evidence = str(edge.get("evidence_span") or "")
    description = str(edge.get("description") or "")

    if edge_type == "SUPERIOR":
        if source_type and target_type and source_type != target_type:
            add_review_warning(
                edge,
                "superior_requires_same_node_type",
                "SUPERIOR 只表示同类知识点之间的上位/下位关系；当前边更像性质/定理隶属于主题概念，需人工确认改类型或删除。",
            )
            needs_review = True
        if "性质" in description and source_type == "Theorem" and target_type == "Concept":
            add_review_warning(
                edge,
                "superior_property_statement_requires_review",
                "行列式性质不应直接作为 n 阶行列式的下位概念自动入主图。",
            )
            needs_review = True

    if edge_type == "USES" and source_type == "Concept" and target_type == "Concept":
        looks_like_parallel_concepts = "需要" in evidence and "概念" in evidence and any(mark in evidence for mark in ["和", "与", "及"])
        if looks_like_parallel_concepts:
            add_review_warning(
                edge,
                "uses_parallel_concepts_requires_review",
                "原文只是并列提出多个概念需求，不足以说明 source 使用 target，需人工确认是否删除。",
            )
            needs_review = True

    return needs_review


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build v4.3 Step 5 normalized review package.")
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES)
    parser.add_argument("--node-review", type=Path, default=DEFAULT_NODE_REVIEW)
    parser.add_argument("--edge-review", type=Path, default=DEFAULT_EDGE_REVIEW)
    parser.add_argument("--app-nodes", type=Path, default=DEFAULT_APP_NODES)
    parser.add_argument("--app-edges", type=Path, default=DEFAULT_APP_EDGES)
    parser.add_argument("--main-nodes-out", type=Path, default=DEFAULT_MAIN_NODES_OUT)
    parser.add_argument("--main-edges-out", type=Path, default=DEFAULT_MAIN_EDGES_OUT)
    parser.add_argument("--rule-cases-out", type=Path, default=DEFAULT_RULE_CASES_OUT)
    parser.add_argument("--review-nodes-out", type=Path, default=DEFAULT_REVIEW_NODES_OUT)
    parser.add_argument("--review-edges-out", type=Path, default=DEFAULT_REVIEW_EDGES_OUT)
    parser.add_argument("--review-rule-cases-out", type=Path, default=DEFAULT_REVIEW_RULE_CASES_OUT)
    parser.add_argument("--rejected-out", type=Path, default=DEFAULT_REJECTED_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--review-md", type=Path, default=DEFAULT_REVIEW_MD)
    parser.add_argument("--include-reviewed-app", action="store_true", help="Put normalized example application candidates into main graph candidates.")
    return parser.parse_args()


def read_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSONL not found: {path}")
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}:{digest}"


def item_key(row: dict[str, Any], fields: list[str]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in fields)


def normalize_node(row: dict[str, Any], layer: str) -> dict[str, Any]:
    node = dict(row)
    node["kg_layer"] = layer
    node["step5_status"] = "pending"
    node["step5_generated_at"] = datetime.now().isoformat(timespec="seconds")
    return node


def normalize_edge(row: dict[str, Any], layer: str) -> dict[str, Any]:
    edge = dict(row)
    edge["kg_layer"] = layer
    edge["step5_status"] = "pending"
    edge["step5_generated_at"] = datetime.now().isoformat(timespec="seconds")
    return edge


def stable_rule_case_id(owner: dict[str, Any], case: dict[str, Any], index: int) -> str:
    return stable_id(
        f"{owner.get('textbook_id', '')}:rulecase",
        [
            str(owner.get("node_id") or ""),
            str(case.get("case_name") or ""),
            str(case.get("evidence_span") or ""),
            str(index),
        ],
    )


def extract_rule_cases(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    main: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for node in nodes:
        for index, case in enumerate(node.get("rule_cases") or [], start=1):
            if not isinstance(case, dict):
                continue
            row = dict(case)
            row.update(
                {
                    "rule_case_id": stable_rule_case_id(node, case, index),
                    "item_kind": "rule_case",
                    "owner_node_id": node.get("node_id", ""),
                    "owner_name": node.get("name", ""),
                    "owner_type": node.get("type", ""),
                    "textbook_id": node.get("textbook_id", ""),
                    "textbook_name": node.get("textbook_name", ""),
                    "chapter": node.get("chapter", ""),
                    "section": node.get("section", ""),
                    "subsection": node.get("subsection", ""),
                    "section_node_id": node.get("section_node_id", ""),
                    "source_scope": node.get("source_scope", ""),
                    "kg_layer": "rule_case",
                    "step5_status": "review",
                    "review_status": "review",
                    "review_reason": "条件判断规则案例默认需审核条件、结论和适用对象。",
                    "step5_generated_at": datetime.now().isoformat(timespec="seconds"),
                }
            )
            review.append(row)
    return main, review


def is_valid_node(node: dict[str, Any]) -> bool:
    return str(node.get("type") or "") in MAIN_NODE_TYPES and bool(node.get("node_id")) and bool(node.get("name"))


def is_valid_edge(edge: dict[str, Any], node_ids: set[str]) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    if str(edge.get("type") or "") not in MAIN_EDGE_TYPES:
        warnings.append(f"invalid_edge_type:{edge.get('type')}")
    if not edge.get("source_node_id") or not edge.get("target_node_id"):
        warnings.append("missing_endpoint_id")
    if edge.get("source_node_id") == edge.get("target_node_id"):
        if str(edge.get("kg_layer") or edge.get("layer") or "") == "example_application":
            add_review_warning(
                edge,
                "application_self_loop_requires_review",
                "应用层自环可能由方法名/工具名归一化造成，应进入 Step 7 判断是否改写为核心公式/性质边。",
            )
        else:
            warnings.append("self_loop")
    if edge.get("source_node_id") not in node_ids:
        warnings.append(f"source_not_in_step5_nodes:{edge.get('source_node_id')}")
    target_layer = str(edge.get("target_layer") or edge.get("kg_layer") or "")
    if edge.get("target_node_id") not in node_ids and target_layer != "core":
        warnings.append(f"target_not_in_step5_nodes:{edge.get('target_node_id')}")
    return not warnings, warnings


def dedupe_nodes(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for node in nodes:
        node_id = str(node.get("node_id") or "")
        if node_id in kept:
            duplicate = dict(node)
            duplicate["step5_reject_reason"] = "duplicate_node_id"
            duplicates.append(duplicate)
            continue
        kept[node_id] = node
    return list(kept.values()), duplicates


def dedupe_edges(edges: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    duplicates: list[dict[str, Any]] = []
    for edge in edges:
        key = item_key(edge, ["source_node_id", "target_node_id", "type", "kg_layer"])
        if key in kept:
            existing = kept[key]
            merged = existing.setdefault("step5_merged_evidence_spans", [])
            for evidence in [existing.get("evidence_span", ""), edge.get("evidence_span", "")]:
                if evidence and evidence not in merged:
                    merged.append(evidence)
            duplicate = dict(edge)
            duplicate["step5_reject_reason"] = "duplicate_edge_key"
            duplicates.append(duplicate)
            continue
        kept[key] = edge
    return list(kept.values()), duplicates


def split_nodes(
    explicit_nodes: list[dict[str, Any]],
    app_nodes: list[dict[str, Any]],
    include_reviewed_app: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    main: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for raw_node in explicit_nodes:
        node = normalize_node(raw_node, "core")
        if node.get("source_scope") == "example":
            node["step5_status"] = "reject"
            node["step5_reject_reason"] = "legacy_example_node_replaced_by_exampleframe"
            rejected.append(node)
            continue
        if not is_valid_node(node):
            node["step5_status"] = "reject"
            node["step5_reject_reason"] = "invalid_node_schema"
            rejected.append(node)
            continue
        if node.get("review_status") == "auto_accept":
            node["step5_status"] = "main"
            main.append(node)
        else:
            node["step5_status"] = "review"
            review.append(node)

    for raw_node in app_nodes:
        node = normalize_node(raw_node, "example_application")
        if not is_valid_node(node):
            node["step5_status"] = "reject"
            node["step5_reject_reason"] = "invalid_app_node_schema"
            rejected.append(node)
            continue
        if include_reviewed_app and node.get("review_status") == "auto_accept":
            node["step5_status"] = "main"
            main.append(node)
        else:
            node["step5_status"] = "review"
            node["review_reason"] = node.get("review_reason") or "例题应用层节点默认需人工确认后入主图。"
            review.append(node)

    main, dup_main = dedupe_nodes(main)
    review, dup_review = dedupe_nodes(review)
    rejected.extend(dup_main)
    rejected.extend(dup_review)
    return main, review, rejected


def split_edges(
    explicit_edges: list[dict[str, Any]],
    app_edges: list[dict[str, Any]],
    main_nodes: list[dict[str, Any]],
    review_nodes: list[dict[str, Any]],
    include_reviewed_app: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    main: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    all_node_ids = {str(node.get("node_id") or "") for node in [*main_nodes, *review_nodes]}

    for raw_edge in explicit_edges:
        edge = normalize_edge(raw_edge, "core")
        ok, warnings = is_valid_edge(edge, all_node_ids)
        if not ok:
            edge["step5_status"] = "reject"
            edge["step5_reject_reason"] = ";".join(warnings)
            rejected.append(edge)
            continue
        if edge.get("review_status") == "auto_accept" and not needs_step5_edge_review(edge):
            edge["step5_status"] = "main"
            main.append(edge)
        else:
            edge["step5_status"] = "review"
            review.append(edge)

    for raw_edge in app_edges:
        edge = normalize_edge(raw_edge, "example_application")
        ok, warnings = is_valid_edge(edge, all_node_ids)
        if not ok:
            edge["step5_status"] = "reject"
            edge["step5_reject_reason"] = ";".join(warnings)
            rejected.append(edge)
            continue
        if include_reviewed_app and edge.get("review_status") == "auto_accept":
            edge["step5_status"] = "main"
            main.append(edge)
        else:
            edge["step5_status"] = "review"
            edge["review_reason"] = edge.get("review_reason") or "例题应用层边默认需人工确认后入主图。"
            review.append(edge)

    main, dup_main = dedupe_edges(main)
    review, dup_review = dedupe_edges(review)
    rejected.extend(dup_main)
    rejected.extend(dup_review)
    return main, review, rejected


def type_counts(rows: list[dict[str, Any]], field: str) -> Counter[str]:
    return Counter(str(row.get(field) or "") for row in rows)


def write_report(
    path: Path,
    main_nodes: list[dict[str, Any]],
    review_nodes: list[dict[str, Any]],
    main_edges: list[dict[str, Any]],
    review_edges: list[dict[str, Any]],
    rule_cases: list[dict[str, Any]],
    review_rule_cases: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> None:
    lines = [
        "# v4.3 Step 5 Global Normalization Report",
        "",
        "## Output Counts",
        f"- main nodes: {len(main_nodes)}",
        f"- review nodes: {len(review_nodes)}",
        f"- main edges: {len(main_edges)}",
        f"- rule cases: {len(rule_cases)}",
        f"- review edges: {len(review_edges)}",
        f"- review rule cases: {len(review_rule_cases)}",
        f"- rejected items: {len(rejected)}",
        "",
        "## Main Node Types",
    ]
    for key, value in sorted(type_counts(main_nodes, "type").items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Review Node Types"])
    for key, value in sorted(type_counts(review_nodes, "type").items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Main Edge Types"])
    for key, value in sorted(type_counts(main_edges, "type").items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Review Edge Types"])
    for key, value in sorted(type_counts(review_edges, "type").items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Review Rule Case Owners"])
    for key, value in sorted(type_counts(review_rule_cases, "owner_type").items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Rejected Reasons"])
    reason_counts = type_counts(rejected, "step5_reject_reason")
    if reason_counts:
        for key, value in sorted(reason_counts.items(), key=lambda item: (-item[1], item[0])):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def short(text: Any, limit: int = 120) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def write_review_md(
    path: Path,
    review_nodes: list[dict[str, Any]],
    review_edges: list[dict[str, Any]],
    review_rule_cases: list[dict[str, Any]],
) -> None:
    lines = [
        "# v4.3 Step 5 Review Checklist",
        "",
        "本文件只列出需要人工拍板的节点和边。默认建议：正文核心 `review` 项逐条看；例题应用层节点/边先抽样看，再决定是否批量接受。",
        "",
        "## 一、待审节点",
        "",
        "| 序号 | 层 | 类型 | 名称 | 来源 | 建议关注点 | evidence |",
        "|---:|---|---|---|---|---|---|",
    ]
    for index, node in enumerate(review_nodes, start=1):
        reason = node.get("review_reason") or node.get("validation_warnings") or "需确认是否入主图"
        lines.append(
            f"| {index} | {node.get('kg_layer','')} | {node.get('type','')} | {node.get('name','')} | "
            f"{node.get('source_label','') or node.get('section_node_id','')} | {short(reason, 80)} | {short(node.get('evidence_span',''), 120)} |"
        )
    lines.extend([
        "",
        "## 二、待审边",
        "",
        "| 序号 | 层 | 关系 | source | target | 来源 | 建议关注点 | evidence |",
        "|---:|---|---|---|---|---|---|---|",
    ])
    for index, edge in enumerate(review_edges, start=1):
        warnings = ", ".join(edge.get("validation_warnings", []) or [])
        reason = edge.get("review_reason") or warnings or "需确认是否入主图"
        lines.append(
            f"| {index} | {edge.get('kg_layer','')} | {edge.get('type','')} | "
            f"{edge.get('source_name','')} | {edge.get('target_name','')} | {edge.get('section_node_id','')} | "
            f"{short(reason, 90)} | {short(edge.get('evidence_span',''), 120)} |"
        )
    lines.extend([
        "",
        "## 三、待审条件判断规则案例",
        "",
        "| 序号 | 所属节点 | case | 适用对象 | 条件 | 结论 | evidence |",
        "|---:|---|---|---|---|---|---|",
    ])
    for index, case in enumerate(review_rule_cases, start=1):
        lines.append(
            f"| {index} | {case.get('owner_name','')} | {case.get('case_name','')} | "
            f"{short(case.get('applies_to',''), 60)} | {short('; '.join(case.get('conditions', []) or []), 90)} | "
            f"{short('; '.join(case.get('outcomes', []) or []), 90)} | {short(case.get('evidence_span',''), 120)} |"
        )
    lines.extend([
        "",
        "## 四、建议审批方式",
        "",
        "1. 先确认正文核心 DERIVES 是否方向正确。",
        "2. 再确认 rule_cases 的条件、结论、适用对象是否准确。",
        "3. 再确认例题应用层 Method / ProblemClass 是否整体接受。",
        "4. 最后决定是否把应用层节点和边批量并入主图，或继续保留在应用层。"
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    explicit_nodes = read_jsonl(args.nodes)
    explicit_edges = read_jsonl(args.edges)
    app_nodes = read_jsonl(args.app_nodes, required=False)
    app_edges = read_jsonl(args.app_edges, required=False)

    main_nodes, review_nodes, rejected_nodes = split_nodes(explicit_nodes, app_nodes, args.include_reviewed_app)
    main_edges, review_edges, rejected_edges = split_edges(
        explicit_edges,
        app_edges,
        main_nodes,
        review_nodes,
        args.include_reviewed_app,
    )
    rule_cases, review_rule_cases = extract_rule_cases([*main_nodes, *review_nodes])
    rejected = [*rejected_nodes, *rejected_edges]

    write_jsonl(args.main_nodes_out, main_nodes)
    write_jsonl(args.main_edges_out, main_edges)
    write_jsonl(args.rule_cases_out, rule_cases)
    write_jsonl(args.review_nodes_out, review_nodes)
    write_jsonl(args.review_edges_out, review_edges)
    write_jsonl(args.review_rule_cases_out, review_rule_cases)
    write_jsonl(args.rejected_out, rejected)
    write_report(args.report, main_nodes, review_nodes, main_edges, review_edges, rule_cases, review_rule_cases, rejected)
    write_review_md(args.review_md, review_nodes, review_edges, review_rule_cases)

    print(f"[OK] main nodes -> {args.main_nodes_out}")
    print(f"[OK] main edges -> {args.main_edges_out}")
    print(f"[OK] rule cases -> {args.rule_cases_out}")
    print(f"[OK] review nodes -> {args.review_nodes_out}")
    print(f"[OK] review edges -> {args.review_edges_out}")
    print(f"[OK] review rule cases -> {args.review_rule_cases_out}")
    print(f"[OK] rejected -> {args.rejected_out}")
    print(f"[OK] report -> {args.report}")
    print(f"[OK] review checklist -> {args.review_md}")


if __name__ == "__main__":
    main()
