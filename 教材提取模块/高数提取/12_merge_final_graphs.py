# -*- coding: utf-8 -*-
"""Merge multiple v4.4 final graph directories into one importable package."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


GRAPH_FILES = [
    "final_core_nodes.jsonl",
    "final_core_edges.jsonl",
    "final_application_nodes.jsonl",
    "final_application_edges.jsonl",
    "final_rule_cases.jsonl",
    "final_knowledge_groups.jsonl",
    "final_knowledge_group_edges.jsonl",
    "final_review_pending.jsonl",
    "final_archived_items.jsonl",
    "merge_execution_trace.jsonl",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge v4.4 final graph directories.")
    parser.add_argument("--final-dir", type=Path, action="append", required=True)
    parser.add_argument("--extra-core-edges", type=Path, action="append", default=[])
    parser.add_argument("--out-final-dir", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def read_jsonl(path: Path, required: bool = False) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSONL not found: {path}")
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def item_id(row: dict[str, Any], file_name: str) -> str:
    for key in ["node_id", "edge_id", "rule_case_id", "group_id", "review_item_id"]:
        value = str(row.get(key) or "")
        if value:
            return f"{file_name}:{value}"
    return f"{file_name}:{json.dumps(row, ensure_ascii=False, sort_keys=True)}"


def edge_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("source_node_id") or ""),
        str(row.get("target_node_id") or ""),
        str(row.get("type") or ""),
    )


def merge_rows(file_name: str, final_dirs: list[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for final_dir in final_dirs:
        for row in read_jsonl(final_dir / file_name, required=False):
            key = item_id(row, file_name)
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


def report(out_dir: Path, counts: dict[str, int], core_edges: list[dict[str, Any]]) -> str:
    lines = [
        "# 高等数学上下册合并图谱报告",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- out_final_dir: `{out_dir}`",
        "",
        "## 文件统计",
    ]
    for file_name, count in counts.items():
        lines.append(f"- {file_name}: {count}")
    lines.extend(["", "## core edge types"])
    for typ, count in sorted(Counter(row.get("type", "") for row in core_edges).items()):
        lines.append(f"- {typ}: {count}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    if args.out_final_dir.exists():
        if not args.replace:
            raise FileExistsError(f"Output final dir already exists: {args.out_final_dir}")
        import shutil

        shutil.rmtree(args.out_final_dir)
    args.out_final_dir.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    merged_by_file: dict[str, list[dict[str, Any]]] = {}
    for file_name in GRAPH_FILES:
        rows = merge_rows(file_name, args.final_dir)
        merged_by_file[file_name] = rows
        counts[file_name] = len(rows)

    core_edges = merged_by_file["final_core_edges.jsonl"]
    seen_edges = {edge_key(row) for row in core_edges if all(edge_key(row))}
    extra_appended: list[dict[str, Any]] = []
    extra_skipped: list[dict[str, Any]] = []
    for extra_path in args.extra_core_edges:
        for edge in read_jsonl(extra_path, required=False):
            key = edge_key(edge)
            if not all(key) or key in seen_edges:
                extra_skipped.append(edge)
                continue
            core_edges.append(edge)
            extra_appended.append(edge)
            seen_edges.add(key)
    counts["extra_core_edges_appended"] = len(extra_appended)
    counts["extra_core_edges_skipped"] = len(extra_skipped)
    counts["final_core_edges.jsonl"] = len(core_edges)

    for file_name, rows in merged_by_file.items():
        write_jsonl(args.out_final_dir / file_name, rows)
    write_jsonl(args.out_final_dir / "final_cross_volume_implicit_edges.jsonl", extra_appended)
    write_jsonl(args.out_final_dir / "final_cross_volume_implicit_edges_skipped.jsonl", extra_skipped)
    (args.out_final_dir / "final_assembly_report.md").write_text(
        report(args.out_final_dir, counts, core_edges),
        encoding="utf-8",
    )
    print(json.dumps({"out_final_dir": str(args.out_final_dir), **counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
