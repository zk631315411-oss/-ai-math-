# -*- coding: utf-8 -*-
"""
v4.4.1 Step 7G: apply narrow repairs found by real scenario spot checks.

This script is deliberately small. It does not run global implicit edge
prediction. It only adds high-confidence, textbook-supported edges that were
missed by the extraction flow and exposed by Step 9 application validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = SCRIPT_DIR / "中间产物" / "c01_c06_cumulative"
DEFAULT_STEP7_FINAL = DEFAULT_RUN_DIR / "step7_final"


REPAIR_SPECS = [
    {
        "source": "不定积分求解",
        "target": "第一类换元法",
        "type": "USES",
        "method_evidence": "通过上述这种换元而求得不定积分的方法称为第一类换元法.",
        "description": "不定积分求解可以使用第一类换元法。教材在“不定积分与原函数的求法”中说明随后介绍几种求不定积分的有效方法，并在该小节中定义第一类换元法。",
    },
    {
        "source": "不定积分求解",
        "target": "第二类换元法",
        "type": "USES",
        "method_evidence": "受这一启发, 对于某些不定积分 $\\int f(x) \\mathrm{d}x$ , 我们也可以直接做变量代换 $x = \\psi(t)$ , 使得被积式 $f(x) \\mathrm{d}x$ 化为新的被积式 $f[\\psi(t)]\\psi'(t) \\mathrm{d}t$ , 而由此比较容易求出不定积分, 这就是所谓的第二类换元法.",
        "description": "不定积分求解可以使用第二类换元法。教材在“不定积分与原函数的求法”中说明随后介绍几种求不定积分的有效方法，并在该小节中定义第二类换元法。",
    },
    {
        "source": "不定积分求解",
        "target": "分部积分法",
        "type": "USES",
        "method_evidence": "其中 $u, v$ 的选取以 $\\int v \\mathrm{d}u$ 比 $\\int u \\mathrm{d}v$ 易求为原则. 利用该公式求不定积分的方法称为分部积分法.",
        "description": "不定积分求解可以使用分部积分法。教材在“不定积分与原函数的求法”中说明随后介绍几种求不定积分的有效方法，并在该小节中定义分部积分法。",
    },
]

RELATION_EVIDENCE = "直接利用基本积分公式和不定积分的性质可计算出的不定积分是非常有限的,下面介绍几种求不定积分的有效方法."


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply v4.4.1 high-confidence spot-check repairs.")
    parser.add_argument("--step7-final-dir", type=Path, default=DEFAULT_STEP7_FINAL)
    parser.add_argument("--out-report", type=Path, default=DEFAULT_STEP7_FINAL / "step7g_spotcheck_repair_report.md")
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


def ensure_source_code(row: dict[str, Any]) -> None:
    row.setdefault("source_code", source_code(row))


def index_nodes(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for node in nodes:
        name = str(node.get("name") or "").strip()
        if name:
            by_name[name] = node
        for alias in node.get("aliases") or []:
            alias_name = str(alias).strip()
            if alias_name and alias_name not in by_name:
                by_name[alias_name] = node
    return by_name


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


def trace_identity(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("review_item_id") or ""),
            str(row.get("action") or ""),
            str(row.get("result") or ""),
            str(row.get("item_id") or ""),
        ]
    )


def make_edge(source: dict[str, Any], target: dict[str, Any], spec: dict[str, str]) -> dict[str, Any]:
    textbook_id = str(target.get("textbook_id") or source.get("textbook_id") or "gaoshu_shang")
    edge = {
        "candidate_id": stable_id(
            f"{textbook_id}:spotcheck-edge-cand",
            [str(source.get("node_id") or source.get("name") or ""), str(target.get("node_id") or target.get("name") or ""), spec["type"]],
        ),
        "edge_id": stable_id(
            f"{textbook_id}:edge",
            [str(source.get("node_id") or source.get("name") or ""), str(target.get("node_id") or target.get("name") or ""), spec["type"], "core"],
        ),
        "source_node_id": source.get("node_id", ""),
        "source_name": source.get("name", ""),
        "target_node_id": target.get("node_id", ""),
        "target_name": target.get("name", ""),
        "type": spec["type"],
        "evidence_spans": [
            {"role": "relation_scope", "text": RELATION_EVIDENCE},
            {"role": "target_method_definition", "text": spec["method_evidence"]},
        ],
        "evidence_span": RELATION_EVIDENCE,
        "description": spec["description"],
        "confidence": 0.94,
        "review_recommended": False,
        "review_reason": "",
        "textbook_id": textbook_id,
        "textbook_name": target.get("textbook_name", source.get("textbook_name", "")),
        "chapter": target.get("chapter", source.get("chapter", "")),
        "section": target.get("section", source.get("section", "")),
        "subsection": target.get("subsection", source.get("subsection", "")),
        "section_node_id": target.get("section_node_id", source.get("section_node_id", "")),
        "source_scope": target.get("source_scope", "core_content"),
        "line_start": target.get("line_start", ""),
        "line_end": target.get("line_end", ""),
        "layer": "implicit_high_confidence",
        "review_status": "auto_accept",
        "source_type": source.get("type", ""),
        "target_type": target.get("type", ""),
        "source_review_status": source.get("review_status", ""),
        "target_review_status": target.get("review_status", ""),
        "kg_layer": "core",
        "step5_status": "step7g_spotcheck_repair",
        "step6_layer": "implicit_deferred",
        "step6_status": "spotcheck_repair",
        "step7_status": "accepted_by_step7g_spotcheck_repair",
        "step7_review_item_id": "step9-real-scenario-spotcheck",
        "step7_action": "repair_accept",
        "step7_basis": "Step 9 真实场景抽检发现不定积分求解到核心求解方法缺少高层 USES 边；教材原文明确说明此处介绍几种求不定积分的有效方法，并随后定义该方法。",
        "repair_source": "real_scenario_spotcheck",
        "repair_policy": "v4.4.1_launch_high_confidence_only",
        "final_import_ready": True,
        "step7_generated_at": now_iso(),
    }
    ensure_source_code(edge)
    return edge


def main() -> None:
    args = parse_args()
    step7_final = args.step7_final_dir
    approved_nodes = read_jsonl(step7_final / "approved_nodes.jsonl")
    approved_edges = read_jsonl(step7_final / "approved_edges.jsonl")
    decision_trace = read_jsonl(step7_final / "decision_trace.jsonl", required=False)

    nodes_by_name = index_nodes(approved_nodes)
    edge_keys = {edge_identity(edge) for edge in approved_edges}
    trace_keys = {trace_identity(row) for row in decision_trace}

    added_edges: list[dict[str, Any]] = []
    skipped_existing: list[str] = []
    missing_nodes: list[str] = []

    for spec in REPAIR_SPECS:
        source = nodes_by_name.get(spec["source"])
        target = nodes_by_name.get(spec["target"])
        if not source:
            missing_nodes.append(spec["source"])
            continue
        if not target:
            missing_nodes.append(spec["target"])
            continue
        edge = make_edge(source, target, spec)
        key = edge_identity(edge)
        if key in edge_keys:
            skipped_existing.append(f"{spec['source']} --{spec['type']}--> {spec['target']}")
            continue
        approved_edges.append(edge)
        edge_keys.add(key)
        added_edges.append(edge)
        trace = {
            "review_item_id": "step9-real-scenario-spotcheck",
            "item_kind": "edge",
            "item_id": edge["edge_id"],
            "action": "step7g_spotcheck_repair",
            "target_layer": "core",
            "result": "accepted",
            "note": edge["description"],
            "generated_at": now_iso(),
        }
        trace_key = trace_identity(trace)
        if trace_key not in trace_keys:
            decision_trace.append(trace)
            trace_keys.add(trace_key)

    if missing_nodes:
        missing = ", ".join(sorted(set(missing_nodes)))
        raise RuntimeError(f"Cannot apply spot-check repairs; missing nodes: {missing}")

    write_jsonl(step7_final / "approved_edges.jsonl", approved_edges)
    write_jsonl(step7_final / "decision_trace.jsonl", decision_trace)
    write_jsonl(step7_final / "step7g_added_edges.jsonl", added_edges)

    report_lines = [
        "# v4.4.1 Step 7G Spot-Check Repair Report",
        "",
        f"- generated_at: `{now_iso()}`",
        "- scope: 仅修复 Step 9 真实场景抽检暴露出的高置信缺边，不做全局隐式边预测。",
        f"- added_edges: {len(added_edges)}",
        f"- skipped_existing: {len(skipped_existing)}",
        f"- approved_edges_after: {len(approved_edges)}",
        "",
        "## 判断依据",
        "",
        f"- 关系总证据：{RELATION_EVIDENCE}",
        "- 三个目标方法均已是正式节点，且教材在同一小节内分别给出定义。",
        "- 修复关系限定为 ProblemClass --USES--> Method，用于支撑上线前真实场景中的方法推荐和路径追溯。",
        "",
        "## 新增边",
    ]
    for edge in added_edges:
        report_lines.append(f"- {edge['source_name']} --{edge['type']}--> {edge['target_name']}")
    if skipped_existing:
        report_lines.extend(["", "## 已存在，未重复添加"])
        report_lines.extend(f"- {item}" for item in skipped_existing)
    args.out_report.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(f"[OK] Step 7G spot-check repairs -> {step7_final}")
    print(f"[INFO] added_edges={len(added_edges)} skipped_existing={len(skipped_existing)} approved_edges={len(approved_edges)}")


if __name__ == "__main__":
    main()
