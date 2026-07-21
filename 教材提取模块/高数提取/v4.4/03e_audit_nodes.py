"""
v4.4 Step 3E: full AI audit for Step 3 node extraction quality.

Only nodes marked review by this audit should enter the Step 7 review path.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_env import load_api_key, resolve_base_url, resolve_timeout


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODULE_DIR = SCRIPT_DIR.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "v4_4_gaoshu_config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "node_quality_audit.md"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "中间产物"
DEFAULT_LEAF_SECTIONS = DEFAULT_OUTPUT_DIR / "leaf_sections.jsonl"
DEFAULT_NODES = DEFAULT_OUTPUT_DIR / "nodes.jsonl"
DEFAULT_RAW_OUTPUT = DEFAULT_OUTPUT_DIR / "raw_node_quality_audit.jsonl"
DEFAULT_AUDITED_NODES = DEFAULT_OUTPUT_DIR / "nodes_audited.jsonl"
DEFAULT_REVIEW = DEFAULT_OUTPUT_DIR / "node_review_queue.jsonl"
DEFAULT_WARNINGS = DEFAULT_OUTPUT_DIR / "node_quality_audit_warnings.jsonl"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "node_quality_audit_report.md"
ENV_PATHS = [REPO_ROOT / ".env", MODULE_DIR / ".env"]

VALID_DECISIONS = {"accept", "review"}
HARD_SCHEMA_WARNING_PREFIXES = (
    "invalid_node_type:",
    "forbidden_node_type:",
    "example_forbidden_node_type:",
    "rule_cases_invalid_node_type:",
)
HARD_SCHEMA_WARNING_EXACT = {
    "missing_name",
    "numbered_name",
    "missing_evidence_span",
    "evidence_span_not_in_section",
    "rule_cases_invalid_node_type",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit v4.4 Step 3 node candidates.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--leaf-sections", type=Path, default=DEFAULT_LEAF_SECTIONS)
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--audited-nodes", type=Path, default=DEFAULT_AUDITED_NODES)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--warnings", type=Path, default=DEFAULT_WARNINGS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--chunk-id", "--section-node-id", dest="section_node_id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=12)
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


def short(text: str, limit: int = 900) -> str:
    text = str(text or "")
    return text if len(text) <= limit else text[:limit] + "..."


def compact_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": node.get("candidate_id", ""),
        "node_id": node.get("node_id", ""),
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "aliases": node.get("aliases", []),
        "source_label": node.get("source_label", ""),
        "definition": short(node.get("definition", ""), 700),
        "description": node.get("description", ""),
        "attributes": node.get("attributes", []),
        "state_notes": node.get("state_notes", []),
        "evidence_span": short(node.get("evidence_span", ""), 900),
        "confidence": node.get("confidence", 0),
        "reason": node.get("reason", ""),
        "review_status_before_audit": node.get("review_status", ""),
        "review_reason_before_audit": node.get("review_reason", ""),
        "validation_warnings": node.get("validation_warnings", []),
        "span_repairs": node.get("span_repairs", []),
        "source_scope": node.get("source_scope", ""),
        "section_node_id": node.get("section_node_id", ""),
    }


def select_nodes(nodes: list[dict[str, Any]], args: argparse.Namespace) -> list[dict[str, Any]]:
    selected = nodes
    if args.section_node_id:
        selected = [node for node in selected if node.get("section_node_id") == args.section_node_id]
        if not selected:
            raise ValueError(f"section_node_id not found in nodes: {args.section_node_id}")
    if args.limit > 0:
        selected = selected[: args.limit]
    return selected


def batched_by_section(nodes: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    current_section = None
    current: list[dict[str, Any]] = []
    for node in nodes:
        section_id = node.get("section_node_id")
        if current and (section_id != current_section or len(current) >= batch_size):
            batches.append(current)
            current = []
        current_section = section_id
        current.append(node)
    if current:
        batches.append(current)
    return batches


def build_payload(batch: list[dict[str, Any]], section_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    section_id = str(batch[0].get("section_node_id") or "") if batch else ""
    section = section_by_id.get(section_id, {})
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
        "nodes": [compact_node(node) for node in batch],
    }


def parse_llm_json(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError as first_exc:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            import re
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
    for node in batch:
        warnings = node.get("validation_warnings") or []
        obvious_schema_issue = any(
            str(w).startswith(("invalid_node_type:", "forbidden_node_type:", "example_forbidden_node_type:"))
            or w in {"missing_name", "numbered_name", "missing_evidence_span", "evidence_span_not_in_section"}
            for w in warnings
        )
        decision = "review" if obvious_schema_issue else "accept"
        decisions.append({
            "node_id": node.get("node_id", ""),
            "candidate_id": node.get("candidate_id", ""),
            "decision": decision,
            "basis": "mock audit based on hard schema warnings",
            "issues": warnings if decision == "review" else [],
            "suggested_fix": "",
            "review_reason": "mock 发现硬性 schema 问题，需 Step 7 复核。" if decision == "review" else "",
            "confidence": 0.5,
        })
    return {"decisions": decisions}


def normalize_decision(raw: dict[str, Any]) -> dict[str, Any]:
    decision = str(raw.get("decision") or "").strip().lower()
    if decision not in VALID_DECISIONS:
        decision = "review"
    issues = raw.get("issues") if isinstance(raw.get("issues"), list) else []
    return {
        "node_id": str(raw.get("node_id") or ""),
        "candidate_id": str(raw.get("candidate_id") or ""),
        "decision": decision,
        "basis": str(raw.get("basis") or "").strip(),
        "issues": [str(issue).strip() for issue in issues if str(issue).strip()],
        "suggested_fix": str(raw.get("suggested_fix") or "").strip(),
        "review_reason": str(raw.get("review_reason") or "").strip(),
        "confidence": coerce_confidence(raw.get("confidence", 0)),
    }


def hard_schema_warnings(node: dict[str, Any]) -> list[str]:
    warnings = [str(w) for w in (node.get("validation_warnings") or [])]
    return [
        warning
        for warning in warnings
        if warning in HARD_SCHEMA_WARNING_EXACT
        or any(warning.startswith(prefix) for prefix in HARD_SCHEMA_WARNING_PREFIXES)
    ]


def audit_node(node: dict[str, Any], decision: dict[str, Any], model: str, mode: str) -> dict[str, Any]:
    audited = dict(node)
    original_status = str(node.get("review_status") or "")
    hard_warnings = hard_schema_warnings(node)
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
        audited["audit_guard_overridden"] = True
        audited["audit_guard_reason"] = "本地硬 schema warning 不允许被 AI 直接升级为 auto_accept。"
        audited["audit_guard_warnings"] = hard_warnings
    else:
        audited["audit_guard_overridden"] = False
        audited["audit_guard_warnings"] = hard_warnings
    audited["pre_audit_review_status"] = original_status
    audited["pre_audit_review_reason"] = node.get("review_reason", "")
    audited["audit_model"] = model
    audited["audit_mode"] = mode
    audited["audit_raw_decision"] = decision["decision"]
    audited["audit_decision"] = effective_decision["decision"]
    audited["audit_basis"] = effective_decision["basis"]
    audited["audit_issues"] = effective_decision["issues"]
    audited["audit_suggested_fix"] = effective_decision["suggested_fix"]
    audited["audit_confidence"] = effective_decision["confidence"]
    audited["audit_generated_at"] = datetime.now().isoformat(timespec="seconds")
    if effective_decision["decision"] == "accept":
        audited["review_status"] = "auto_accept"
        audited["review_recommended"] = False
        audited["review_reason"] = ""
    else:
        audited["review_status"] = "review"
        audited["review_recommended"] = True
        audited["review_reason"] = effective_decision["review_reason"] or effective_decision["basis"] or "Step 3E 节点质量复核建议进入 Step 7。"
    return audited


def write_report(path: Path, total_nodes: int, status_counts: Counter[str], issue_counts: Counter[str]) -> None:
    lines = [
        "# v4.4 Step 3E Node Quality Audit Report",
        "",
        f"- audited nodes: {total_nodes}",
        "",
        "## Audit Decisions",
    ]
    for key, value in sorted(status_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Top Issues"])
    if issue_counts:
        for key, value in issue_counts.most_common(20):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = read_config(args.config)
    nodes = select_nodes(read_jsonl(args.nodes), args)
    sections = read_jsonl(args.leaf_sections, required=False)
    section_by_id = {str(section.get("section_node_id") or ""): section for section in sections}
    prompt = args.prompt.read_text(encoding="utf-8")
    llm_config = config.get("llm", {})
    model = args.model or llm_config.get("node_audit_model") or llm_config.get("review_model") or llm_config.get("high_risk_model", "GPT-5.5")
    base_url = resolve_base_url(args.base_url, llm_config)
    temperature = args.temperature if args.temperature is not None else float(llm_config.get("temperature", 0.0))
    timeout = resolve_timeout(args.timeout, llm_config)

    api_key = ""
    if not args.mock:
        api_key = load_api_key(llm_config)
        if not api_key:
            raise RuntimeError("API key not found. Set OPENAI_API_KEY or LLM_API_KEY, or use --mock for local validation.")

    print(f"[INFO] nodes={len(nodes)} batch_size={args.batch_size} model={model} mock={args.mock}")
    status_counts: Counter[str] = Counter()
    issue_counts: Counter[str] = Counter()
    total = 0

    with (
        open_output(args.raw_output, args.append) as raw_f,
        open_output(args.audited_nodes, args.append) as audited_f,
        open_output(args.review, args.append) as review_f,
        open_output(args.warnings, args.append) as warn_f,
    ):
        for batch_index, batch in enumerate(batched_by_section(nodes, max(1, args.batch_size)), start=1):
            payload = build_payload(batch, section_by_id)
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
                "node_count": len(batch),
                "model": model,
                "mode": mode,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }, ensure_ascii=False) + "\n")

            decisions = raw.get("decisions") if isinstance(raw.get("decisions"), list) else []
            decision_by_key: dict[tuple[str, str], dict[str, Any]] = {}
            for raw_decision in decisions:
                if not isinstance(raw_decision, dict):
                    continue
                decision = normalize_decision(raw_decision)
                decision_by_key[(decision["node_id"], decision["candidate_id"])] = decision

            for node in batch:
                key = (str(node.get("node_id") or ""), str(node.get("candidate_id") or ""))
                decision = decision_by_key.get(key)
                if not decision:
                    decision = {
                        "node_id": key[0],
                        "candidate_id": key[1],
                        "decision": "review",
                        "basis": "Step 3E 复核未返回该节点的决策。",
                        "issues": ["missing_audit_decision"],
                        "suggested_fix": "",
                        "review_reason": "Step 3E 复核缺失，需 Step 7 复核。",
                        "confidence": 0.0,
                    }
                    warn_f.write(json.dumps({
                        "section_node_id": section_id,
                        "node_id": key[0],
                        "candidate_id": key[1],
                        "warnings": ["missing_audit_decision"],
                    }, ensure_ascii=False) + "\n")
                audited = audit_node(node, decision, model, mode)
                audited_f.write(json.dumps(audited, ensure_ascii=False) + "\n")
                if audited["review_status"] == "review":
                    review_f.write(json.dumps(audited, ensure_ascii=False) + "\n")
                status_counts[audited["review_status"]] += 1
                for issue in audited.get("audit_issues") or []:
                    issue_counts[str(issue)] += 1
                total += 1

            print(f"[OK] batch={batch_index} section={section_id} mode={mode} elapsed={elapsed:.1f}s nodes={len(batch)}")

    write_report(args.report, total, status_counts, issue_counts)
    print(f"[OK] audited nodes -> {args.audited_nodes}")
    print(f"[OK] review queue -> {args.review}")
    print(f"[OK] report -> {args.report}")


if __name__ == "__main__":
    main()


