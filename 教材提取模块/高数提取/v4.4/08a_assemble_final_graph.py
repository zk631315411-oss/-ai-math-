"""
v4.4 Step 8A: assemble final graph package.

Step 8A reads Step 7 approved packages and merge_plans, executes approved merge
plans, generates deterministic KnowledgeGroup records, and writes the final
package consumed by Step 8B Neo4j import.
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
DEFAULT_REVIEW_DIR = SCRIPT_DIR / "中间产物" / "step7_review"
DEFAULT_OUT_DIR = SCRIPT_DIR / "中间产物" / "step8a_final_package"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble v4.4 Step 8A final graph package.")
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
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


def group_identity(group: dict[str, Any]) -> str:
    return str(group.get("group_id") or "")


def group_edge_identity(edge: dict[str, Any]) -> str:
    return str(edge.get("edge_id") or "")


def add_unique(rows: list[dict[str, Any]], row: dict[str, Any], key_func) -> bool:
    existing = {key_func(item) for item in rows}
    key = key_func(row)
    if key in existing:
        return False
    rows.append(row)
    return True


def find_node(nodes: list[dict[str, Any]], node_id: str = "", name: str = "") -> dict[str, Any] | None:
    for node in nodes:
        if node_id and str(node.get("node_id") or "") == node_id:
            return node
        if name and str(node.get("name") or "") == name:
            return node
    return None


def remove_node(nodes: list[dict[str, Any]], node_id: str = "", name: str = "") -> dict[str, Any] | None:
    for index, node in enumerate(nodes):
        if node_id and str(node.get("node_id") or "") == node_id:
            return nodes.pop(index)
        if name and str(node.get("name") or "") == name:
            return nodes.pop(index)
    return None


def merge_aliases(primary: dict[str, Any], secondary: dict[str, Any], plan: dict[str, Any]) -> None:
    aliases = list(primary.get("aliases") or [])
    secondary_name = str(secondary.get("name") or "")
    if secondary_name and secondary_name != primary.get("name") and secondary_name not in aliases:
        aliases.append(secondary_name)
    for alias in secondary.get("aliases") or []:
        alias = str(alias).strip()
        if alias and alias != primary.get("name") and alias not in aliases:
            aliases.append(alias)
    primary["aliases"] = aliases

    traces = list(primary.get("merged_from_nodes") or [])
    traces.append(
        {
            "source_node_id": secondary.get("node_id", ""),
            "source_name": secondary_name,
            "source_type": secondary.get("type", ""),
            "definition": secondary.get("definition", ""),
            "description": secondary.get("description", ""),
            "evidence_span": secondary.get("evidence_span", ""),
            "merge_plan_id": plan.get("merge_plan_id", ""),
            "basis": plan.get("basis", ""),
        }
    )
    primary["merged_from_nodes"] = traces
    primary["step8a_status"] = "merged_primary"
    primary["final_import_ready"] = True
    primary["step8a_generated_at"] = now_iso()


def refresh_edge_id(edge: dict[str, Any]) -> None:
    textbook_id = str(edge.get("textbook_id") or "unknown_textbook")
    edge["edge_id"] = stable_id(
        f"{textbook_id}:edge",
        [
            str(edge.get("source_node_id") or edge.get("source_name") or ""),
            str(edge.get("target_node_id") or edge.get("target_name") or ""),
            str(edge.get("type") or ""),
            str(edge.get("kg_layer") or ""),
        ],
    )


def redirect_edge(edge: dict[str, Any], old_id: str, old_name: str, primary: dict[str, Any], plan: dict[str, Any]) -> bool:
    changed = False
    primary_id = str(primary.get("node_id") or "")
    primary_name = str(primary.get("name") or "")
    primary_type = str(primary.get("type") or "")
    if (old_id and str(edge.get("source_node_id") or "") == old_id) or (old_name and str(edge.get("source_name") or "") == old_name):
        edge["source_node_id"] = primary_id
        edge["source_name"] = primary_name
        edge["source_type"] = primary_type
        changed = True
    if (old_id and str(edge.get("target_node_id") or "") == old_id) or (old_name and str(edge.get("target_name") or "") == old_name):
        edge["target_node_id"] = primary_id
        edge["target_name"] = primary_name
        edge["target_type"] = primary_type
        changed = True
    if changed:
        redirects = list(edge.get("step8a_endpoint_redirects") or [])
        redirects.append({"from_node_id": old_id, "from_name": old_name, "to_node_id": primary_id, "to_name": primary_name, "merge_plan_id": plan.get("merge_plan_id", "")})
        edge["step8a_endpoint_redirects"] = redirects
        edge["step8a_status"] = "endpoint_redirected_by_merge_plan"
        edge["step8a_generated_at"] = now_iso()
        refresh_edge_id(edge)
    return changed


def redirect_rule_case(rule_case: dict[str, Any], old_id: str, old_name: str, primary: dict[str, Any], plan: dict[str, Any]) -> bool:
    if not ((old_id and str(rule_case.get("owner_node_id") or "") == old_id) or (old_name and str(rule_case.get("owner_name") or "") == old_name)):
        return False
    redirects = list(rule_case.get("step8a_owner_redirects") or [])
    redirects.append({"from_node_id": old_id, "from_name": old_name, "to_node_id": primary.get("node_id", ""), "to_name": primary.get("name", ""), "merge_plan_id": plan.get("merge_plan_id", "")})
    rule_case["owner_node_id"] = primary.get("node_id", "")
    rule_case["owner_name"] = primary.get("name", "")
    rule_case["owner_type"] = primary.get("type", "")
    rule_case["step8a_owner_redirects"] = redirects
    rule_case["step8a_status"] = "owner_redirected_by_merge_plan"
    rule_case["step8a_generated_at"] = now_iso()
    if not rule_case.get("rule_case_id"):
        rule_case["rule_case_id"] = rule_case_identity(rule_case)
    return True


def prune_edges(edges: list[dict[str, Any]], archive: list[dict[str, Any]], plan: dict[str, Any]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for edge in edges:
        if edge.get("source_node_id") and edge.get("source_node_id") == edge.get("target_node_id"):
            row = dict(edge)
            row["archive_status"] = "step8a_removed_self_loop_after_merge"
            row["merge_plan_id"] = plan.get("merge_plan_id", "")
            archive.append(row)
            continue
        key = edge_identity(edge)
        if key in seen:
            row = dict(edge)
            row["archive_status"] = "step8a_removed_duplicate_edge_after_merge"
            row["merge_plan_id"] = plan.get("merge_plan_id", "")
            archive.append(row)
            continue
        seen.add(key)
        kept.append(edge)
    return kept


def prune_rule_cases(rule_cases: list[dict[str, Any]], archive: list[dict[str, Any]], plan: dict[str, Any]) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for rule_case in rule_cases:
        key = (str(rule_case.get("owner_node_id") or rule_case.get("owner_name") or ""), str(rule_case.get("case_name") or ""), str(rule_case.get("evidence_span") or ""))
        if key in seen:
            row = dict(rule_case)
            row["archive_status"] = "step8a_removed_duplicate_rule_case_after_merge"
            row["merge_plan_id"] = plan.get("merge_plan_id", "")
            archive.append(row)
            continue
        seen.add(key)
        kept.append(rule_case)
    return kept


def prune_edges_missing_endpoints(edges: list[dict[str, Any]], nodes: list[dict[str, Any]], archive: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    node_ids = {str(node.get("node_id") or "") for node in nodes if node.get("node_id")}
    kept: list[dict[str, Any]] = []
    for edge in edges:
        source_id = str(edge.get("source_node_id") or "")
        target_id = str(edge.get("target_node_id") or "")
        if source_id in node_ids and target_id in node_ids:
            kept.append(edge)
            continue
        row = dict(edge)
        row["archive_status"] = status
        row["missing_source_node"] = source_id not in node_ids
        row["missing_target_node"] = target_id not in node_ids
        archive.append(row)
    return kept


def prune_rule_cases_missing_owner(rule_cases: list[dict[str, Any]], nodes: list[dict[str, Any]], archive: list[dict[str, Any]]) -> list[dict[str, Any]]:
    node_ids = {str(node.get("node_id") or "") for node in nodes if node.get("node_id")}
    node_names = {str(node.get("name") or "") for node in nodes if node.get("name")}
    kept: list[dict[str, Any]] = []
    for rule_case in rule_cases:
        owner_id = str(rule_case.get("owner_node_id") or "")
        owner_name = str(rule_case.get("owner_name") or "")
        if (owner_id and owner_id in node_ids) or (owner_name and owner_name in node_names):
            kept.append(rule_case)
            continue
        row = dict(rule_case)
        row["archive_status"] = "step8a_rule_case_owner_missing"
        archive.append(row)
    return kept


def apply_merge_plan(plan: dict[str, Any], core_nodes: list[dict[str, Any]], app_nodes: list[dict[str, Any]], core_edges: list[dict[str, Any]], app_edges: list[dict[str, Any]], rule_cases: list[dict[str, Any]], archive: list[dict[str, Any]], traces: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    primary_id = str(plan.get("primary_node_id") or "")
    primary_name = str(plan.get("primary_name") or "")
    secondary_id = str(plan.get("secondary_node_id") or "")
    secondary_name = str(plan.get("secondary_name") or "")
    all_nodes = [*core_nodes, *app_nodes]
    primary = find_node(all_nodes, primary_id, primary_name)
    if not primary:
        plan_archive = dict(plan)
        plan_archive["archive_status"] = "step8a_merge_plan_primary_not_found"
        archive.append(plan_archive)
        traces.append({"merge_plan_id": plan.get("merge_plan_id", ""), "result": "defer", "note": "primary_not_found", "generated_at": now_iso()})
        return core_edges, app_edges, rule_cases

    secondary = find_node(all_nodes, secondary_id, secondary_name)
    secondary_trace = secondary or dict(plan.get("secondary_node") or {"node_id": secondary_id, "name": secondary_name, "type": plan.get("node_type", "")})
    if primary.get("type") and secondary_trace.get("type") and primary.get("type") != secondary_trace.get("type"):
        plan_archive = dict(plan)
        plan_archive["archive_status"] = "step8a_merge_plan_type_mismatch"
        archive.append(plan_archive)
        traces.append({"merge_plan_id": plan.get("merge_plan_id", ""), "result": "defer", "note": "type_mismatch", "generated_at": now_iso()})
        return core_edges, app_edges, rule_cases

    if secondary:
        removed = remove_node(core_nodes, secondary_id, secondary_name)
        if removed is None:
            removed = remove_node(app_nodes, secondary_id, secondary_name)
        secondary_trace = removed or secondary_trace
        archived_secondary = dict(secondary_trace)
        archived_secondary["archive_status"] = "step8a_merged_into_primary_node"
        archived_secondary["merged_into_node_id"] = primary.get("node_id", "")
        archived_secondary["merged_into_name"] = primary.get("name", "")
        archived_secondary["merge_plan_id"] = plan.get("merge_plan_id", "")
        archive.append(archived_secondary)

    merge_aliases(primary, secondary_trace, plan)
    old_id = str(secondary_trace.get("node_id") or secondary_id)
    old_name = str(secondary_trace.get("name") or secondary_name)
    for edge in [*core_edges, *app_edges]:
        redirect_edge(edge, old_id, old_name, primary, plan)
    for rule_case in rule_cases:
        redirect_rule_case(rule_case, old_id, old_name, primary, plan)

    core_edges = prune_edges(core_edges, archive, plan)
    app_edges = prune_edges(app_edges, archive, plan)
    rule_cases = prune_rule_cases(rule_cases, archive, plan)
    traces.append({"merge_plan_id": plan.get("merge_plan_id", ""), "result": "merged", "primary_node_id": primary.get("node_id", ""), "secondary_node_id": old_id, "generated_at": now_iso()})
    return core_edges, app_edges, rule_cases


def build_section_groups(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for node in nodes:
        section_node_id = str(node.get("section_node_id") or "").strip()
        if section_node_id:
            grouped.setdefault(section_node_id, []).append(node)
    groups: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for section_node_id, members in sorted(grouped.items()):
        first = members[0]
        group_id = stable_id(f"{first.get('textbook_id', '')}:group", [section_node_id, "SectionGroup"])
        group = ensure_source_code(
            {
                "group_id": group_id,
                "name": str(first.get("section") or first.get("subsection") or section_node_id),
                "type": "KnowledgeGroup",
                "group_type": "SectionGroup",
                "kg_layer": "knowledge_group",
                "textbook_id": first.get("textbook_id", ""),
                "textbook_name": first.get("textbook_name", ""),
                "chapter": first.get("chapter", ""),
                "section": first.get("section", ""),
                "subsection": first.get("subsection", ""),
                "section_node_id": section_node_id,
                "source_scope": first.get("source_scope", ""),
                "member_count": len(members),
                "creation_policy": "auto_by_section_node_id",
                "final_import_ready": True,
                "step8a_generated_at": now_iso(),
            }
        )
        groups.append(group)
        for member in members:
            member_id = str(member.get("node_id") or "")
            if not member_id:
                continue
            edges.append(
                ensure_source_code(
                    {
                        "edge_id": stable_id(f"{first.get('textbook_id', '')}:groupedge", [group_id, member_id, "HAS_MEMBER"]),
                        "type": "HAS_MEMBER",
                        "kg_layer": "knowledge_group",
                        "source_group_id": group_id,
                        "source_node_id": group_id,
                        "source_name": group["name"],
                        "source_type": "KnowledgeGroup",
                        "target_node_id": member_id,
                        "target_name": member.get("name", ""),
                        "target_type": member.get("type", ""),
                        "textbook_id": member.get("textbook_id", ""),
                        "textbook_name": member.get("textbook_name", ""),
                        "chapter": member.get("chapter", ""),
                        "section": member.get("section", ""),
                        "subsection": member.get("subsection", ""),
                        "section_node_id": member.get("section_node_id", ""),
                        "source_scope": member.get("source_scope", ""),
                        "description": "知识点属于该小节知识组。",
                        "evidence_span": member.get("evidence_span", ""),
                        "confidence": 1.0,
                        "final_import_ready": True,
                        "step8a_generated_at": now_iso(),
                    }
                )
            )
    return groups, edges


def build_rule_groups(rule_cases: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for rule_case in rule_cases:
        owner_id = str(rule_case.get("owner_node_id") or rule_case.get("owner_name") or "").strip()
        if owner_id:
            grouped.setdefault(owner_id, []).append(rule_case)
    groups: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for owner_id, cases in sorted(grouped.items()):
        first = cases[0]
        owner_name = str(first.get("owner_name") or owner_id)
        group_id = stable_id(f"{first.get('textbook_id', '')}:group", [owner_id, "RuleGroup"])
        group = ensure_source_code(
            {
                "group_id": group_id,
                "name": f"{owner_name}规则组",
                "type": "KnowledgeGroup",
                "group_type": "RuleGroup",
                "kg_layer": "knowledge_group",
                "textbook_id": first.get("textbook_id", ""),
                "textbook_name": first.get("textbook_name", ""),
                "chapter": first.get("chapter", ""),
                "section": first.get("section", ""),
                "subsection": first.get("subsection", ""),
                "section_node_id": first.get("section_node_id", ""),
                "source_scope": first.get("source_scope", ""),
                "member_count": len(cases),
                "anchor_node_id": first.get("owner_node_id", ""),
                "anchor_name": owner_name,
                "creation_policy": "auto_by_rule_case_owner",
                "final_import_ready": True,
                "step8a_generated_at": now_iso(),
            }
        )
        groups.append(group)
        if first.get("owner_node_id"):
            edges.append(
                ensure_source_code(
                    {
                        "edge_id": stable_id(f"{first.get('textbook_id', '')}:groupedge", [group_id, str(first.get("owner_node_id") or ""), "HAS_ANCHOR"]),
                        "type": "HAS_ANCHOR",
                        "kg_layer": "knowledge_group",
                        "source_group_id": group_id,
                        "source_node_id": group_id,
                        "source_name": group["name"],
                        "source_type": "KnowledgeGroup",
                        "target_node_id": first.get("owner_node_id", ""),
                        "target_name": owner_name,
                        "target_type": first.get("owner_type", ""),
                        "textbook_id": first.get("textbook_id", ""),
                        "textbook_name": first.get("textbook_name", ""),
                        "chapter": first.get("chapter", ""),
                        "section": first.get("section", ""),
                        "subsection": first.get("subsection", ""),
                        "section_node_id": first.get("section_node_id", ""),
                        "source_scope": first.get("source_scope", ""),
                        "description": "规则组的锚点知识节点。",
                        "evidence_span": first.get("evidence_span", ""),
                        "confidence": 1.0,
                        "final_import_ready": True,
                        "step8a_generated_at": now_iso(),
                    }
                )
            )
        for case in cases:
            case_id = str(case.get("rule_case_id") or "")
            if case_id:
                edges.append(
                    ensure_source_code(
                        {
                            "edge_id": stable_id(f"{first.get('textbook_id', '')}:groupedge", [group_id, case_id, "HAS_MEMBER"]),
                            "type": "HAS_MEMBER",
                            "kg_layer": "knowledge_group",
                            "source_group_id": group_id,
                            "source_node_id": group_id,
                            "source_name": group["name"],
                            "source_type": "KnowledgeGroup",
                            "target_node_id": case_id,
                            "target_name": case.get("case_name", ""),
                            "target_type": "RuleCase",
                            "textbook_id": case.get("textbook_id", ""),
                            "textbook_name": case.get("textbook_name", ""),
                            "chapter": case.get("chapter", ""),
                            "section": case.get("section", ""),
                            "subsection": case.get("subsection", ""),
                            "section_node_id": case.get("section_node_id", ""),
                            "source_scope": case.get("source_scope", ""),
                            "description": "规则案例属于该规则组。",
                            "evidence_span": case.get("evidence_span", ""),
                            "confidence": 1.0,
                            "final_import_ready": True,
                            "step8a_generated_at": now_iso(),
                        }
                    )
                )
    return groups, edges


def write_report(path: Path, core_nodes: list[dict[str, Any]], core_edges: list[dict[str, Any]], app_nodes: list[dict[str, Any]], app_edges: list[dict[str, Any]], rule_cases: list[dict[str, Any]], groups: list[dict[str, Any]], group_edges: list[dict[str, Any]], archive: list[dict[str, Any]], traces: list[dict[str, Any]]) -> None:
    node_types = Counter(str(row.get("type") or "") for row in [*core_nodes, *app_nodes])
    edge_types = Counter(str(row.get("type") or "") for row in [*core_edges, *app_edges])
    group_types = Counter(str(row.get("group_type") or "") for row in groups)
    lines = [
        "# v4.4 Step 8A Final Graph Assembly Report",
        "",
        f"- final_core_nodes: {len(core_nodes)}",
        f"- final_core_edges: {len(core_edges)}",
        f"- final_application_nodes: {len(app_nodes)}",
        f"- final_application_edges: {len(app_edges)}",
        f"- final_rule_cases: {len(rule_cases)}",
        f"- final_knowledge_groups: {len(groups)}",
        f"- final_knowledge_group_edges: {len(group_edges)}",
        f"- final_archived_items: {len(archive)}",
        f"- merge_trace_rows: {len(traces)}",
        "",
        "## Node Types",
    ]
    for key, value in sorted(node_types.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Edge Types"])
    for key, value in sorted(edge_types.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Knowledge Groups"])
    for key, value in sorted(group_types.items()):
        lines.append(f"- {key}: {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    core_nodes = read_jsonl(args.review_dir / "approved_nodes.jsonl", required=False)
    core_edges = read_jsonl(args.review_dir / "approved_edges.jsonl", required=False)
    app_nodes = read_jsonl(args.review_dir / "approved_application_nodes.jsonl", required=False)
    app_edges = read_jsonl(args.review_dir / "approved_application_edges.jsonl", required=False)
    rule_cases = read_jsonl(args.review_dir / "approved_rule_cases.jsonl", required=False)
    merge_plans = read_jsonl(args.review_dir / "merge_plans.jsonl", required=False)
    review_archive = read_jsonl(args.review_dir / "review_archive.jsonl", required=False)
    deferred = read_jsonl(args.review_dir / "deferred_items.jsonl", required=False)

    archive = list(review_archive)
    traces: list[dict[str, Any]] = []
    for plan in merge_plans:
        core_edges, app_edges, rule_cases = apply_merge_plan(plan, core_nodes, app_nodes, core_edges, app_edges, rule_cases, archive, traces)

    all_nodes = [*core_nodes, *app_nodes]
    core_edges = prune_edges_missing_endpoints(core_edges, all_nodes, archive, "step8a_core_edge_endpoint_missing")
    app_edges = prune_edges_missing_endpoints(app_edges, all_nodes, archive, "step8a_application_edge_endpoint_missing")
    rule_cases = prune_rule_cases_missing_owner(rule_cases, all_nodes, archive)

    final_groups: list[dict[str, Any]] = []
    final_group_edges: list[dict[str, Any]] = []
    section_groups, section_edges = build_section_groups([*core_nodes, *app_nodes])
    rule_groups, rule_edges = build_rule_groups(rule_cases)
    for group in [*section_groups, *rule_groups]:
        add_unique(final_groups, group, group_identity)
    for edge in [*section_edges, *rule_edges]:
        add_unique(final_group_edges, edge, group_edge_identity)

    for row in [*core_nodes, *app_nodes, *core_edges, *app_edges, *rule_cases, *final_groups, *final_group_edges]:
        row["final_import_ready"] = True
        row["step8a_generated_at"] = row.get("step8a_generated_at") or now_iso()
        ensure_source_code(row)

    write_jsonl(out_dir / "final_core_nodes.jsonl", core_nodes)
    write_jsonl(out_dir / "final_core_edges.jsonl", core_edges)
    write_jsonl(out_dir / "final_application_nodes.jsonl", app_nodes)
    write_jsonl(out_dir / "final_application_edges.jsonl", app_edges)
    write_jsonl(out_dir / "final_rule_cases.jsonl", rule_cases)
    write_jsonl(out_dir / "final_knowledge_groups.jsonl", final_groups)
    write_jsonl(out_dir / "final_knowledge_group_edges.jsonl", final_group_edges)
    write_jsonl(out_dir / "final_archived_items.jsonl", archive)
    write_jsonl(out_dir / "final_review_pending.jsonl", deferred)
    write_jsonl(out_dir / "merge_execution_trace.jsonl", traces)
    write_report(out_dir / "final_assembly_report.md", core_nodes, core_edges, app_nodes, app_edges, rule_cases, final_groups, final_group_edges, archive, traces)
    print(f"[OK] Step 8A final graph package -> {out_dir}")
    print(f"[INFO] core nodes/edges={len(core_nodes)}/{len(core_edges)} groups={len(final_groups)} merge_traces={len(traces)}")


if __name__ == "__main__":
    main()
