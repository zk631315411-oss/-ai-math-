# -*- coding: utf-8 -*-
"""
Export the v4.4 Step 8 final graph package into one portable JSON file.

The exported file is not used by Step 8B directly. It is a stable handoff
artifact for backup, review, transfer, or later re-import tooling.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RUN_DIR = SCRIPT_DIR / "中间产物" / "c01_c06_cumulative"
DEFAULT_FINAL_DIR = DEFAULT_RUN_DIR / "step8_final_graph"
DEFAULT_IMPORT_REPORT = DEFAULT_RUN_DIR / "neo4j_import_report.md"
DEFAULT_STEP9_RESULTS = DEFAULT_RUN_DIR / "step9_application_validation" / "step9_application_validation_results.json"
DEFAULT_OUT = DEFAULT_RUN_DIR / "gaoshu_shang_v4_4_c01_c06_kg_package.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export one JSON package from v4.4 Step 8 final graph files.")
    parser.add_argument("--final-dir", type=Path, default=DEFAULT_FINAL_DIR)
    parser.add_argument("--import-report", type=Path, default=DEFAULT_IMPORT_REPORT)
    parser.add_argument("--step9-results", type=Path, default=DEFAULT_STEP9_RESULTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--package-id", default="gaoshu_shang_v4_4_c01_c06")
    parser.add_argument("--import-batch", default="gaoshu_c01_c06_v44_20260625_step7f")
    return parser.parse_args()


def read_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSONL not found: {path}")
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def read_json(path: Path, required: bool = False) -> Any:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSON not found: {path}")
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_text(path: Path, required: bool = False) -> str:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"Text file not found: {path}")
        return ""
    return path.read_text(encoding="utf-8-sig")


def count_by(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(key) or "") for row in rows).items()))


def typed_rule_cases(rule_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    typed: list[dict[str, Any]] = []
    for row in rule_cases:
        item = dict(row)
        item.setdefault("type", "RuleCase")
        typed.append(item)
    return typed


def build_package(args: argparse.Namespace) -> dict[str, Any]:
    final_dir = args.final_dir
    core_nodes = read_jsonl(final_dir / "final_core_nodes.jsonl")
    core_edges = read_jsonl(final_dir / "final_core_edges.jsonl")
    application_nodes = read_jsonl(final_dir / "final_application_nodes.jsonl", required=False)
    application_edges = read_jsonl(final_dir / "final_application_edges.jsonl", required=False)
    rule_cases = read_jsonl(final_dir / "final_rule_cases.jsonl")
    knowledge_groups = read_jsonl(final_dir / "final_knowledge_groups.jsonl")
    knowledge_group_edges = read_jsonl(final_dir / "final_knowledge_group_edges.jsonl")
    review_pending = read_jsonl(final_dir / "final_review_pending.jsonl", required=False)
    archived_items = read_jsonl(final_dir / "final_archived_items.jsonl", required=False)
    merge_trace = read_jsonl(final_dir / "merge_execution_trace.jsonl", required=False)
    assembly_report = read_text(final_dir / "final_assembly_report.md", required=False)
    import_report = read_text(args.import_report, required=False)
    step9_results = read_json(args.step9_results, required=False)

    rule_case_nodes = typed_rule_cases(rule_cases)
    visible_nodes = core_nodes + application_nodes + rule_case_nodes + knowledge_groups
    visible_edges = core_edges + application_edges + knowledge_group_edges

    return {
        "metadata": {
            "package_id": args.package_id,
            "schema_version": "v4.4.final_package.v1",
            "textbook_id": "gaoshu_shang",
            "textbook_name": "高等数学上册",
            "chapter_range": "C01-C06",
            "source_final_dir": str(final_dir),
            "import_batch": args.import_batch,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        },
        "summary": {
            "visible_nodes": len(visible_nodes),
            "visible_edges": len(visible_edges),
            "core_nodes": len(core_nodes),
            "core_edges": len(core_edges),
            "application_nodes": len(application_nodes),
            "application_edges": len(application_edges),
            "rule_cases": len(rule_cases),
            "knowledge_groups": len(knowledge_groups),
            "knowledge_group_edges": len(knowledge_group_edges),
            "review_pending": len(review_pending),
            "archived_items": len(archived_items),
            "merge_trace_rows": len(merge_trace),
            "node_types": count_by(visible_nodes, "type"),
            "edge_types": count_by(visible_edges, "type"),
        },
        "graph": {
            "core_nodes": core_nodes,
            "core_edges": core_edges,
            "application_nodes": application_nodes,
            "application_edges": application_edges,
            "rule_cases": rule_cases,
            "knowledge_groups": knowledge_groups,
            "knowledge_group_edges": knowledge_group_edges,
        },
        "audit": {
            "review_pending": review_pending,
            "archived_items": archived_items,
            "merge_execution_trace": merge_trace,
        },
        "reports": {
            "final_assembly_report_md": assembly_report,
            "neo4j_import_report_md": import_report,
            "step9_application_validation_results": step9_results,
        },
    }


def main() -> None:
    args = parse_args()
    package = build_package(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] package -> {args.out}")
    print(json.dumps(package["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
