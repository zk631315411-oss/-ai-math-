"""
v4.4 Step 7D: apply validated review decisions.

Step 7D lands review results into approved/rejected/deferred packages. It does
not assemble the final graph and does not execute semantic merges. Accepted
merge candidates become merge_plans.jsonl for Step 8A.
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
DEFAULT_MIDDLE_DIR = SCRIPT_DIR / "中间产物"
DEFAULT_LAYER_DIR = DEFAULT_MIDDLE_DIR / "step6_layers"
DEFAULT_REVIEW_DIR = DEFAULT_MIDDLE_DIR / "step7_review"
DEFAULT_DECISIONS = DEFAULT_REVIEW_DIR / "validated_review_decisions.jsonl"
DEFAULT_OUT_DIR = DEFAULT_REVIEW_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply v4.4 Step 7D validated review decisions.")
    parser.add_argument("--layer-dir", type=Path, default=DEFAULT_LAYER_DIR)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--approval-label", default="validated_step7c")
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


def ensure_source_code(item: dict[str, Any]) -> dict[str, Any]:
    item.setdefault("source_code", source_code(item))
    return item


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


def rule_case_identity(rule_case: dict[str, Any]) -> str:
    if rule_case.get("rule_case_id"):
        return str(rule_case.get("rule_case_id"))
    return stable_id(
        "rule-case-key",
        [
            str(rule_case.get("owner_node_id") or rule_case.get("owner_name") or ""),
            str(rule_case.get("case_name") or ""),
            str(rule_case.get("evidence_span") or ""),
        ],
    )


def add_unique(rows: list[dict[str, Any]], row: dict[str, Any], key_func) -> bool:
    existing = {key_func(item) for item in rows}
    key = key_func(row)
    if key in existing:
        return False
    rows.append(row)
    return True


def approved_item(row: dict[str, Any], layer: str, decision: dict[str, Any], status: str) -> dict[str, Any]:
    item = dict(row)
    item["kg_layer"] = layer
    item["step7_status"] = status
    item["step7_approval_label"] = decision.get("approval_label", "")
    item["step7_review_item_id"] = decision.get("review_item_id", "")
    item["step7_action"] = decision.get("action", "")
    item["step7_basis"] = decision.get("basis", "")
    item["final_import_ready"] = True
    item["step7_generated_at"] = now_iso()
    if item.get("item_kind") == "node" or item.get("type") in {"Concept", "Method", "Formula", "Theorem", "ProblemClass"}:
        item["rule_cases"] = []
        item["rule_cases_step7_policy"] = "rule_cases_are_reviewed_separately"
    return ensure_source_code(item)


def archived_item(source: dict[str, Any], decision: dict[str, Any], status: str, item_kind: str) -> dict[str, Any]:
    item = dict(source)
    item["item_kind"] = item_kind
    item["archive_status"] = status
    item["step7_review_item_id"] = decision.get("review_item_id", "")
    item["step7_action"] = decision.get("action", "")
    item["step7_basis"] = decision.get("basis", "")
    item["final_import_ready"] = False
    item["step7_generated_at"] = now_iso()
    return item


def trace_row(decision: dict[str, Any], result: str, note: str = "", item_id: str = "") -> dict[str, Any]:
    return {
        "review_item_id": decision.get("review_item_id", ""),
        "item_kind": decision.get("item_kind", ""),
        "item_id": item_id or decision.get("item_id", ""),
        "title": decision.get("title", ""),
        "action": decision.get("action", ""),
        "target_layer": decision.get("target_layer", ""),
        "basis": decision.get("basis", ""),
        "validation_status": decision.get("validation_status", ""),
        "result": result,
        "note": note,
        "generated_at": now_iso(),
    }


def enrich_rewritten_edge(rewrite: dict[str, Any], source: dict[str, Any], nodes_by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    item = dict(source)
    item.update({key: value for key, value in rewrite.items() if key != "operation"})
    source_node = nodes_by_name.get(str(item.get("source_name") or ""), {})
    target_node = nodes_by_name.get(str(item.get("target_name") or ""), {})
    item["source_node_id"] = source_node.get("node_id", item.get("source_node_id", ""))
    item["target_node_id"] = target_node.get("node_id", item.get("target_node_id", ""))
    item["source_type"] = source_node.get("type", item.get("source_type", ""))
    item["target_type"] = target_node.get("type", item.get("target_type", ""))
    item["kg_layer"] = item.get("kg_layer") or "core"
    item["edge_id"] = stable_id(
        f"{item.get('textbook_id', 'unknown')}:review-edge",
        [str(item.get("source_node_id") or item.get("source_name") or ""), str(item.get("target_node_id") or item.get("target_name") or ""), str(item.get("type") or "")],
    )
    return item


def enrich_rewritten_rule_case(rewrite: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    item = dict(source)
    item.update({key: value for key, value in rewrite.items() if key != "operation"})
    item["kg_layer"] = "rule_case"
    if not item.get("rule_case_id"):
        item["rule_case_id"] = rule_case_identity(item)
    return item


def node_brief_from_candidate(candidate: dict[str, Any], node_id: str, name: str) -> dict[str, Any]:
    for field in ["node_a", "node_b"]:
        node = candidate.get(field) or {}
        if node_id and str(node.get("node_id") or "") == node_id:
            return dict(node)
        if name and str(node.get("name") or "") == name:
            return dict(node)
    return {"node_id": node_id, "name": name, "type": candidate.get("node_type", "")}


def merge_plan_from_candidate(candidate: dict[str, Any], decision: dict[str, Any]) -> dict[str, Any]:
    primary_id = str(candidate.get("primary_node_id") or "")
    primary_name = str(candidate.get("primary_name") or "")
    secondary_id = str(candidate.get("secondary_node_id") or "")
    secondary_name = str(candidate.get("secondary_name") or "")
    plan = {
        "merge_plan_id": stable_id("merge-plan", [primary_id, secondary_id, str(decision.get("review_item_id") or "")]),
        "review_item_id": decision.get("review_item_id", ""),
        "primary_node_id": primary_id,
        "primary_name": primary_name,
        "secondary_node_id": secondary_id,
        "secondary_name": secondary_name,
        "node_type": candidate.get("node_type", ""),
        "primary_node": node_brief_from_candidate(candidate, primary_id, primary_name),
        "secondary_node": node_brief_from_candidate(candidate, secondary_id, secondary_name),
        "merge_actions": [
            "keep_primary_node",
            "merge_aliases",
            "merge_description_source_evidence",
            "redirect_edges_to_primary",
            "redirect_rule_case_owner_to_primary",
            "mark_secondary_as_merged",
            "dedupe_edges_after_redirect",
        ],
        "basis": decision.get("basis", ""),
        "merge_score": candidate.get("merge_score", ""),
        "name_similarity": candidate.get("name_similarity", ""),
        "alias_similarity": candidate.get("alias_similarity", ""),
        "text_similarity": candidate.get("text_similarity", ""),
        "role_similarity": candidate.get("role_similarity", ""),
        "generated_at": now_iso(),
    }
    return plan


def load_existing_main(layer_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        read_jsonl(layer_dir / "explicit_core_nodes.jsonl", required=False),
        read_jsonl(layer_dir / "explicit_core_edges.jsonl", required=False),
        read_jsonl(layer_dir / "example_application_nodes.jsonl", required=False),
        read_jsonl(layer_dir / "example_application_edges.jsonl", required=False),
        read_jsonl(layer_dir / "rule_cases.jsonl", required=False),
    )


def write_summary(path: Path, decisions: list[dict[str, Any]], approved_nodes: list[dict[str, Any]], approved_edges: list[dict[str, Any]], approved_rule_cases: list[dict[str, Any]], merge_plans: list[dict[str, Any]], archive: list[dict[str, Any]], deferred: list[dict[str, Any]]) -> None:
    counts = Counter((row.get("item_kind", ""), row.get("action", "")) for row in decisions)
    lines = [
        "# v4.4 Step 7D Review Application Summary",
        "",
        f"- decisions: {len(decisions)}",
        f"- approved_nodes: {len(approved_nodes)}",
        f"- approved_edges: {len(approved_edges)}",
        f"- approved_rule_cases: {len(approved_rule_cases)}",
        f"- merge_plans: {len(merge_plans)}",
        f"- review_archive: {len(archive)}",
        f"- deferred_items: {len(deferred)}",
        "",
        "## Decision Counts",
    ]
    for (kind, action), count in sorted(counts.items()):
        lines.append(f"- {kind} / {action}: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    base_core_nodes, base_core_edges, base_app_nodes, base_app_edges, base_rule_cases = load_existing_main(args.layer_dir)
    approved_nodes = [approved_item(row, "core", {"approval_label": "step6_main", "action": "base"}, "accepted_from_step6") for row in base_core_nodes]
    approved_edges = [approved_item(row, "core", {"approval_label": "step6_main", "action": "base"}, "accepted_from_step6") for row in base_core_edges]
    approved_app_nodes = [approved_item(row, "example_application", {"approval_label": "step6_main", "action": "base"}, "accepted_from_step6") for row in base_app_nodes]
    approved_app_edges = [approved_item(row, "example_application", {"approval_label": "step6_main", "action": "base"}, "accepted_from_step6") for row in base_app_edges]
    approved_rule_cases = [approved_item(row, "rule_case", {"approval_label": "step6_main", "action": "base"}, "accepted_from_step6") for row in base_rule_cases]

    nodes_by_name = {str(node.get("name") or ""): node for node in [*approved_nodes, *approved_app_nodes] if node.get("name")}
    decisions = read_jsonl(args.decisions)
    archive: list[dict[str, Any]] = []
    deferred: list[dict[str, Any]] = []
    merge_plans: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []

    for raw_decision in decisions:
        decision = dict(raw_decision)
        decision["approval_label"] = args.approval_label
        action = str(decision.get("action") or "")
        item_kind = str(decision.get("item_kind") or "")
        source = dict(decision.get("source_item") or {})

        if action == "accept":
            if item_kind == "node":
                item = approved_item(source, "example_application" if decision.get("target_layer") == "example_application" else "core", decision, "accepted_by_step7")
                add_unique(approved_app_nodes if item["kg_layer"] == "example_application" else approved_nodes, item, node_identity)
                nodes_by_name.setdefault(str(item.get("name") or ""), item)
                traces.append(trace_row(decision, "accept", item_id=node_identity(item)))
            elif item_kind == "edge":
                item = approved_item(source, "example_application" if decision.get("target_layer") == "example_application" else "core", decision, "accepted_by_step7")
                add_unique(approved_app_edges if item["kg_layer"] == "example_application" else approved_edges, item, edge_identity)
                traces.append(trace_row(decision, "accept", item_id=edge_identity(item)))
            elif item_kind == "rule_case":
                item = approved_item(source, "rule_case", decision, "accepted_by_step7")
                add_unique(approved_rule_cases, item, rule_case_identity)
                traces.append(trace_row(decision, "accept", item_id=rule_case_identity(item)))
            else:
                deferred.append(archived_item(source, decision, "deferred_unknown_accept_item_kind", item_kind))
                traces.append(trace_row(decision, "defer", "unknown_accept_item_kind"))
        elif action == "rewrite":
            rewrite = decision.get("rewritten_item") or {}
            archive.append(archived_item(source, decision, "rewritten_original_archived", item_kind))
            if item_kind == "edge" and rewrite.get("operation") == "replace_edge":
                item = approved_item(enrich_rewritten_edge(rewrite, source, nodes_by_name), str(rewrite.get("kg_layer") or "core"), decision, "rewritten_by_step7")
                add_unique(approved_app_edges if item["kg_layer"] == "example_application" else approved_edges, item, edge_identity)
                traces.append(trace_row(decision, "rewrite", "rewritten_edge_approved", edge_identity(item)))
            elif item_kind == "rule_case" and rewrite.get("operation") == "replace_rule_case":
                item = approved_item(enrich_rewritten_rule_case(rewrite, source), "rule_case", decision, "rewritten_by_step7")
                add_unique(approved_rule_cases, item, rule_case_identity)
                traces.append(trace_row(decision, "rewrite", "rewritten_rule_case_approved", rule_case_identity(item)))
            else:
                deferred.append(archived_item(source, decision, "deferred_invalid_rewrite_after_validation", item_kind))
                traces.append(trace_row(decision, "defer", "invalid_rewrite_after_validation"))
        elif action == "reject":
            archive.append(archived_item(source, decision, "rejected_by_step7", item_kind))
            traces.append(trace_row(decision, "reject"))
        elif action == "accept_merge":
            plan = merge_plan_from_candidate(source, decision)
            merge_plans.append(plan)
            traces.append(trace_row(decision, "accept_merge", item_id=plan["merge_plan_id"]))
        elif action == "reject_merge":
            archive.append(archived_item(source, decision, "merge_candidate_rejected_by_step7", "merge_candidate"))
            traces.append(trace_row(decision, "reject_merge"))
        else:
            deferred.append(archived_item(source, decision, "deferred_by_step7", item_kind))
            traces.append(trace_row(decision, "defer"))

    write_jsonl(out_dir / "approved_nodes.jsonl", approved_nodes)
    write_jsonl(out_dir / "approved_edges.jsonl", approved_edges)
    write_jsonl(out_dir / "approved_application_nodes.jsonl", approved_app_nodes)
    write_jsonl(out_dir / "approved_application_edges.jsonl", approved_app_edges)
    write_jsonl(out_dir / "approved_rule_cases.jsonl", approved_rule_cases)
    write_jsonl(out_dir / "merge_plans.jsonl", merge_plans)
    write_jsonl(out_dir / "review_archive.jsonl", archive)
    write_jsonl(out_dir / "deferred_items.jsonl", deferred)
    write_jsonl(out_dir / "decision_trace.jsonl", traces)
    write_summary(out_dir / "step7d_application_summary.md", decisions, [*approved_nodes, *approved_app_nodes], [*approved_edges, *approved_app_edges], approved_rule_cases, merge_plans, archive, deferred)
    print(f"[OK] Step 7D review package -> {out_dir}")
    print(f"[INFO] approved nodes/edges/rules={len(approved_nodes)+len(approved_app_nodes)}/{len(approved_edges)+len(approved_app_edges)}/{len(approved_rule_cases)} merge_plans={len(merge_plans)}")


if __name__ == "__main__":
    main()
