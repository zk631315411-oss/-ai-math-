"""
v4.4 Step 7C: validate AI review decisions and isolate conflicts.

Hard constraints are enforced here. AI suggestions cannot accept edges with
missing endpoints, rule cases with missing owners, invalid rewrites, or merges
between different node types.
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
DEFAULT_AI_DECISIONS = DEFAULT_REVIEW_DIR / "ai_review_decisions.jsonl"
DEFAULT_VALIDATED = DEFAULT_REVIEW_DIR / "validated_review_decisions.jsonl"
DEFAULT_CONFLICT_ITEMS = DEFAULT_REVIEW_DIR / "conflict_review_items.jsonl"
DEFAULT_CONFLICT_DECISIONS = DEFAULT_REVIEW_DIR / "conflict_review_decisions.jsonl"
DEFAULT_ERRORS = DEFAULT_REVIEW_DIR / "decision_validation_errors.jsonl"
DEFAULT_SUMMARY = DEFAULT_REVIEW_DIR / "decision_validation_summary.md"

VALID_EDGE_TYPES = {"SUPERIOR", "EQUATIVE", "PART_OF", "HAS_PROPERTY", "USES", "GETS", "DERIVES"}
VALID_RULE_LOGIC = {"AND", "OR", "IFF", "PIECEWISE", "UNKNOWN"}
STANDARD_ACTIONS = {"accept", "reject", "rewrite", "defer"}
MERGE_ACTIONS = {"accept_merge", "reject_merge", "defer"}
BLOCKING_MERGE_EDGE_TYPES = {"SUPERIOR", "PART_OF", "HAS_PROPERTY", "USES", "GETS", "DERIVES"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate v4.4 Step 7B AI review decisions.")
    parser.add_argument("--layer-dir", type=Path, default=DEFAULT_LAYER_DIR)
    parser.add_argument("--ai-decisions", type=Path, default=DEFAULT_AI_DECISIONS)
    parser.add_argument("--validated-out", type=Path, default=DEFAULT_VALIDATED)
    parser.add_argument("--conflict-items-out", type=Path, default=DEFAULT_CONFLICT_ITEMS)
    parser.add_argument("--conflict-decisions-out", type=Path, default=DEFAULT_CONFLICT_DECISIONS)
    parser.add_argument("--errors-out", type=Path, default=DEFAULT_ERRORS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
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


def node_identity(node: dict[str, Any]) -> str:
    node_id = str(node.get("node_id") or "")
    if node_id:
        return node_id
    return stable_id("node-key", [str(node.get("name") or ""), str(node.get("type") or "")])


def load_context(layer_dir: Path) -> dict[str, Any]:
    nodes = (
        read_jsonl(layer_dir / "explicit_core_nodes.jsonl", required=False)
        + read_jsonl(layer_dir / "example_application_nodes.jsonl", required=False)
        + read_jsonl(layer_dir / "review_pending_nodes.jsonl", required=False)
    )
    edges = (
        read_jsonl(layer_dir / "explicit_core_edges.jsonl", required=False)
        + read_jsonl(layer_dir / "example_application_edges.jsonl", required=False)
        + read_jsonl(layer_dir / "review_pending_edges.jsonl", required=False)
    )
    node_ids = {str(node.get("node_id") or "") for node in nodes if node.get("node_id")}
    node_names = {str(node.get("name") or "") for node in nodes if node.get("name")}
    nodes_by_id = {str(node.get("node_id") or ""): node for node in nodes if node.get("node_id")}
    nodes_by_name = {str(node.get("name") or ""): node for node in nodes if node.get("name")}
    related_pairs: set[frozenset[str]] = set()
    for edge in edges:
        if str(edge.get("type") or "") not in BLOCKING_MERGE_EDGE_TYPES:
            continue
        source_id = str(edge.get("source_node_id") or "")
        target_id = str(edge.get("target_node_id") or "")
        if source_id and target_id and source_id != target_id:
            related_pairs.add(frozenset((source_id, target_id)))
    return {
        "nodes": nodes,
        "edges": edges,
        "node_ids": node_ids,
        "node_names": node_names,
        "nodes_by_id": nodes_by_id,
        "nodes_by_name": nodes_by_name,
        "related_pairs": related_pairs,
    }


def normalize_action(decision: dict[str, Any]) -> str:
    action = str(decision.get("action") or decision.get("recommendation") or "").strip().lower()
    item_kind = str(decision.get("item_kind") or "")
    if item_kind == "merge_candidate":
        return action if action in MERGE_ACTIONS else "defer"
    return action if action in STANDARD_ACTIONS else "defer"


def force_defer(decision: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    fixed = dict(decision)
    fixed["action"] = "defer"
    fixed["target_layer"] = "review_pending"
    fixed["validation_status"] = "conflict_deferred"
    fixed["validation_errors"] = errors
    fixed["validated_at"] = now_iso()
    return fixed


def force_reject_merge(decision: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    fixed = dict(decision)
    fixed["action"] = "reject_merge"
    fixed["target_layer"] = "rejected_archive"
    fixed["validation_status"] = "conflict_rejected_merge"
    fixed["validation_errors"] = errors
    fixed["validated_at"] = now_iso()
    return fixed


def edge_endpoints_exist(edge: dict[str, Any], context: dict[str, Any]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    source_id = str(edge.get("source_node_id") or "")
    target_id = str(edge.get("target_node_id") or "")
    source_name = str(edge.get("source_name") or "")
    target_name = str(edge.get("target_name") or "")
    if source_id:
        if source_id not in context["node_ids"]:
            missing.append(f"missing_source_id:{source_id}")
    elif source_name not in context["node_names"]:
        missing.append(f"missing_source_name:{source_name}")
    if target_id:
        if target_id not in context["node_ids"]:
            missing.append(f"missing_target_id:{target_id}")
    elif target_name not in context["node_names"]:
        missing.append(f"missing_target_name:{target_name}")
    return not missing, missing


def rule_case_owner_exists(rule_case: dict[str, Any], context: dict[str, Any]) -> bool:
    owner_id = str(rule_case.get("owner_node_id") or "")
    owner_name = str(rule_case.get("owner_name") or "")
    return bool((owner_id and owner_id in context["node_ids"]) or (owner_name and owner_name in context["node_names"]))


def validate_rewrite(rewrite: Any, item_kind: str, context: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(rewrite, dict):
        return ["missing_rewritten_item"]
    operation = str(rewrite.get("operation") or "")
    if item_kind == "edge":
        if operation != "replace_edge":
            errors.append("edge_rewrite_requires_replace_edge")
        if str(rewrite.get("type") or "") not in VALID_EDGE_TYPES:
            errors.append("invalid_rewrite_edge_type")
        if not rewrite.get("source_name") or not rewrite.get("target_name"):
            errors.append("missing_rewrite_edge_endpoint")
        if rewrite.get("source_name") and rewrite.get("source_name") not in context["node_names"]:
            errors.append(f"missing_rewrite_source_name:{rewrite.get('source_name')}")
        if rewrite.get("target_name") and rewrite.get("target_name") not in context["node_names"]:
            errors.append(f"missing_rewrite_target_name:{rewrite.get('target_name')}")
    elif item_kind == "rule_case":
        if operation != "replace_rule_case":
            errors.append("rule_case_rewrite_requires_replace_rule_case")
        if not rewrite.get("conditions") or not rewrite.get("outcomes"):
            errors.append("rewrite_rule_case_missing_condition_or_outcome")
        if str(rewrite.get("condition_logic") or "UNKNOWN") not in VALID_RULE_LOGIC:
            errors.append("invalid_rewrite_rule_logic")
    elif item_kind == "node":
        errors.append("node_rewrite_disabled_in_v4_4_review_flow")
    else:
        errors.append(f"unknown_rewrite_item_kind:{item_kind}")
    return errors


def merge_nodes(candidate: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    primary_id = str(candidate.get("primary_node_id") or "")
    primary_name = str(candidate.get("primary_name") or "")
    secondary_id = str(candidate.get("secondary_node_id") or "")
    secondary_name = str(candidate.get("secondary_name") or "")
    primary = context["nodes_by_id"].get(primary_id) or context["nodes_by_name"].get(primary_name)
    secondary = context["nodes_by_id"].get(secondary_id) or context["nodes_by_name"].get(secondary_name)
    if not primary:
        primary = (candidate.get("node_a") or {}) if str((candidate.get("node_a") or {}).get("node_id") or "") == primary_id else None
    if not secondary:
        secondary = (candidate.get("node_b") or {}) if str((candidate.get("node_b") or {}).get("node_id") or "") == secondary_id else None
    return primary, secondary


def validate_merge(candidate: dict[str, Any], context: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    primary, secondary = merge_nodes(candidate, context)
    if not primary:
        errors.append("merge_primary_not_found")
    if not secondary:
        errors.append("merge_secondary_not_found")
    if primary and secondary:
        primary_type = str(primary.get("type") or candidate.get("node_type") or "")
        secondary_type = str(secondary.get("type") or candidate.get("node_type") or "")
        if primary_type and secondary_type and primary_type != secondary_type:
            errors.append(f"merge_type_mismatch:{primary_type}!={secondary_type}")
        primary_id = str(primary.get("node_id") or candidate.get("primary_node_id") or "")
        secondary_id = str(secondary.get("node_id") or candidate.get("secondary_node_id") or "")
        if primary_id and secondary_id and primary_id == secondary_id:
            errors.append("merge_same_node")
        if primary_id and secondary_id and frozenset((primary_id, secondary_id)) in context["related_pairs"]:
            errors.append("merge_blocked_by_existing_semantic_edge")
    return errors


def validate_decision(decision: dict[str, Any], context: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    action = normalize_action(decision)
    item_kind = str(decision.get("item_kind") or "")
    source = dict(decision.get("source_item") or {})
    fixed = dict(decision)
    fixed["action"] = action
    fixed["validated_at"] = now_iso()
    errors: list[str] = []

    if action == "accept" and item_kind == "edge":
        if str(source.get("type") or "") not in VALID_EDGE_TYPES:
            errors.append(f"invalid_edge_type:{source.get('type')}")
        ok, missing = edge_endpoints_exist(source, context)
        if not ok:
            errors.extend(missing)
    if action == "accept" and item_kind == "rule_case":
        if not rule_case_owner_exists(source, context):
            errors.append("rule_case_owner_not_found")
        if not source.get("conditions") or not source.get("outcomes"):
            errors.append("rule_case_missing_condition_or_outcome")
    if action == "rewrite":
        errors.extend(validate_rewrite(decision.get("rewritten_item"), item_kind, context))
    if action == "accept_merge":
        errors.extend(validate_merge(source, context))

    conflict_items: list[dict[str, Any]] = []
    validation_errors: list[dict[str, Any]] = []
    if errors:
        conflict_items.append(
            {
                "review_item_id": decision.get("review_item_id", ""),
                "item_kind": item_kind,
                "title": decision.get("title", ""),
                "ai_decision": decision,
                "conflict_errors": errors,
                "source_item": source,
                "generated_at": now_iso(),
            }
        )
        validation_errors.append(
            {
                "review_item_id": decision.get("review_item_id", ""),
                "item_kind": item_kind,
                "action": action,
                "errors": errors,
                "generated_at": now_iso(),
            }
        )
        if action == "accept_merge":
            return force_reject_merge(decision, errors), conflict_items, validation_errors
        return force_defer(decision, errors), conflict_items, validation_errors

    fixed["validation_status"] = "validated"
    fixed["validation_errors"] = []
    return fixed, conflict_items, validation_errors


def write_summary(path: Path, decisions: list[dict[str, Any]], conflicts: list[dict[str, Any]], errors: list[dict[str, Any]]) -> None:
    counts = Counter((row.get("item_kind", ""), row.get("action", ""), row.get("validation_status", "")) for row in decisions)
    lines = [
        "# v4.4 Step 7C Decision Validation Summary",
        "",
        f"- validated_decisions: {len(decisions)}",
        f"- conflict_review_items: {len(conflicts)}",
        f"- validation_errors: {len(errors)}",
        "",
        "## Counts",
    ]
    for (kind, action, status), count in sorted(counts.items()):
        lines.append(f"- {kind} / {action} / {status}: {count}")
    if errors:
        lines.extend(["", "## Error Samples"])
        for row in errors[:100]:
            lines.append(f"- {json.dumps(row, ensure_ascii=False)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    context = load_context(args.layer_dir)
    ai_decisions = read_jsonl(args.ai_decisions)
    validated: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for decision in ai_decisions:
        fixed, item_conflicts, item_errors = validate_decision(decision, context)
        validated.append(fixed)
        conflicts.extend(item_conflicts)
        errors.extend(item_errors)

    # In this conservative implementation, conflict decisions are the guarded
    # validated decisions for conflict items. A future optional second AI pass
    # can write richer replacements here, but hard constraints remain final.
    conflict_ids = {str(row.get("review_item_id") or "") for row in conflicts}
    conflict_decisions = [row for row in validated if str(row.get("review_item_id") or "") in conflict_ids]

    write_jsonl(args.validated_out, validated)
    write_jsonl(args.conflict_items_out, conflicts)
    write_jsonl(args.conflict_decisions_out, conflict_decisions)
    write_jsonl(args.errors_out, errors)
    write_summary(args.summary, validated, conflicts, errors)
    print(f"[OK] validated decisions -> {args.validated_out}")
    print(f"[OK] conflicts/errors -> {len(conflicts)}/{len(errors)}")


if __name__ == "__main__":
    main()
