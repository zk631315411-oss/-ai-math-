# -*- coding: utf-8 -*-
"""Merge implicit edges into a copied v4.4 Step 8 final graph directory."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append implicit edges to a copied final graph package.")
    parser.add_argument("--base-final-dir", type=Path, required=True)
    parser.add_argument("--implicit-edges", type=Path, required=True)
    parser.add_argument("--out-final-dir", type=Path, required=True)
    parser.add_argument("--replace", action="store_true")
    return parser.parse_args()


def read_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
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


def copy_final_dir(src: Path, dst: Path, replace: bool) -> None:
    if dst.exists():
        if not replace:
            raise FileExistsError(f"Output final dir already exists: {dst}")
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def edge_key(edge: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(edge.get("source_node_id") or ""),
        str(edge.get("target_node_id") or ""),
        str(edge.get("type") or ""),
    )


def build_report(
    base_edges: list[dict[str, Any]],
    implicit_edges: list[dict[str, Any]],
    appended_edges: list[dict[str, Any]],
    skipped_edges: list[dict[str, Any]],
    out_final_dir: Path,
) -> str:
    lines = [
        "# v4.4 隐式边合并报告",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- out_final_dir: `{out_final_dir}`",
        f"- base_core_edges: {len(base_edges)}",
        f"- implicit_edges_input: {len(implicit_edges)}",
        f"- implicit_edges_appended: {len(appended_edges)}",
        f"- implicit_edges_skipped_duplicate: {len(skipped_edges)}",
        f"- final_core_edges: {len(base_edges) + len(appended_edges)}",
        "",
        "## 追加隐式边类型",
    ]
    for typ, count in sorted(Counter(row.get("type", "") for row in appended_edges).items()):
        lines.append(f"- {typ}: {count}")
    lines.extend(["", "## 样例"])
    for edge in appended_edges[:20]:
        lines.append(f"- {edge.get('source_name')} --{edge.get('type')}--> {edge.get('target_name')} ({edge.get('description', '')})")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    copy_final_dir(args.base_final_dir, args.out_final_dir, args.replace)

    core_edges_path = args.out_final_dir / "final_core_edges.jsonl"
    base_edges = read_jsonl(core_edges_path)
    implicit_edges = read_jsonl(args.implicit_edges, required=False)

    seen = {edge_key(edge) for edge in base_edges}
    appended: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for edge in implicit_edges:
        key = edge_key(edge)
        if not all(key) or key in seen:
            skipped.append(edge)
            continue
        item = dict(edge)
        item["kg_layer"] = "implicit"
        item["final_import_ready"] = True
        appended.append(item)
        seen.add(key)

    write_jsonl(core_edges_path, base_edges + appended)
    write_jsonl(args.out_final_dir / "final_implicit_edges.jsonl", appended)
    write_jsonl(args.out_final_dir / "final_implicit_edges_skipped.jsonl", skipped)
    (args.out_final_dir / "implicit_merge_report.md").write_text(
        build_report(base_edges, implicit_edges, appended, skipped, args.out_final_dir),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "base_core_edges": len(base_edges),
                "implicit_input": len(implicit_edges),
                "appended": len(appended),
                "skipped_duplicate": len(skipped),
                "final_core_edges": len(base_edges) + len(appended),
                "out_final_dir": str(args.out_final_dir),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
