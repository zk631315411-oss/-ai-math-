"""
v4.4 Step 4E: full AI audit for Step 4 relation extraction quality.

Only edges and rule cases marked review by this audit should enter the Step 7
review path. Step 4A/4B validation warnings are pre-audit signals only.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_env import load_api_key, resolve_base_url, resolve_timeout


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODULE_DIR = SCRIPT_DIR.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "v4_4_gaoshu_config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "relation_quality_audit.md"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "中间产物"
DEFAULT_LEAF_SECTIONS = DEFAULT_OUTPUT_DIR / "leaf_sections.jsonl"
DEFAULT_NODES = DEFAULT_OUTPUT_DIR / "nodes_audited.jsonl"
DEFAULT_EDGES = DEFAULT_OUTPUT_DIR / "edges.jsonl"
DEFAULT_RULE_CASES = DEFAULT_OUTPUT_DIR / "rule_cases.jsonl"
DEFAULT_RAW_OUTPUT = DEFAULT_OUTPUT_DIR / "raw_relation_quality_audit.jsonl"
DEFAULT_AUDITED_EDGES = DEFAULT_OUTPUT_DIR / "edges_audited.jsonl"
DEFAULT_AUDITED_RULE_CASES = DEFAULT_OUTPUT_DIR / "rule_cases_audited.jsonl"
DEFAULT_EDGE_REVIEW = DEFAULT_OUTPUT_DIR / "edge_review_queue.jsonl"
DEFAULT_RULE_CASE_REVIEW = DEFAULT_OUTPUT_DIR / "rule_case_review_queue.jsonl"
DEFAULT_WARNINGS = DEFAULT_OUTPUT_DIR / "relation_quality_audit_warnings.jsonl"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "relation_quality_audit_report.md"
ENV_PATHS = [REPO_ROOT / ".env", MODULE_DIR / ".env"]

VALID_DECISIONS = {"accept", "review"}
HARD_EDGE_WARNING_PREFIXES = (
    "source_not_in_node_pool:",
    "target_not_in_node_pool:",
    "invalid_edge_type:",
    "forbidden_edge_type:",
    "example_forbidden_edge_type:",
    "uses_invalid_source_type:",
    "uses_invalid_target_type:",
    "uses_method_target_invalid_source_type:",
    "gets_invalid_source_type:",
    "gets_invalid_target_type:",
    "derives_invalid_source_type:",
    "derives_invalid_target_type:",
    "part_of_invalid_type_pair:",
    "evidence_span_not_in_section:",
    "empty_evidence_span:",
    "evidence_span_contains_ellipsis:",
    "weak_evidence_span:",
    "derives_naming_statement:",
    "equative_naming_statement:",
)
HARD_EDGE_WARNING_EXACT = {
    "self_loop",
    "missing_evidence_spans",
    "confidence_below_reject_threshold",
}
HARD_RULE_CASE_WARNING_PREFIXES = (
    "owner_not_in_node_pool:",
    "invalid_owner_type:",
)
HARD_RULE_CASE_WARNING_EXACT = {
    "missing_owner_node_id",
    "missing_case_name",
    "missing_conditions",
    "missing_outcomes",
    "missing_evidence_span",
    "evidence_span_not_in_section",
    "confidence_below_reject_threshold",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit v4.4 Step 4 edge and rule-case candidates.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--leaf-sections", type=Path, default=DEFAULT_LEAF_SECTIONS)
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--edges", type=Path, default=DEFAULT_EDGES)
    parser.add_argument("--rule-cases", type=Path, default=DEFAULT_RULE_CASES)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--audited-edges", type=Path, default=DEFAULT_AUDITED_EDGES)
    parser.add_argument("--audited-rule-cases", type=Path, default=DEFAULT_AUDITED_RULE_CASES)
    parser.add_argument("--edge-review", type=Path, default=DEFAULT_EDGE_REVIEW)
    parser.add_argument("--rule-case-review", type=Path, default=DEFAULT_RULE_CASE_REVIEW)
    parser.add_argument("--warnings", type=Path, default=DEFAULT_WARNINGS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--chunk-id", "--section-node-id", dest="section_node_id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--append", action="store_true")
    return parser.parse_args()


def read_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}. Run 00_prepare_config.py first.")
    return json.loads(path.read_text(encoding="utf-8"))


def load_env_value(key: str) -> str:
    for env_path in ENV_PATHS:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    return os.environ.get(key, "")


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


def open_output(path: Path, append: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a" if append else "w", encoding="utf-8", newline="\n")


def coerce_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def short(text: Any, limit: int = 900) -> str:
    value = str(text or "")
    return value if len(value) <= limit else value[:limit] + "..."


def item_id(row: dict[str, Any], kind: str) -> str:
    if kind == "edge":
        return str(row.get("edge_id") or row.get("candidate_id") or "")
    return str(row.get("rule_case_id") or row.get("candidate_id") or "")


def item_key(row: dict[str, Any], kind: str) -> tuple[str, str, str]:
    return (kind, item_id(row, kind), str(row.get("candidate_id") or ""))


def compact_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": node.get("node_id", ""),
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "review_status": node.get("review_status", ""),
        "source_label": node.get("source_label", ""),
        "section_node_id": node.get("section_node_id", ""),
    }


def compact_edge(edge: dict[str, Any], node_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    source = node_by_id.get(str(edge.get("source_node_id") or ""), {})
    target = node_by_id.get(str(edge.get("target_node_id") or ""), {})
    return {
        "item_kind": "edge",
        "item_id": item_id(edge, "edge"),
        "candidate_id": edge.get("candidate_id", ""),
        "source_node": compact_node(source) if source else {
            "node_id": edge.get("source_node_id", ""),
            "name": edge.get("source_name", ""),
            "type": edge.get("source_type", ""),
            "review_status": edge.get("source_review_status", ""),
        },
        "target_node": compact_node(target) if target else {
            "node_id": edge.get("target_node_id", ""),
            "name": edge.get("target_name", ""),
            "type": edge.get("target_type", ""),
            "review_status": edge.get("target_review_status", ""),
        },
        "type": edge.get("type", ""),
        "description": edge.get("description", ""),
        "evidence_span": short(edge.get("evidence_span", ""), 1200),
        "confidence": edge.get("confidence", 0),
        "pre_audit_review_status": edge.get("review_status", ""),
        "pre_audit_review_reason": edge.get("review_reason", ""),
        "validation_warnings": edge.get("validation_warnings", []),
    }


def compact_rule_case(case: dict[str, Any], node_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    owner = node_by_id.get(str(case.get("owner_node_id") or ""), {})
    return {
        "item_kind": "rule_case",
        "item_id": item_id(case, "rule_case"),
        "candidate_id": case.get("candidate_id", ""),
        "owner_node": compact_node(owner) if owner else {
            "node_id": case.get("owner_node_id", ""),
            "name": case.get("owner_name", ""),
            "type": case.get("owner_type", ""),
            "review_status": case.get("owner_review_status", ""),
        },
        "case_name": case.get("case_name", ""),
        "applies_to": case.get("applies_to", ""),
        "conditions": case.get("conditions", []),
        "condition_logic": case.get("condition_logic", ""),
        "outcomes": case.get("outcomes", []),
        "formula_refs": case.get("formula_refs", []),
        "evidence_span": short(case.get("evidence_span", ""), 1200),
        "confidence": case.get("confidence", 0),
        "pre_audit_review_status": case.get("review_status", ""),
        "pre_audit_review_reason": case.get("review_reason", ""),
        "validation_warnings": case.get("validation_warnings", []),
    }


def select_items(rows: list[dict[str, Any]], section_id: str, limit: int) -> list[dict[str, Any]]:
    selected = rows
    if section_id:
        selected = [row for row in selected if row.get("section_node_id") == section_id]
    if limit > 0:
        selected = selected[:limit]
    return selected


def make_work_items(edges: list[dict[str, Any]], rule_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items = [{"kind": "edge", "row": edge} for edge in edges]
    items.extend({"kind": "rule_case", "row": case} for case in rule_cases)
    return sorted(items, key=lambda item: (
        str(item["row"].get("section_node_id") or ""),
        0 if item["kind"] == "edge" else 1,
        str(item["row"].get("candidate_id") or item_id(item["row"], item["kind"])),
    ))


def batched_by_section(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current_section = None
    current: list[dict[str, Any]] = []
    for item in items:
        section_id = item["row"].get("section_node_id")
        if current and (section_id != current_section or len(current) >= batch_size):
            batches.append(current)
            current = []
        current_section = section_id
        current.append(item)
    if current:
        batches.append(current)
    return batches


def build_payload(
    batch: list[dict[str, Any]],
    section_by_id: dict[str, dict[str, Any]],
    node_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    section_id = str(batch[0]["row"].get("section_node_id") or "") if batch else ""
    section = section_by_id.get(section_id, {})
    edges = [compact_edge(item["row"], node_by_id) for item in batch if item["kind"] == "edge"]
    rule_cases = [compact_rule_case(item["row"], node_by_id) for item in batch if item["kind"] == "rule_case"]
    return {
        "section_metadata": {
            "section_node_id": section.get("section_node_id", section_id),
            "textbook_id": section.get("textbook_id", ""),
            "textbook_name": section.get("textbook_name", ""),
            "chapter": section.get("chapter", ""),
            "section": section.get("section", ""),
            "subsection": section.get("subsection", ""),
            "source_scope": section.get("source_scope", ""),
            "line_start": section.get("line_start", 0),
            "line_end": section.get("line_end", 0),
        },
        "section_text": short(section.get("text", ""), 9000),
        "edges": edges,
        "rule_cases": rule_cases,
    }


def parse_llm_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError as first_exc:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
        raise RuntimeError(f"LLM returned invalid JSON: {first_exc}; content_prefix={content[:1000]}") from first_exc


def call_llm(
    api_key: str,
    base_url: str,
    model: str,
    prompt: str,
    payload: dict[str, Any],
    temperature: float,
    timeout: float,
) -> dict[str, Any]:
    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你只输出合法 JSON，不输出 Markdown 或解释。"},
            {"role": "user", "content": prompt + "\n\n## 当前输入\n\n" + json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(request_body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url=base_url.rstrip("/") + "/chat/completions",
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    last_error: RuntimeError | None = None
    max_attempts = 5
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_body = json.loads(response.read().decode("utf-8"))
            content = response_body.get("choices", [{}])[0].get("message", {}).get("content") or "{}"
            return parse_llm_json(content)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 or 500 <= exc.code < 600:
                last_error = RuntimeError(f"LLM HTTP {exc.code}: {body[:1000]}")
            else:
                raise RuntimeError(f"LLM HTTP {exc.code}: {body[:1000]}") from exc
        except (ConnectionResetError, TimeoutError, socket.timeout, http.client.HTTPException) as exc:
            last_error = RuntimeError(f"LLM connection failed: {exc}")
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"LLM request failed: {exc}")
        except RuntimeError as exc:
            last_error = exc
        if attempt < max_attempts:
            sleep_seconds = 10 * attempt if "HTTP 429" in str(last_error) else 1.5 * attempt
            time.sleep(sleep_seconds)
    assert last_error is not None
    raise last_error


def mock_audit(batch: list[dict[str, Any]]) -> dict[str, Any]:
    decisions = []
    for item in batch:
        row = item["row"]
        warnings = row.get("validation_warnings") or []
        endpoint_or_owner_pending = (
            "edge_touches_review_node" in warnings
            or "rule_case_owner_review_node" in warnings
        )
        hard_issue = any(str(w).startswith(("invalid_", "missing_", "evidence_span_not_in_section")) for w in warnings)
        decision = "review" if endpoint_or_owner_pending or hard_issue else "accept"
        decisions.append({
            "item_kind": item["kind"],
            "item_id": item_id(row, item["kind"]),
            "candidate_id": row.get("candidate_id", ""),
            "decision": decision,
            "basis": "mock audit based on endpoint/owner status and hard warnings",
            "issues": warnings if decision == "review" else [],
            "suggested_fix": "",
            "review_reason": "mock 发现待审端点/owner 或硬性 warning，需 Step 7 复核。" if decision == "review" else "",
            "confidence": 0.5,
        })
    return {"decisions": decisions}


def normalize_decision(raw: dict[str, Any]) -> dict[str, Any]:
    kind = str(raw.get("item_kind") or "").strip()
    if kind not in {"edge", "rule_case"}:
        kind = ""
    decision = str(raw.get("decision") or "").strip().lower()
    if decision not in VALID_DECISIONS:
        decision = "review"
    issues = raw.get("issues") if isinstance(raw.get("issues"), list) else []
    return {
        "item_kind": kind,
        "item_id": str(raw.get("item_id") or ""),
        "candidate_id": str(raw.get("candidate_id") or ""),
        "decision": decision,
        "basis": str(raw.get("basis") or "").strip(),
        "issues": [str(issue).strip() for issue in issues if str(issue).strip()],
        "suggested_fix": str(raw.get("suggested_fix") or "").strip(),
        "review_reason": str(raw.get("review_reason") or "").strip(),
        "confidence": coerce_confidence(raw.get("confidence", 0)),
    }


def hard_schema_warnings(row: dict[str, Any], kind: str) -> list[str]:
    warnings = [str(w) for w in (row.get("validation_warnings") or [])]
    if kind == "edge":
        prefixes = HARD_EDGE_WARNING_PREFIXES
        exact = HARD_EDGE_WARNING_EXACT
    else:
        prefixes = HARD_RULE_CASE_WARNING_PREFIXES
        exact = HARD_RULE_CASE_WARNING_EXACT
    return [
        warning
        for warning in warnings
        if warning in exact or any(warning.startswith(prefix) for prefix in prefixes)
    ]


def audit_row(row: dict[str, Any], kind: str, decision: dict[str, Any], model: str, mode: str) -> dict[str, Any]:
    audited = dict(row)
    original_status = str(row.get("review_status") or "")
    hard_warnings = hard_schema_warnings(row, kind)
    effective_decision = dict(decision)
    if hard_warnings and effective_decision["decision"] == "accept":
        effective_decision["decision"] = "review"
        effective_decision["review_reason"] = "本地硬 schema warning 不允许被 AI 直接升级为 auto_accept，需 Step 7 复核。"
        effective_decision["basis"] = (
            (effective_decision.get("basis") or "").strip()
            + "；本地硬 schema 闸门覆盖 AI accept。"
        ).strip("；")
        issues = list(effective_decision.get("issues") or [])
        for warning in hard_warnings:
            if warning not in issues:
                issues.append(warning)
        effective_decision["issues"] = issues
        audited["relation_audit_guard_overridden"] = True
        audited["relation_audit_guard_reason"] = "本地硬 schema warning 不允许被 AI 直接升级为 auto_accept。"
        audited["relation_audit_guard_warnings"] = hard_warnings
    else:
        audited["relation_audit_guard_overridden"] = False
        audited["relation_audit_guard_warnings"] = hard_warnings
    audited["pre_audit_review_status"] = original_status
    audited["pre_audit_review_reason"] = row.get("review_reason", "")
    audited["relation_audit_model"] = model
    audited["relation_audit_mode"] = mode
    audited["relation_audit_raw_decision"] = decision["decision"]
    audited["relation_audit_decision"] = effective_decision["decision"]
    audited["relation_audit_basis"] = effective_decision["basis"]
    audited["relation_audit_issues"] = effective_decision["issues"]
    audited["relation_audit_suggested_fix"] = effective_decision["suggested_fix"]
    audited["relation_audit_confidence"] = effective_decision["confidence"]
    audited["relation_audit_generated_at"] = datetime.now().isoformat(timespec="seconds")
    if effective_decision["decision"] == "accept":
        audited["review_status"] = "auto_accept"
        audited["review_recommended"] = False
        audited["review_reason"] = ""
    else:
        audited["review_status"] = "review"
        audited["review_recommended"] = True
        default_reason = "Step 4E 关系质量复核建议进入 Step 7。"
        if kind == "rule_case":
            default_reason = "Step 4E 规则案例质量复核建议进入 Step 7。"
        audited["review_reason"] = effective_decision["review_reason"] or effective_decision["basis"] or default_reason
    return audited


def write_report(
    path: Path,
    audited_edges: int,
    audited_rule_cases: int,
    status_counts: Counter[str],
    issue_counts: Counter[str],
) -> None:
    lines = [
        "# v4.4 Step 4E Relation Quality Audit Report",
        "",
        f"- audited edges: {audited_edges}",
        f"- audited rule cases: {audited_rule_cases}",
        "",
        "## Audit Decisions",
    ]
    for key, value in sorted(status_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Issues"])
    if issue_counts:
        for key, value in issue_counts.most_common(30):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = read_config(args.config)
    nodes = read_jsonl(args.nodes)
    node_by_id = {str(node.get("node_id") or ""): node for node in nodes if node.get("node_id")}
    edges = select_items(read_jsonl(args.edges, required=False), args.section_node_id, args.limit)
    rule_cases = select_items(read_jsonl(args.rule_cases, required=False), args.section_node_id, args.limit)
    items = make_work_items(edges, rule_cases)
    if args.section_node_id and not items:
        raise ValueError(f"section_node_id not found in edge/rule-case candidates: {args.section_node_id}")
    sections = read_jsonl(args.leaf_sections, required=False)
    section_by_id = {str(section.get("section_node_id") or ""): section for section in sections}
    prompt = args.prompt.read_text(encoding="utf-8")
    llm_config = config.get("llm", {})
    model = args.model or llm_config.get("relation_audit_model") or llm_config.get("review_model") or llm_config.get("high_risk_model", "GPT-5.5")
    base_url = resolve_base_url(args.base_url, llm_config)
    temperature = args.temperature if args.temperature is not None else float(llm_config.get("temperature", 0.0))
    timeout = resolve_timeout(args.timeout, llm_config)

    api_key = ""
    if not args.mock:
        api_key = load_api_key(llm_config)
        if not api_key:
            raise RuntimeError("API key not found. Set OPENAI_API_KEY or LLM_API_KEY, or use --mock for local validation.")

    print(
        f"[INFO] edges={len(edges)} rule_cases={len(rule_cases)} "
        f"batch_size={args.batch_size} model={model} mock={args.mock}"
    )
    status_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    audited_edges = 0
    audited_rule_cases = 0

    with (
        open_output(args.raw_output, args.append) as raw_f,
        open_output(args.audited_edges, args.append) as edges_f,
        open_output(args.audited_rule_cases, args.append) as rule_cases_f,
        open_output(args.edge_review, args.append) as edge_review_f,
        open_output(args.rule_case_review, args.append) as rule_review_f,
        open_output(args.warnings, args.append) as warn_f,
    ):
        for batch_index, batch in enumerate(batched_by_section(items, max(1, args.batch_size)), start=1):
            payload = build_payload(batch, section_by_id, node_by_id)
            section_id = payload["section_metadata"]["section_node_id"]
            if args.mock:
                raw = mock_audit(batch)
                elapsed = 0.0
                mode = "mock"
            else:
                started = time.time()
                raw = call_llm(api_key, base_url, model, prompt, payload, temperature, timeout)
                elapsed = time.time() - started
                mode = "llm"

            raw_f.write(json.dumps({
                "batch_index": batch_index,
                "section_node_id": section_id,
                "raw": raw,
                "edge_count": len(payload["edges"]),
                "rule_case_count": len(payload["rule_cases"]),
                "model": model,
                "mode": mode,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }, ensure_ascii=False) + "\n")

            decisions = raw.get("decisions") if isinstance(raw.get("decisions"), list) else []
            decision_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
            for raw_decision in decisions:
                if not isinstance(raw_decision, dict):
                    continue
                decision = normalize_decision(raw_decision)
                if not decision["item_kind"]:
                    continue
                decision_by_key[(decision["item_kind"], decision["item_id"], decision["candidate_id"])] = decision

            for item in batch:
                kind = item["kind"]
                row = item["row"]
                key = item_key(row, kind)
                decision = decision_by_key.get(key)
                if not decision:
                    decision = {
                        "item_kind": kind,
                        "item_id": key[1],
                        "candidate_id": key[2],
                        "decision": "review",
                        "basis": "Step 4E 复核未返回该候选的决策。",
                        "issues": ["missing_audit_decision"],
                        "suggested_fix": "",
                        "review_reason": "Step 4E 复核缺失，需 Step 7 复核。",
                        "confidence": 0.0,
                    }
                    warn_f.write(json.dumps({
                        "section_node_id": section_id,
                        "item_kind": kind,
                        "item_id": key[1],
                        "candidate_id": key[2],
                        "warnings": ["missing_audit_decision"],
                    }, ensure_ascii=False) + "\n")
                audited = audit_row(row, kind, decision, model, mode)
                if kind == "edge":
                    edges_f.write(json.dumps(audited, ensure_ascii=False) + "\n")
                    audited_edges += 1
                    if audited["review_status"] == "review":
                        edge_review_f.write(json.dumps(audited, ensure_ascii=False) + "\n")
                else:
                    rule_cases_f.write(json.dumps(audited, ensure_ascii=False) + "\n")
                    audited_rule_cases += 1
                    if audited["review_status"] == "review":
                        rule_review_f.write(json.dumps(audited, ensure_ascii=False) + "\n")
                status_counts[f"{kind}:{audited['review_status']}"] += 1
                for issue in audited.get("relation_audit_issues") or []:
                    issue_counts[str(issue)] += 1

            print(
                f"[OK] batch={batch_index} section={section_id} mode={mode} "
                f"elapsed={elapsed:.1f}s edges={len(payload['edges'])} rule_cases={len(payload['rule_cases'])}"
            )

    write_report(args.report, audited_edges, audited_rule_cases, status_counts, issue_counts)
    print(f"[OK] audited edges -> {args.audited_edges}")
    print(f"[OK] audited rule cases -> {args.audited_rule_cases}")
    print(f"[OK] edge review queue -> {args.edge_review}")
    print(f"[OK] rule-case review queue -> {args.rule_case_review}")
    print(f"[OK] report -> {args.report}")


if __name__ == "__main__":
    main()


