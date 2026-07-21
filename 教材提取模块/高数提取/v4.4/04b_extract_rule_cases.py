"""
v4.4 Step 4B: extract conditional rule cases from audited nodes.

This step handles "if/when/iff/piecewise" mathematical rules. It does not
produce ordinary binary edges; Step 4A owns ordinary edge extraction.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_env import load_api_key, resolve_base_url, resolve_timeout


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODULE_DIR = SCRIPT_DIR.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "v4_4_gaoshu_config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "rule_case_extraction.md"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "中间产物"
DEFAULT_LEAF_SECTIONS = DEFAULT_OUTPUT_DIR / "leaf_sections.jsonl"
DEFAULT_NODES = DEFAULT_OUTPUT_DIR / "nodes_audited.jsonl"
DEFAULT_RAW_OUTPUT = DEFAULT_OUTPUT_DIR / "raw_rule_case_candidates.jsonl"
DEFAULT_RULE_CASES = DEFAULT_OUTPUT_DIR / "rule_cases.jsonl"
DEFAULT_REVIEW = DEFAULT_OUTPUT_DIR / "rule_case_pre_audit_review_queue.jsonl"
DEFAULT_WARNINGS = DEFAULT_OUTPUT_DIR / "rule_case_extraction_warnings.jsonl"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "rule_case_extraction_report.md"
ENV_PATHS = [REPO_ROOT / ".env", MODULE_DIR / ".env"]

OWNER_TYPES = {"Concept", "Theorem", "Formula", "Method"}
VALID_LOGIC = {"AND", "OR", "IFF", "PIECEWISE", "UNKNOWN"}
HARD_VALIDATION_PREFIXES = ("owner_not_in_node_pool:", "invalid_owner_type:")
HARD_VALIDATION_EXACT = {
    "missing_owner_node_id",
    "missing_case_name",
    "missing_conditions",
    "missing_outcomes",
    "missing_evidence_span",
    "evidence_span_not_in_section",
    "confidence_below_reject_threshold",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract v4.4 conditional rule cases.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--leaf-sections", type=Path, default=DEFAULT_LEAF_SECTIONS)
    parser.add_argument("--nodes", type=Path, default=DEFAULT_NODES)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--raw-output", type=Path, default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--rule-cases", type=Path, default=DEFAULT_RULE_CASES)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW, help="Pre-audit queue from Step 4B validation; Step 4E writes the final rule_case_review_queue.jsonl.")
    parser.add_argument("--warnings", type=Path, default=DEFAULT_WARNINGS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--chunk-id", "--section-node-id", dest="section_node_id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--max-node-pool", type=int, default=48)
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"JSONL not found: {path}")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def open_output(path: Path, append: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a" if append else "w", encoding="utf-8", newline="\n")


def clean_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def coerce_confidence(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, number))


def chunk_order_from_id(section_node_id: str) -> tuple[int, int, int]:
    match = re.search(r":C(\d+):S(\d+):U(\d+)$", str(section_node_id or ""))
    if not match:
        return (0, 0, 0)
    return tuple(int(part) for part in match.groups())


def section_sort_key(section: dict[str, Any]) -> tuple[int, int, int, str]:
    return (*chunk_order_from_id(str(section.get("section_node_id") or "")), str(section.get("section_node_id") or ""))


def node_visible_for_section(node: dict[str, Any], section: dict[str, Any]) -> bool:
    return chunk_order_from_id(str(node.get("section_node_id") or "")) <= chunk_order_from_id(str(section.get("section_node_id") or ""))


def node_current_section(node: dict[str, Any], section: dict[str, Any]) -> bool:
    return str(node.get("section_node_id") or "") == str(section.get("section_node_id") or "")


def compact_node(node: dict[str, Any]) -> dict[str, Any]:
    evidence = str(node.get("evidence_span") or "")
    return {
        "node_id": node.get("node_id", ""),
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "aliases": node.get("aliases", []),
        "source_label": node.get("source_label", ""),
        "description": node.get("description", ""),
        "evidence_preview": evidence[:260],
        "review_status": node.get("review_status", ""),
        "section_node_id": node.get("section_node_id", ""),
    }


def build_node_pool(section: dict[str, Any], nodes: list[dict[str, Any]], max_nodes: int) -> list[dict[str, Any]]:
    current = [
        node for node in nodes
        if node_current_section(node, section)
        and node.get("type") in OWNER_TYPES
    ]
    previous = [
        node for node in nodes
        if not node_current_section(node, section)
        and node_visible_for_section(node, section)
        and node.get("type") in OWNER_TYPES
    ]
    seen: set[str] = set()
    pool: list[dict[str, Any]] = []
    ordered = [*current, *previous]
    for node in ordered:
        node_id = str(node.get("node_id") or "")
        if node_id and node_id not in seen:
            seen.add(node_id)
            pool.append(node)
        if len(pool) >= max_nodes and not node_current_section(node, section):
            break
    return pool


def select_sections(sections: list[dict[str, Any]], config: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    sections = sorted(sections, key=section_sort_key)
    if args.section_node_id:
        selected = [section for section in sections if section.get("section_node_id") == args.section_node_id]
        if not selected:
            raise ValueError(f"section_node_id not found: {args.section_node_id}")
        return selected
    skip_scopes = set(config.get("tree", {}).get("skip_source_scopes", ["exercise"]))
    eligible = [section for section in sections if section.get("source_scope") == "core_content" and section.get("source_scope") not in skip_scopes]
    if args.dry_run:
        return eligible[:1]
    if args.limit > 0:
        return eligible[: args.limit]
    return eligible


def build_payload(section: dict[str, Any], node_pool: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "section_metadata": {
            "section_node_id": section.get("section_node_id", ""),
            "textbook_id": section.get("textbook_id", ""),
            "textbook_name": section.get("textbook_name", ""),
            "chapter": section.get("chapter", ""),
            "section": section.get("section", ""),
            "subsection": section.get("subsection", ""),
            "source_scope": section.get("source_scope", ""),
            "line_start": section.get("line_start", 0),
            "line_end": section.get("line_end", 0),
        },
        "section_text": section.get("text", ""),
        "node_pool": [compact_node(node) for node in node_pool],
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


def normalize_for_match(text: str) -> str:
    text = re.sub(r"\s+", "", text)
    text = text.replace("\\pmb", "")
    text = text.replace("{", "").replace("}", "")
    return text


def span_in_section(span: str, section_text: str) -> bool:
    if not span:
        return False
    if span in section_text:
        return True
    normalized_span = normalize_for_match(span)
    normalized_text = normalize_for_match(section_text)
    return bool(normalized_span and normalized_span in normalized_text)


def stable_rule_case_id(owner: dict[str, Any], case: dict[str, Any], index: int) -> str:
    digest = hashlib.sha1(
        "|".join([
            str(owner.get("node_id") or ""),
            str(case.get("case_name") or ""),
            str(case.get("evidence_span") or ""),
            str(index),
        ]).encode("utf-8")
    ).hexdigest()[:14]
    return f"{owner.get('textbook_id', '')}:rulecase:{digest}"


def normalize_rule_case(
    raw: dict[str, Any],
    section: dict[str, Any],
    node_by_id: dict[str, dict[str, Any]],
    node_by_name: dict[str, dict[str, Any]],
    index: int,
    model: str,
    mode: str,
) -> dict[str, Any]:
    owner_id = str(raw.get("owner_node_id") or "")
    owner_name = str(raw.get("owner_name") or "").strip()
    owner = node_by_id.get(owner_id) or node_by_name.get(owner_name) or {}
    if owner and not owner_id:
        owner_id = str(owner.get("node_id") or "")
    if owner and not owner_name:
        owner_name = str(owner.get("name") or "")
    logic = str(raw.get("condition_logic") or raw.get("logic") or "UNKNOWN").strip().upper()
    if logic not in VALID_LOGIC:
        logic = "UNKNOWN"
    case = {
        "rule_case_id": "",
        "candidate_id": f"{section.get('section_node_id', '')}:rule-cand-{index:03d}",
        "item_kind": "rule_case",
        "owner_node_id": owner_id,
        "owner_name": owner_name,
        "owner_type": owner.get("type", ""),
        "owner_review_status": owner.get("review_status", ""),
        "case_name": str(raw.get("case_name") or "").strip(),
        "applies_to": str(raw.get("applies_to") or "").strip(),
        "conditions": clean_list(raw.get("conditions")),
        "condition_logic": logic,
        "outcomes": clean_list(raw.get("outcomes")),
        "formula_refs": clean_list(raw.get("formula_refs")),
        "evidence_span": str(raw.get("evidence_span") or "").strip(),
        "source_label": str(raw.get("source_label") or "").strip(),
        "reason": str(raw.get("reason") or "").strip(),
        "confidence": coerce_confidence(raw.get("confidence", 0)),
        "review_recommended": True,
        "review_reason": str(raw.get("review_reason") or "需确认条件、结论、适用对象是否对应同一条教材规则。").strip(),
        "textbook_id": section.get("textbook_id", ""),
        "textbook_name": section.get("textbook_name", ""),
        "chapter": section.get("chapter", ""),
        "section": section.get("section", ""),
        "subsection": section.get("subsection", ""),
        "section_node_id": section.get("section_node_id", ""),
        "source_scope": section.get("source_scope", ""),
        "kg_layer": "rule_case",
        "review_status": "review",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "mode": mode,
    }
    if owner:
        case["rule_case_id"] = stable_rule_case_id(owner, case, index)
    return case


def validate_rule_case(case: dict[str, Any], section_text: str, node_pool_ids: set[str]) -> list[str]:
    warnings: list[str] = []
    if not case.get("owner_node_id"):
        warnings.append("missing_owner_node_id")
    elif case.get("owner_node_id") not in node_pool_ids:
        warnings.append(f"owner_not_in_node_pool:{case.get('owner_node_id')}")
    elif case.get("owner_review_status") != "auto_accept":
        warnings.append("rule_case_owner_review_node")
    if case.get("owner_type") not in OWNER_TYPES:
        warnings.append(f"invalid_owner_type:{case.get('owner_type')}")
    if not case.get("case_name"):
        warnings.append("missing_case_name")
    if not case.get("conditions"):
        warnings.append("missing_conditions")
    if not case.get("outcomes"):
        warnings.append("missing_outcomes")
    evidence = str(case.get("evidence_span") or "")
    if not evidence:
        warnings.append("missing_evidence_span")
    elif not span_in_section(evidence, section_text):
        warnings.append("evidence_span_not_in_section")
    if case.get("confidence", 0.0) < 0.5:
        warnings.append("confidence_below_reject_threshold")
    return warnings


def decide_status(warnings: list[str]) -> str:
    return "review"


def hard_validation_warnings(warnings: list[str]) -> list[str]:
    return [
        warning
        for warning in warnings
        if warning in HARD_VALIDATION_EXACT
        or any(warning.startswith(prefix) for prefix in HARD_VALIDATION_PREFIXES)
    ]


def mock_rule_cases(section: dict[str, Any], node_pool: list[dict[str, Any]]) -> dict[str, Any]:
    if not node_pool:
        return {"rule_cases": []}
    text = str(section.get("text") or "")
    owner = node_pool[0]
    return {
        "rule_cases": [
            {
                "owner_node_id": owner.get("node_id", ""),
                "owner_name": owner.get("name", ""),
                "case_name": f"{owner.get('name', '')} mock 条件判断",
                "applies_to": owner.get("name", ""),
                "conditions": ["mock condition"],
                "condition_logic": "UNKNOWN",
                "outcomes": ["mock outcome"],
                "formula_refs": [],
                "evidence_span": text[:80],
                "source_label": "",
                "reason": "mock rule case",
                "confidence": 0.5,
                "review_recommended": True,
                "review_reason": "mock 仅用于本地流程验证。",
            }
        ]
    }


def write_report(
    path: Path,
    processed_sections: int,
    total_raw: int,
    status_counts: dict[str, int],
    warning_counts: dict[str, int],
) -> None:
    lines = [
        "# v4.4 Step 4B Rule Case Extraction Report",
        "",
        f"- processed sections: {processed_sections}",
        f"- raw rule cases: {total_raw}",
        "",
        "## Review Status",
    ]
    for key in sorted(status_counts):
        lines.append(f"- {key}: {status_counts[key]}")
    lines.extend(["", "## Top Warnings"])
    if warning_counts:
        for key, value in sorted(warning_counts.items(), key=lambda item: (-item[1], item[0]))[:20]:
            lines.append(f"- {key}: {value}")
    else:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = read_config(args.config)
    sections = select_sections(read_jsonl(args.leaf_sections), config, args)
    nodes = read_jsonl(args.nodes)
    node_by_id = {str(node.get("node_id") or ""): node for node in nodes if node.get("node_id")}
    node_by_name = {str(node.get("name") or ""): node for node in nodes if node.get("name")}
    prompt = args.prompt.read_text(encoding="utf-8")
    llm_config = config.get("llm", {})
    model = args.model or llm_config.get("rule_case_model") or llm_config.get("high_risk_model", "GPT-5.5")
    base_url = resolve_base_url(args.base_url, llm_config)
    temperature = args.temperature if args.temperature is not None else float(llm_config.get("temperature", 0.0))
    timeout = resolve_timeout(args.timeout, llm_config)

    api_key = ""
    if not args.mock:
        api_key = load_api_key(llm_config)
        if not api_key:
            raise RuntimeError("API key not found. Set OPENAI_API_KEY or LLM_API_KEY, or use --mock for local validation.")

    print(f"[INFO] sections={len(sections)} nodes={len(nodes)} model={model} mock={args.mock}")
    processed_sections = 0
    total_raw = 0
    status_counts: dict[str, int] = {}
    warning_counts: dict[str, int] = {}

    with (
        open_output(args.raw_output, args.append) as raw_f,
        open_output(args.rule_cases, args.append) as case_f,
        open_output(args.review, args.append) as review_f,
        open_output(args.warnings, args.append) as warn_f,
    ):
        for section in sections:
            node_pool = build_node_pool(section, nodes, args.max_node_pool)
            section_id = section.get("section_node_id", "")
            if not node_pool:
                print(f"[SKIP] {section_id} rule_owner_pool=0")
                continue

            if args.mock:
                raw = mock_rule_cases(section, node_pool)
                elapsed = 0.0
                mode = "mock"
            else:
                started = time.time()
                payload = build_payload(section, node_pool)
                raw = call_llm(api_key, base_url, model, prompt, payload, temperature, timeout)
                elapsed = time.time() - started
                mode = "llm"

            raw_cases = raw.get("rule_cases") if isinstance(raw.get("rule_cases"), list) else []
            raw_f.write(json.dumps({
                "section_node_id": section_id,
                "raw": raw,
                "node_pool_size": len(node_pool),
                "model": model,
                "mode": mode,
                "generated_at": datetime.now().isoformat(timespec="seconds"),
            }, ensure_ascii=False) + "\n")
            processed_sections += 1
            node_pool_ids = {str(node.get("node_id") or "") for node in node_pool}
            section_text = str(section.get("text") or "")
            kept = 0
            warning_rows = 0

            for index, raw_case in enumerate(raw_cases, start=1):
                if not isinstance(raw_case, dict):
                    warn_f.write(json.dumps({
                        "section_node_id": section_id,
                        "candidate_index": index,
                        "warnings": ["raw_rule_case_item_not_object"],
                    }, ensure_ascii=False) + "\n")
                    warning_counts["raw_rule_case_item_not_object"] = warning_counts.get("raw_rule_case_item_not_object", 0) + 1
                    continue
                total_raw += 1
                case = normalize_rule_case(raw_case, section, node_by_id, node_by_name, index, model, mode)
                warnings = validate_rule_case(case, section_text, node_pool_ids)
                if "rule_case_owner_review_node" in warnings:
                    existing_reason = str(case.get("review_reason") or "").strip()
                    extra_reason = "RuleCase 挂载到 Step 3E 待审节点，需随 owner 节点一起进入 Step 7 复核。"
                    case["review_reason"] = f"{existing_reason}；{extra_reason}" if existing_reason else extra_reason
                status = decide_status(warnings)
                hard_warnings = hard_validation_warnings(warnings)
                if hard_warnings:
                    case["pre_audit_hard_warnings"] = hard_warnings
                case["review_status"] = status
                case["step4b_status"] = status
                case["validation_warnings"] = warnings
                status_counts[status] = status_counts.get(status, 0) + 1
                for warning in warnings:
                    warning_counts[warning] = warning_counts.get(warning, 0) + 1

                if warnings:
                    warning_rows += 1
                    warn_f.write(json.dumps({
                        "section_node_id": section_id,
                        "candidate_id": case["candidate_id"],
                        "case_name": case["case_name"],
                        "owner_name": case["owner_name"],
                        "review_status": status,
                        "warnings": warnings,
                    }, ensure_ascii=False) + "\n")
                if status == "review":
                    review_f.write(json.dumps(case, ensure_ascii=False) + "\n")
                case_f.write(json.dumps(case, ensure_ascii=False) + "\n")
                kept += 1

            print(
                f"[OK] {section_id} mode={mode} elapsed={elapsed:.1f}s "
                f"raw_rule_cases={len(raw_cases)} kept={kept} warnings={warning_rows}"
            )

    write_report(args.report, processed_sections, total_raw, status_counts, warning_counts)
    print(f"[OK] raw -> {args.raw_output}")
    print(f"[OK] rule cases -> {args.rule_cases}")
    print(f"[OK] review -> {args.review}")
    print(f"[OK] warnings -> {args.warnings}")
    print(f"[OK] report -> {args.report}")


if __name__ == "__main__":
    main()


