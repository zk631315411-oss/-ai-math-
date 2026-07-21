"""
v4.4 Step 7F: apply guarded repairs for Step 7C invalid rewrites.

This script is intentionally narrow. It only handles review items whose Step 7B
rewrite suggestions were semantically useful but failed Step 7C because the
rewritten edge endpoint was not an existing graph node. Repairs are explicit,
audited, and written back into the Step 7 final package before Step 8A assembly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = SCRIPT_DIR / "中间产物" / "c01_c05_cumulative"
DEFAULT_STEP7_FINAL = DEFAULT_RUN_DIR / "step7_final"
DEFAULT_STEP7_REVIEW = DEFAULT_RUN_DIR / "step7_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply explicit v4.4 Step 7C conflict repairs.")
    parser.add_argument("--step7-final-dir", type=Path, default=DEFAULT_STEP7_FINAL)
    parser.add_argument("--step7-review-dir", type=Path, default=DEFAULT_STEP7_REVIEW)
    parser.add_argument("--out-report", type=Path, default=DEFAULT_STEP7_FINAL / "step7f_conflict_repair_report.md")
    return parser.parse_args()


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}:{digest}"


def read_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSONL not found: {path}")
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def source_code(row: dict[str, Any]) -> str:
    if row.get("source_code"):
        return str(row.get("source_code"))
    section_node_id = str(row.get("section_node_id") or "").strip()
    textbook_id = str(row.get("textbook_id") or "").strip()
    base = section_node_id or textbook_id or "unknown-source"
    line_start = row.get("line_start")
    line_end = row.get("line_end")
    if line_start not in (None, "", 0) or line_end not in (None, "", 0):
        return f"{base}:L{line_start or ''}-L{line_end or ''}"
    return base


def node_identity(node: dict[str, Any]) -> str:
    node_id = str(node.get("node_id") or "")
    if node_id:
        return node_id
    return stable_id("node-key", [str(node.get("name") or ""), str(node.get("type") or "")])


def edge_identity(edge: dict[str, Any]) -> str:
    return stable_id(
        "edge-key",
        [
            str(edge.get("source_node_id") or edge.get("source_name") or ""),
            str(edge.get("target_node_id") or edge.get("target_name") or ""),
            str(edge.get("type") or ""),
            str(edge.get("kg_layer") or ""),
        ],
    )


def add_alias(node: dict[str, Any], alias: str) -> None:
    alias = alias.strip()
    if not alias or alias == node.get("name"):
        return
    aliases = [str(item) for item in node.get("aliases") or []]
    if alias not in aliases:
        aliases.append(alias)
    node["aliases"] = aliases


def ensure_source_code(row: dict[str, Any]) -> None:
    row.setdefault("source_code", source_code(row))


def find_node(nodes_by_name: dict[str, dict[str, Any]], name: str) -> dict[str, Any]:
    node = nodes_by_name.get(name)
    if not node:
        raise RuntimeError(f"Repair node not found: {name}")
    return node


def index_nodes(nodes: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_name: dict[str, dict[str, Any]] = {}
    by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        name = str(node.get("name") or "")
        node_id = str(node.get("node_id") or "")
        if name:
            by_name[name] = node
        if node_id:
            by_id[node_id] = node
        for alias in node.get("aliases") or []:
            alias = str(alias).strip()
            if alias and alias not in by_name:
                by_name[alias] = node
    return by_name, by_id


def make_node(template: dict[str, Any], name: str, node_type: str, evidence: str, description: str, aliases: list[str] | None = None) -> dict[str, Any]:
    textbook_id = str(template.get("textbook_id") or "gaoshu_shang")
    node = {
        "candidate_id": stable_id(f"{textbook_id}:repair-node-cand", [name, node_type, str(template.get("section_node_id") or "")]),
        "node_id": stable_id(f"{textbook_id}:node", [name, node_type]),
        "name": name,
        "type": node_type,
        "aliases": aliases or [],
        "source_label": "",
        "definition": evidence,
        "description": description,
        "attributes": [],
        "state_notes": ["Step 7F 依据审核意见补入的正式知识点。"],
        "rule_cases": [],
        "evidence_span": evidence,
        "confidence": 0.9,
        "reason": "Step 7C 冲突修补：审核意见需要该正式端点，且教材原文支持该知识点。",
        "review_recommended": False,
        "review_reason": "",
        "textbook_id": textbook_id,
        "textbook_name": template.get("textbook_name", ""),
        "chapter": template.get("chapter", ""),
        "section": template.get("section", ""),
        "subsection": template.get("subsection", ""),
        "section_node_id": template.get("section_node_id", ""),
        "source_scope": template.get("source_scope", "core_content"),
        "line_start": template.get("line_start", ""),
        "line_end": template.get("line_end", ""),
        "layer": "explicit",
        "review_status": "auto_accept",
        "kg_layer": "core",
        "step5_status": "step7f_repair",
        "step6_layer": "explicit_core",
        "step6_status": "candidate",
        "step7_status": "accepted_by_step7f_repair",
        "step7_action": "repair_accept",
        "step7_basis": "审核 AI 建议使用该端点；经人工判断该端点是正式知识点，可补入主图。",
        "final_import_ready": True,
        "step7_generated_at": now_iso(),
        "step7f_repair": True,
    }
    ensure_source_code(node)
    return node


def make_edge(source: dict[str, Any], target: dict[str, Any], edge_type: str, evidence: str, description: str, template: dict[str, Any], review_item_id: str, basis: str) -> dict[str, Any]:
    textbook_id = str(template.get("textbook_id") or source.get("textbook_id") or target.get("textbook_id") or "gaoshu_shang")
    edge = {
        "candidate_id": stable_id(f"{textbook_id}:repair-edge-cand", [review_item_id, source.get("node_id", ""), target.get("node_id", ""), edge_type]),
        "edge_id": stable_id(f"{textbook_id}:edge", [str(source.get("node_id") or source.get("name") or ""), str(target.get("node_id") or target.get("name") or ""), edge_type, "core"]),
        "source_node_id": source.get("node_id", ""),
        "source_name": source.get("name", ""),
        "target_node_id": target.get("node_id", ""),
        "target_name": target.get("name", ""),
        "type": edge_type,
        "evidence_spans": [{"role": "primary", "text": evidence}],
        "evidence_span": evidence,
        "description": description,
        "confidence": 0.88,
        "review_recommended": False,
        "review_reason": "",
        "textbook_id": textbook_id,
        "textbook_name": template.get("textbook_name", source.get("textbook_name", "")),
        "chapter": template.get("chapter", source.get("chapter", "")),
        "section": template.get("section", source.get("section", "")),
        "subsection": template.get("subsection", source.get("subsection", "")),
        "section_node_id": template.get("section_node_id", source.get("section_node_id", "")),
        "source_scope": template.get("source_scope", "core_content"),
        "line_start": template.get("line_start", source.get("line_start", "")),
        "line_end": template.get("line_end", source.get("line_end", "")),
        "layer": "explicit",
        "review_status": "auto_accept",
        "source_type": source.get("type", ""),
        "target_type": target.get("type", ""),
        "source_review_status": source.get("review_status", ""),
        "target_review_status": target.get("review_status", ""),
        "kg_layer": "core",
        "step5_status": "step7f_repair",
        "step6_layer": "explicit_core",
        "step6_status": "candidate",
        "step7_status": "accepted_by_step7f_repair",
        "step7_review_item_id": review_item_id,
        "step7_action": "repair_accept",
        "step7_basis": basis,
        "final_import_ready": True,
        "step7_generated_at": now_iso(),
        "step7f_repair": True,
    }
    ensure_source_code(edge)
    return edge


def archive_deferred_item(item: dict[str, Any], status: str, basis: str) -> dict[str, Any]:
    archived = dict(item)
    archived["archive_status"] = status
    archived["step7f_basis"] = basis
    archived["final_import_ready"] = False
    archived["step7f_repaired_at"] = now_iso()
    return archived


def archive_identity(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("step7_review_item_id") or row.get("review_item_id") or ""),
            str(row.get("archive_status") or ""),
            str(row.get("edge_id") or row.get("node_id") or row.get("rule_case_id") or row.get("candidate_id") or ""),
        ]
    )


def trace(review_item_id: str, result: str, note: str, item_id: str = "") -> dict[str, Any]:
    return {
        "review_item_id": review_item_id,
        "item_kind": "edge",
        "item_id": item_id,
        "action": "step7f_repair",
        "target_layer": "core" if result == "accepted" else "review_pending",
        "result": result,
        "note": note,
        "generated_at": now_iso(),
    }


def trace_identity(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("review_item_id") or ""),
            str(row.get("action") or ""),
            str(row.get("result") or ""),
            str(row.get("item_id") or ""),
        ]
    )


def add_unique_by(rows: list[dict[str, Any]], row: dict[str, Any], seen: set[str], key_func) -> None:
    key = key_func(row)
    if key in seen:
        return
    rows.append(row)
    seen.add(key)


def update_endpoint_names(rows: list[dict[str, Any]], node: dict[str, Any]) -> None:
    node_id = str(node.get("node_id") or "")
    name = str(node.get("name") or "")
    node_type = str(node.get("type") or "")
    for row in rows:
        if node_id and str(row.get("source_node_id") or "") == node_id:
            row["source_name"] = name
            row["source_type"] = node_type
        if node_id and str(row.get("target_node_id") or "") == node_id:
            row["target_name"] = name
            row["target_type"] = node_type
        if node_id and str(row.get("owner_node_id") or "") == node_id:
            row["owner_name"] = name
            row["owner_type"] = node_type


def main() -> None:
    args = parse_args()
    step7_final = args.step7_final_dir
    step7_review = args.step7_review_dir

    approved_nodes = read_jsonl(step7_final / "approved_nodes.jsonl")
    approved_edges = read_jsonl(step7_final / "approved_edges.jsonl")
    approved_rule_cases = read_jsonl(step7_final / "approved_rule_cases.jsonl", required=False)
    review_archive = read_jsonl(step7_final / "review_archive.jsonl", required=False)
    deferred_items = read_jsonl(step7_final / "deferred_items.jsonl", required=False)
    decision_trace = read_jsonl(step7_final / "decision_trace.jsonl", required=False)
    archive_seen = {archive_identity(row) for row in review_archive}
    trace_seen = {trace_identity(row) for row in decision_trace}
    ai_decisions = {str(row.get("review_item_id") or ""): row for row in read_jsonl(step7_review / "ai_review_decisions.jsonl", required=False)}

    deferred_by_id = {str(row.get("step7_review_item_id") or row.get("review_item_id") or ""): row for row in deferred_items}
    nodes_by_name, nodes_by_id = index_nodes(approved_nodes)
    edge_keys = {edge_identity(edge) for edge in approved_edges}
    node_ids = {node_identity(node) for node in approved_nodes}
    accepted_repairs: list[str] = []
    kept_deferred: list[str] = []

    def add_node_if_missing(node: dict[str, Any]) -> dict[str, Any]:
        existing = nodes_by_name.get(str(node.get("name") or ""))
        if existing:
            return existing
        key = node_identity(node)
        if key not in node_ids:
            approved_nodes.append(node)
            node_ids.add(key)
        nodes_by_name[str(node.get("name") or "")] = node
        nodes_by_id[str(node.get("node_id") or "")] = node
        return node

    def add_edge(edge: dict[str, Any]) -> None:
        key = edge_identity(edge)
        if key not in edge_keys:
            approved_edges.append(edge)
            edge_keys.add(key)

    def accept_repair(review_item_id: str, edge_specs: list[dict[str, str]], basis: str) -> None:
        source_item = deferred_by_id.get(review_item_id, {})
        decision = ai_decisions.get(review_item_id, {})
        template = source_item or decision.get("source_item") or {}
        if source_item:
            add_unique_by(review_archive, archive_deferred_item(source_item, "repaired_by_step7f_original_archived", basis), archive_seen, archive_identity)
        for spec in edge_specs:
            source = find_node(nodes_by_name, spec["source"])
            target = find_node(nodes_by_name, spec["target"])
            edge = make_edge(
                source,
                target,
                spec["type"],
                spec.get("evidence") or str((decision.get("rewritten_item") or {}).get("evidence_span") or template.get("evidence_span") or ""),
                spec.get("description", ""),
                template,
                review_item_id,
                basis,
            )
            add_edge(edge)
            add_unique_by(decision_trace, trace(review_item_id, "accepted", spec.get("description", ""), edge.get("edge_id", "")), trace_seen, trace_identity)
        accepted_repairs.append(review_item_id)

    # Rename an overly narrow node instead of adding a duplicate "反正弦函数" node.
    arcsin_node = nodes_by_name.get("反正弦函数主值")
    if arcsin_node:
        add_alias(arcsin_node, "反正弦函数主值")
        arcsin_node["name"] = "反正弦函数"
        arcsin_node["description"] = "正弦函数在主值区间上的反函数，通常记作 y=arcsin x。"
        arcsin_node["step7f_repair"] = True
        arcsin_node["step7_basis"] = "审核意见指出原名“反正弦函数主值”过窄；教材随后说明通常称 y=arcsin x 为反正弦函数。"
        nodes_by_name.pop("反正弦函数主值", None)
        nodes_by_name["反正弦函数"] = arcsin_node
        update_endpoint_names([*approved_edges, *approved_rule_cases], arcsin_node)

    # Add aliases to existing aggregate/alias nodes rather than adding duplicate endpoint nodes.
    if "基本积分表" in nodes_by_name:
        add_alias(nodes_by_name["基本积分表"], "基本积分公式")
    if "积分上限函数" in nodes_by_name:
        add_alias(nodes_by_name["积分上限函数"], "变上限积分")
    if "积分下限函数" in nodes_by_name:
        add_alias(nodes_by_name["积分下限函数"], "变下限积分")

    # Add the general interval node required by the validated audit suggestion.
    interval_template = deferred_by_id.get("review-item:c577c322c92b7b") or {}
    interval_node = make_node(
        interval_template,
        "区间",
        "Concept",
        "变量取值范围常用区间来表示。",
        "表示变量取值范围的一类数集，包含闭区间、开区间、半开半闭区间、无限区间以及邻域等具体形式。",
    )
    add_node_if_missing(interval_node)

    interval_evidence = "变量取值范围常用区间来表示。满足不等式 a≤x≤b 的实数全体叫作闭区间；满足不等式 a<x<b 的实数全体叫作开区间。邻域也是常用的一类区间。"
    interval_basis = "审核意见指出“邻域 -> 开区间”过窄，教材直接支持“邻域 -> 区间”；经判断“区间”是缺失的正式上位概念。"
    accept_repair(
        "review-item:c577c322c92b7b",
        [{"source": "邻域", "target": "区间", "type": "SUPERIOR", "evidence": interval_evidence, "description": "邻域是常用的一类区间。"}],
        interval_basis,
    )
    for subtype in ["闭区间", "开区间", "半开半闭区间", "有限区间", "无限区间"]:
        if subtype in nodes_by_name:
            add_edge(
                make_edge(
                    nodes_by_name[subtype],
                    nodes_by_name["区间"],
                    "SUPERIOR",
                    interval_evidence,
                    f"{subtype} 是区间的一种具体形式。",
                    interval_template,
                    "step7f:interval-hierarchy",
                    "补入缺失的区间层级，以支持审核意见中的上位概念。",
                )
            )

    accept_repair(
        "review-item:707cef0a31761e",
        [{"source": "反正弦函数", "target": "反三角函数", "type": "SUPERIOR", "description": "反正弦函数是常用反三角函数之一。"}],
        "审核意见认为源端应为“反正弦函数”；已将原节点语义名修正并保留旧名为别名。",
    )

    kept_deferred.append("review-item:499af45881670b")
    add_unique_by(
        decision_trace,
        trace("review-item:499af45881670b", "deferred", "需要新增过程性方法节点，端点命名仍需人工确认，暂不落主图。"),
        trace_seen,
        trace_identity,
    )

    accept_repair(
        "review-item:690d9caa6503bd",
        [{"source": "无穷小量", "target": "无穷小的和差性质", "type": "HAS_PROPERTY", "description": "无穷小量具有和差仍为无穷小的性质。"}],
        "审核意见中的“无穷小的定义”不是独立节点；按图谱规则改为对象到性质的 HAS_PROPERTY。",
    )

    accept_repair(
        "review-item:6c3a2d2a650f3c",
        [{"source": "夹逼定理", "target": "第二个重要极限", "type": "DERIVES", "description": "教材由夹逼定理推出第二个重要极限的相应形式。"}],
        "目标公式已作为“第二个重要极限”的别名/内容存在，保留正式节点名，不新增公式端点。",
    )

    accept_repair(
        "review-item:1b3934b5c87ac6",
        [{"source": "复合函数的极限定理", "target": "复合函数的连续性", "type": "DERIVES", "description": "复合函数极限定理参与推出复合函数的连续性定理。"}],
        "审核意见中的“连续函数的定义”不作为独立节点；保留可落地的已有推导依据“复合函数的极限定理”。",
    )

    accept_repair(
        "review-item:2d39f3df2780c6",
        [{"source": "连续函数的四则运算连续性", "target": "初等函数的连续性", "type": "DERIVES", "description": "连续函数运算法则参与推出初等函数的连续性。"}],
        "审核意见中的“连续函数的定义及运算法则”不是节点；用已有“连续函数的四则运算连续性”承接运算法则依据。",
    )

    accept_repair(
        "review-item:f98785c13f901a",
        [{"source": "微分与导数关系公式", "target": "利用微分计算函数值增量的近似公式", "type": "DERIVES", "description": "由微分表达式推出函数值增量近似公式。"}],
        "审核意见中的“微分表达式(2-4-3)”已由“微分与导数关系公式”节点承接。",
    )

    accept_repair(
        "review-item:e99e941f77e7cc",
        [{"source": "积分上限函数", "target": "变限积分", "type": "SUPERIOR", "description": "积分上限函数又称变上限积分，是变限积分的一种。"}],
        "“变上限积分”已作为“积分上限函数”的别名，使用既有正式节点落边。",
    )

    accept_repair(
        "review-item:6ef2d7aa77f763",
        [{"source": "积分下限函数", "target": "变限积分", "type": "SUPERIOR", "description": "积分下限函数又称变下限积分，是变限积分的一种。"}],
        "“变下限积分”已作为“积分下限函数”的别名，使用既有正式节点落边。",
    )

    accept_repair(
        "review-item:e85fc000397b13",
        [{"source": "不定积分求解", "target": "基本积分表", "type": "USES", "description": "求不定积分需要使用基本积分公式/基本积分表。"}],
        "“基本积分公式”作为“基本积分表”的别名处理，避免新增重复的公式集合节点。",
    )

    accept_repair(
        "review-item:2f470581194e81",
        [{"source": "不定积分", "target": "不定积分与原函数关系定理", "type": "HAS_PROPERTY", "description": "不定积分概念下包含其与原函数关系的核心定理。"}],
        "审核意见中的“不定积分的定义”不作为独立节点；改为概念到相关定理的 HAS_PROPERTY。",
    )

    accept_repair(
        "review-item:410d19dcce3b9f",
        [{"source": "无穷积分计算", "target": "无穷积分定义公式", "type": "USES", "description": "无穷积分计算使用无穷积分定义公式。"}],
        "“无穷积分的定义”已由“无穷积分定义公式”承接，保留正式公式节点。",
    )

    accept_repair(
        "review-item:263fe3be7b27d9",
        [{"source": "连续函数在区间上的平均值", "target": "连续函数在区间上的平均值公式", "type": "HAS_PROPERTY", "description": "平均值概念具有对应的定积分计算公式。"}],
        "审核意见中的极限表达不作为独立节点；改为概念到公式的 HAS_PROPERTY。",
    )

    accept_repair(
        "review-item:1db3a296fd67cd",
        [{"source": "电流有效值", "target": "电流有效值公式", "type": "HAS_PROPERTY", "description": "电流有效值概念具有对应的积分计算公式。"}],
        "审核意见中的“电流有效值的定义”不作为独立节点；改为概念到公式的 HAS_PROPERTY。",
    )

    accepted_set = set(accepted_repairs)
    deferred_items = [
        row
        for row in deferred_items
        if str(row.get("step7_review_item_id") or row.get("review_item_id") or "") not in accepted_set
    ]

    write_jsonl(step7_final / "approved_nodes.jsonl", approved_nodes)
    write_jsonl(step7_final / "approved_edges.jsonl", approved_edges)
    write_jsonl(step7_final / "approved_rule_cases.jsonl", approved_rule_cases)
    write_jsonl(step7_final / "review_archive.jsonl", review_archive)
    write_jsonl(step7_final / "deferred_items.jsonl", deferred_items)
    write_jsonl(step7_final / "decision_trace.jsonl", decision_trace)

    report_lines = [
        "# v4.4 Step 7F Conflict Repair Report",
        "",
        f"- accepted_repairs: {len(accepted_repairs)}",
        f"- kept_deferred: {len(kept_deferred)}",
        f"- approved_nodes_after: {len(approved_nodes)}",
        f"- approved_edges_after: {len(approved_edges)}",
        f"- deferred_items_after: {len(deferred_items)}",
        "",
        "说明：accepted_repairs 表示审核冲突已被处理；若修补边在 Step 6 主图中已存在，Step 8A 会按语义键去重，最终图中不会重复新增。",
        "",
        "## Accepted Repairs",
    ]
    for item_id in accepted_repairs:
        report_lines.append(f"- {item_id}")
    report_lines.extend(["", "## Kept Deferred"])
    for item_id in kept_deferred:
        report_lines.append(f"- {item_id}: 需要新增过程性方法节点，暂不落主图。")
    args.out_report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")
    print(f"[OK] Step 7F repairs -> {args.step7_final_dir}")
    print(f"[INFO] accepted_repairs={len(accepted_repairs)} kept_deferred={len(kept_deferred)} nodes={len(approved_nodes)} edges={len(approved_edges)} deferred={len(deferred_items)}")


if __name__ == "__main__":
    main()
