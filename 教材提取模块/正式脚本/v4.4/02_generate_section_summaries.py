"""
v4.3 Step 2: generate leaf-section summaries.

Default model comes from v4_3_config.json. Use --mock for local validation
without calling the DeepSeek API.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODULE_DIR = SCRIPT_DIR.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "v4_3_config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "section_summary.md"
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "中间产物"
DEFAULT_LEAF_SECTIONS = DEFAULT_OUTPUT_DIR / "leaf_sections.jsonl"
DEFAULT_OUTPUT = DEFAULT_OUTPUT_DIR / "section_summaries.jsonl"
DEFAULT_WARNINGS = DEFAULT_OUTPUT_DIR / "section_summary_warnings.jsonl"
ENV_PATHS = [REPO_ROOT / ".env", MODULE_DIR / ".env"]
SPAN_LIST_FIELDS = ("definition_spans", "theorem_formula_spans", "method_problem_spans")
FORMULA_BLOCK_TITLE_ALLOW_RE = re.compile(r"(公式|求解|解公式|展开|计算|表示|表达|判别|递推)")
FORMULA_BLOCK_TITLE_BLOCK_RE = re.compile(r"(性质|等式)$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate v4.3 section summaries.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--leaf-sections", type=Path, default=DEFAULT_LEAF_SECTIONS)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--warnings", type=Path, default=DEFAULT_WARNINGS)
    parser.add_argument("--chunk-id", "--section-node-id", dest="section_node_id", default="")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true", help="Process one eligible section.")
    parser.add_argument("--mock", action="store_true", help="Generate deterministic local mock summaries.")
    parser.add_argument("--model", default="", help="Override model.")
    parser.add_argument("--base-url", default="", help="Override API base URL.")
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


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"JSONL not found: {path}. Run 01_build_textbook_tree.py first.")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def select_sections(sections: list[dict[str, Any]], config: dict[str, Any], args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.section_node_id:
        selected = [s for s in sections if s.get("section_node_id") == args.section_node_id]
        if not selected:
            raise ValueError(f"section_node_id not found: {args.section_node_id}")
        return selected

    skip_scopes = set(config.get("tree", {}).get("skip_source_scopes", ["exercise"]))
    eligible = [s for s in sections if s.get("source_scope") not in skip_scopes]
    if args.dry_run:
        return eligible[:1]
    if args.limit > 0:
        return eligible[: args.limit]
    return eligible


def build_payload(section: dict[str, Any]) -> dict[str, Any]:
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
            "anchors": [
                {
                    "anchor_id": a.get("anchor_id", ""),
                    "title": a.get("title", ""),
                    "anchor_type": a.get("anchor_type", ""),
                    "source_label": a.get("source_label", ""),
                }
                for a in section.get("anchors", [])
            ],
        },
        "section_text": section.get("text", ""),
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
        raise RuntimeError(
            f"LLM returned invalid JSON: {first_exc}; content_prefix={content[:1000]}"
        ) from first_exc


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
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    last_error: RuntimeError | None = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                response_body = json.loads(response.read().decode("utf-8"))
            content = response_body.get("choices", [{}])[0].get("message", {}).get("content") or "{}"
            return parse_llm_json(content)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"LLM HTTP {exc.code}: {body[:1000]}") from exc
        except urllib.error.URLError as exc:
            last_error = RuntimeError(f"LLM request failed: {exc}")
        except RuntimeError as exc:
            last_error = exc
        if attempt < 3:
            time.sleep(1.5 * attempt)
    assert last_error is not None
    raise last_error


def first_sentences(text: str, max_chars: int = 260) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= max_chars:
        return compact
    return compact[:max_chars].rstrip() + "..."


def mock_summary(section: dict[str, Any]) -> dict[str, Any]:
    terms: list[str] = []
    for anchor in section.get("anchors", [])[:8]:
        title = str(anchor.get("title", "")).strip()
        if title:
            terms.append(title)
    subsection = str(section.get("subsection") or section.get("section") or "")
    if subsection and subsection not in terms:
        terms.insert(0, subsection)
    return {
        "summary": first_sentences(section.get("text", "")),
        "key_terms": terms[:10],
        "definition_spans": [],
        "theorem_formula_spans": [],
        "formula_block_hints": [],
        "method_problem_spans": [],
        "state_or_attribute_hints": [],
        "rule_case_hints": [],
        "section_role_notes": "",
        "skip_reason": "",
    }


def normalize_summary(raw: dict[str, Any], section: dict[str, Any], model: str, mode: str) -> dict[str, Any]:
    def list_field(name: str) -> list[Any]:
        value = raw.get(name)
        return value if isinstance(value, list) else []

    section_text = str(section.get("text") or "")
    filtered_invalid_span_counts: dict[str, int] = {}

    def valid_span_items(name: str) -> list[Any]:
        items = list_field(name)
        valid_items: list[Any] = []
        filtered = 0
        for item in items:
            if not isinstance(item, dict):
                filtered += 1
                continue
            span = str(item.get("span") or "")
            if span_in_section(span, section_text):
                valid_items.append(item)
            else:
                filtered += 1
        if filtered:
            filtered_invalid_span_counts[name] = filtered
        return valid_items

    def valid_rule_case_hints() -> list[dict[str, Any]]:
        items = list_field("rule_case_hints")
        valid_items: list[dict[str, Any]] = []
        filtered = 0
        for item in items:
            if not isinstance(item, dict):
                filtered += 1
                continue
            full_span = str(item.get("full_span") or "")
            condition_span = str(item.get("condition_span") or "")
            outcome_span = str(item.get("outcome_span") or "")
            if (
                span_in_section(full_span, section_text)
                or span_in_section(condition_span, section_text)
                or span_in_section(outcome_span, section_text)
            ):
                valid_items.append(item)
            else:
                filtered += 1
        if filtered:
            filtered_invalid_span_counts["rule_case_hints"] = filtered
        return valid_items

    def valid_formula_block_hints() -> list[dict[str, Any]]:
        items = list_field("formula_block_hints")
        valid_items: list[dict[str, Any]] = []
        filtered = 0
        for item in items:
            if not isinstance(item, dict):
                filtered += 1
                continue
            formula_span = str(item.get("formula_span") or "")
            full_span = str(item.get("full_span") or "")
            lead_span = str(item.get("lead_span") or "")
            if not formula_block_hint_allowed(item):
                filtered += 1
                continue
            if (
                span_in_section(formula_span, section_text)
                or span_in_section(full_span, section_text)
                or span_in_section(lead_span, section_text)
            ):
                valid_items.append(item)
            else:
                filtered += 1
        if filtered:
            filtered_invalid_span_counts["formula_block_hints"] = filtered
        return valid_items

    deprecated_candidate_hints = list_field("candidate_node_hints")
    deprecated_relation_hints = list_field("relation_hints")
    source_scope = section.get("source_scope", "")
    theorem_formula_spans = valid_span_items("theorem_formula_spans")
    filtered_example_theorem_formula_count = 0
    if source_scope == "example":
        filtered_example_theorem_formula_count = len(theorem_formula_spans)
        theorem_formula_spans = []
    formula_block_hints = valid_formula_block_hints()
    filtered_example_formula_block_count = 0
    if source_scope == "example":
        filtered_example_formula_block_count = len(formula_block_hints)
        formula_block_hints = []
    return {
        "summary_id": f"{section.get('section_node_id', '')}:summary",
        "section_node_id": section.get("section_node_id", ""),
        "textbook_id": section.get("textbook_id", ""),
        "textbook_name": section.get("textbook_name", ""),
        "chapter": section.get("chapter", ""),
        "section": section.get("section", ""),
        "subsection": section.get("subsection", ""),
        "source_scope": section.get("source_scope", ""),
        "line_start": section.get("line_start", 0),
        "line_end": section.get("line_end", 0),
        "summary": str(raw.get("summary", "") or "").strip(),
        "key_terms": list_field("key_terms"),
        "definition_spans": valid_span_items("definition_spans"),
        "theorem_formula_spans": theorem_formula_spans,
        "formula_block_hints": formula_block_hints,
        "method_problem_spans": valid_span_items("method_problem_spans"),
        "state_or_attribute_hints": list_field("state_or_attribute_hints"),
        "rule_case_hints": valid_rule_case_hints(),
        "section_role_notes": str(raw.get("section_role_notes", "") or "").strip(),
        "skip_reason": str(raw.get("skip_reason", "") or "").strip(),
        "deprecated_candidate_node_hints_count": len(deprecated_candidate_hints),
        "deprecated_relation_hints_count": len(deprecated_relation_hints),
        "filtered_example_theorem_formula_count": filtered_example_theorem_formula_count,
        "filtered_example_formula_block_count": filtered_example_formula_block_count,
        "filtered_invalid_span_counts": filtered_invalid_span_counts,
        "model": model,
        "mode": mode,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


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


def formula_block_hint_allowed(item: dict[str, Any]) -> bool:
    title = str(item.get("semantic_title") or "")
    label = str(item.get("source_label") or "")
    note = str(item.get("note") or "")
    joined = title + " " + label + " " + note
    if FORMULA_BLOCK_TITLE_ALLOW_RE.search(joined):
        return True
    if FORMULA_BLOCK_TITLE_BLOCK_RE.search(title):
        return False
    if "性质" in joined and "公式" not in joined:
        return False
    return True


def validate_summary(row: dict[str, Any], section: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if row["source_scope"] != "exercise" and not row["summary"]:
        warnings.append("missing_summary")
    if row["source_scope"] == "exercise" and row["summary"]:
        warnings.append("exercise_has_summary")
    if not isinstance(row.get("key_terms"), list):
        warnings.append("key_terms_not_list")
    if row.get("deprecated_candidate_node_hints_count", 0):
        warnings.append("deprecated_candidate_node_hints_returned")
    if row.get("deprecated_relation_hints_count", 0):
        warnings.append("deprecated_relation_hints_returned")
    if row["source_scope"] == "example" and row.get("filtered_example_theorem_formula_count", 0):
        warnings.append("example_theorem_formula_spans_filtered")
    if row["source_scope"] == "example" and row.get("filtered_example_formula_block_count", 0):
        warnings.append("example_formula_block_hints_filtered")
    for field, count in row.get("filtered_invalid_span_counts", {}).items():
        warnings.append(f"{field}_invalid_spans_filtered:{count}")

    section_text = str(section.get("text") or "")
    for field in SPAN_LIST_FIELDS:
        value = row.get(field)
        if not isinstance(value, list):
            warnings.append(f"{field}_not_list")
            continue
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                warnings.append(f"{field}_item_not_object:{index}")
                continue
            span = str(item.get("span") or "")
            if not span_in_section(span, section_text):
                warnings.append(f"{field}_span_not_in_section:{index}")
    value = row.get("formula_block_hints")
    if not isinstance(value, list):
        warnings.append("formula_block_hints_not_list")
    else:
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                warnings.append(f"formula_block_hints_item_not_object:{index}")
                continue
            formula_span = str(item.get("formula_span") or "")
            full_span = str(item.get("full_span") or "")
            lead_span = str(item.get("lead_span") or "")
            if not (
                span_in_section(formula_span, section_text)
                or span_in_section(full_span, section_text)
                or span_in_section(lead_span, section_text)
            ):
                warnings.append(f"formula_block_hints_span_not_in_section:{index}")
    return warnings


def open_output(path: Path, append: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    return path.open("a" if append else "w", encoding="utf-8", newline="\n")


def main() -> None:
    args = parse_args()
    config = read_config(args.config)
    sections = select_sections(read_jsonl(args.leaf_sections), config, args)
    prompt = args.prompt.read_text(encoding="utf-8")
    llm_config = config.get("llm", {})
    model = args.model or llm_config.get("default_model", "deepseek-chat")
    base_url = args.base_url or llm_config.get("base_url", "https://api.deepseek.com/v1")
    temperature = args.temperature if args.temperature is not None else float(llm_config.get("temperature", 0.0))
    timeout = args.timeout if args.timeout is not None else float(llm_config.get("timeout_seconds", 120))

    api_key = ""
    if not args.mock:
        api_key = load_env_value("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY not found. Use --mock for local validation.")

    print(f"[INFO] sections={len(sections)} model={model} mock={args.mock}")
    warning_count = 0
    with open_output(args.output, args.append) as out_f, open_output(args.warnings, args.append) as warn_f:
        for section in sections:
            if args.mock:
                raw = mock_summary(section)
                elapsed = 0.0
                mode = "mock"
            else:
                payload = build_payload(section)
                started = time.time()
                raw = call_llm(api_key, base_url, model, prompt, payload, temperature, timeout)
                elapsed = time.time() - started
                mode = "llm"

            row = normalize_summary(raw, section, model, mode)
            warnings = validate_summary(row, section)
            out_f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if warnings:
                warning_count += 1
                warn_f.write(json.dumps({
                    "section_node_id": section.get("section_node_id", ""),
                    "warnings": warnings,
                    "summary_id": row["summary_id"],
                }, ensure_ascii=False) + "\n")
            print(f"[OK] {section.get('section_node_id')} mode={mode} elapsed={elapsed:.1f}s warnings={len(warnings)}")

    print(f"[OK] summaries -> {args.output}")
    print(f"[OK] warnings -> {args.warnings} count={warning_count}")


if __name__ == "__main__":
    main()
