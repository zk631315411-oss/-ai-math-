"""
v4.4 Step 7A: build unified review items.

Step 7A does not make decisions. It only converts Step 6 pending packages into
one auditable review-item format for AI review, rule validation, and tracing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_LAYER_DIR = SCRIPT_DIR / "中间产物" / "step6_layers"
DEFAULT_OUT_DIR = SCRIPT_DIR / "中间产物" / "step7_review"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build v4.4 Step 7A unified review items.")
    parser.add_argument("--layer-dir", type=Path, default=DEFAULT_LAYER_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def read_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSONL not found: {path}")
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}:{digest}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if value in (None, ""):
        return []
    return [str(value)]


def warnings_from(item: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for field in [
        "validation_warnings",
        "pre_audit_hard_warnings",
        "audit_guard_warnings",
        "relation_audit_guard_warnings",
        "llm_audit_guard_warnings",
    ]:
        result.extend(as_list(item.get(field)))
    if item.get("review_reason"):
        result.append(str(item.get("review_reason")))
    return list(dict.fromkeys(result))


def source_code(item: dict[str, Any]) -> str:
    if item.get("source_code"):
        return str(item.get("source_code"))
    section_node_id = str(item.get("section_node_id") or "").strip()
    textbook_id = str(item.get("textbook_id") or "").strip()
    base = section_node_id or textbook_id or "unknown-source"
    line_start = item.get("line_start")
    line_end = item.get("line_end")
    if line_start not in (None, "", 0) or line_end not in (None, "", 0):
        return f"{base}:L{line_start or ''}-L{line_end or ''}"
    return base


def base_review_item(
    item_kind: str,
    item_id: str,
    title: str,
    source_item: dict[str, Any],
    allowed_actions: list[str],
    context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "review_item_id": stable_id("review-item", [item_kind, item_id, title]),
        "item_kind": item_kind,
        "item_id": item_id,
        "title": title,
        "source_item": source_item,
        "context": context,
        "allowed_actions": allowed_actions,
        "default_action": "defer",
        "risk_flags": warnings_from(source_item),
        "source_code": source_code(source_item),
        "generated_at": now_iso(),
    }


def node_review_item(node: dict[str, Any]) -> dict[str, Any]:
    return base_review_item(
        "node",
        str(node.get("node_id") or ""),
        f"{node.get('type', '')} {node.get('name', '')}",
        node,
        ["accept", "reject", "rewrite", "defer"],
        {
            "kg_layer": node.get("kg_layer") or node.get("step6_layer") or "core",
            "name": node.get("name", ""),
            "type": node.get("type", ""),
            "definition": node.get("definition", ""),
            "description": node.get("description", ""),
            "evidence_span": node.get("evidence_span", ""),
        },
    )


def edge_review_item(edge: dict[str, Any]) -> dict[str, Any]:
    return base_review_item(
        "edge",
        str(edge.get("edge_id") or ""),
        f"{edge.get('type', '')} {edge.get('source_name', '')} -> {edge.get('target_name', '')}",
        edge,
        ["accept", "reject", "rewrite", "defer"],
        {
            "kg_layer": edge.get("kg_layer") or edge.get("step6_layer") or "core",
            "edge_type": edge.get("type", ""),
            "source_node_id": edge.get("source_node_id", ""),
            "source_name": edge.get("source_name", ""),
            "target_node_id": edge.get("target_node_id", ""),
            "target_name": edge.get("target_name", ""),
            "evidence_span": edge.get("evidence_span", ""),
        },
    )


def rule_case_review_item(case: dict[str, Any]) -> dict[str, Any]:
    return base_review_item(
        "rule_case",
        str(case.get("rule_case_id") or ""),
        f"RuleCase {case.get('owner_name', '')} / {case.get('case_name', '')}",
        case,
        ["accept", "reject", "rewrite", "defer"],
        {
            "owner_node_id": case.get("owner_node_id", ""),
            "owner_name": case.get("owner_name", ""),
            "conditions": case.get("conditions", []),
            "condition_logic": case.get("condition_logic", ""),
            "outcomes": case.get("outcomes", []),
            "evidence_span": case.get("evidence_span", ""),
        },
    )


def merge_review_item(candidate: dict[str, Any]) -> dict[str, Any]:
    return base_review_item(
        "merge_candidate",
        str(candidate.get("candidate_id") or ""),
        f"MergeCandidate {candidate.get('primary_name', '')} <- {candidate.get('secondary_name', '')}",
        candidate,
        ["accept_merge", "reject_merge", "defer"],
        {
            "primary_node_id": candidate.get("primary_node_id", ""),
            "primary_name": candidate.get("primary_name", ""),
            "secondary_node_id": candidate.get("secondary_node_id", ""),
            "secondary_name": candidate.get("secondary_name", ""),
            "node_type": candidate.get("node_type", ""),
            "merge_score": candidate.get("merge_score", ""),
            "name_similarity": candidate.get("name_similarity", ""),
            "alias_similarity": candidate.get("alias_similarity", ""),
            "text_similarity": candidate.get("text_similarity", ""),
            "role_similarity": candidate.get("role_similarity", ""),
            "candidate_reason": candidate.get("candidate_reason", []),
            "node_a": candidate.get("node_a", {}),
            "node_b": candidate.get("node_b", {}),
        },
    )


def write_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    counts = Counter(str(row.get("item_kind") or "") for row in rows)
    lines = [
        "# v4.4 Step 7A Review Items",
        "",
        "Step 7A 只构造统一审核项，不做任何接受、拒绝、改写或合并决定。",
        "",
        "## Counts",
        f"- review_items: {len(rows)}",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Actions"])
    lines.append("- node / edge / rule_case: accept / reject / rewrite / defer")
    lines.append("- merge_candidate: accept_merge / reject_merge / defer")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    review_nodes = read_jsonl(args.layer_dir / "review_pending_nodes.jsonl", required=False)
    review_edges = read_jsonl(args.layer_dir / "review_pending_edges.jsonl", required=False)
    review_rule_cases = read_jsonl(args.layer_dir / "review_pending_rule_cases.jsonl", required=False)
    review_merge_candidates = read_jsonl(args.layer_dir / "review_pending_merge_candidates.jsonl", required=False)

    rows: list[dict[str, Any]] = []
    rows.extend(node_review_item(row) for row in review_nodes)
    rows.extend(edge_review_item(row) for row in review_edges)
    rows.extend(rule_case_review_item(row) for row in review_rule_cases)
    rows.extend(merge_review_item(row) for row in review_merge_candidates)

    write_jsonl(out_dir / "review_items.jsonl", rows)
    write_summary(out_dir / "review_items_summary.md", rows)
    print(f"[OK] review items -> {out_dir / 'review_items.jsonl'}")
    print(f"[INFO] review_items={len(rows)}")


if __name__ == "__main__":
    main()
