"""
v4.4 Step 7B: AI review suggestions for all review items.

Step 7B produces suggestions only. It never changes graph candidates and never
executes merges. Step 7C validates the suggestions before Step 7D applies them.
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
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from llm_env import load_api_key, resolve_base_url, resolve_timeout


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
MODULE_DIR = SCRIPT_DIR.parents[1]
DEFAULT_CONFIG = SCRIPT_DIR / "v4_4_gaoshu_config.json"
DEFAULT_PROMPT = SCRIPT_DIR / "prompts" / "review_item_ai_suggestion.md"
DEFAULT_REVIEW_DIR = SCRIPT_DIR / "中间产物" / "step7_review"
DEFAULT_REVIEW_ITEMS = DEFAULT_REVIEW_DIR / "review_items.jsonl"
DEFAULT_OUT = DEFAULT_REVIEW_DIR / "ai_review_decisions.jsonl"
DEFAULT_SUMMARY = DEFAULT_REVIEW_DIR / "ai_review_summary.md"
ENV_PATHS = [REPO_ROOT / ".env", MODULE_DIR / ".env"]

STANDARD_ACTIONS = {"accept", "reject", "rewrite", "defer"}
MERGE_ACTIONS = {"accept_merge", "reject_merge", "defer"}
ALL_ACTIONS = STANDARD_ACTIONS | MERGE_ACTIONS
SAFE_DEFAULT_MODEL = "GPT-5.5"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate v4.4 Step 7B AI review suggestions.")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--review-items", type=Path, default=DEFAULT_REVIEW_ITEMS)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--temperature", type=float, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-workers", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--item-kind", choices=["all", "node", "edge", "rule_case", "merge_candidate"], default="all")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--append", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--allow-pro", action="store_true")
    return parser.parse_args()


def read_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSON not found: {path}")
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSONL not found: {path}")
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]], append: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_env_value(key: str) -> str:
    if os.environ.get(key):
        return os.environ[key]
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
    return ""


def is_pro_model(model: str) -> bool:
    return "pro" in model.lower()


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


def call_llm(api_key: str, base_url: str, model: str, prompt: str, payload: dict[str, Any], temperature: float, timeout: float) -> dict[str, Any]:
    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你只输出合法 JSON，不输出 Markdown 或解释。"},
            {"role": "user", "content": prompt + "\n\n## 当前审核输入\n\n" + json.dumps(payload, ensure_ascii=False)},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        url=base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
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
                last_error = RuntimeError(f"LLM HTTP {exc.code}: {body[:1200]}")
            else:
                raise RuntimeError(f"LLM HTTP {exc.code}: {body[:1200]}") from exc
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


def completed_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    result: set[str] = set()
    for row in read_jsonl(path, required=False):
        review_item_id = str(row.get("review_item_id") or "")
        if review_item_id:
            result.add(review_item_id)
    return result


def select_items(items: list[dict[str, Any]], item_kind: str, limit: int) -> list[dict[str, Any]]:
    selected = items if item_kind == "all" else [row for row in items if row.get("item_kind") == item_kind]
    return selected[:limit] if limit > 0 else selected


def batched(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    size = max(1, size)
    return [rows[index : index + size] for index in range(0, len(rows), size)]


def compact_item(item: dict[str, Any]) -> dict[str, Any]:
    source = item.get("source_item") or {}
    context = item.get("context") or {}
    allowed_rewrite_endpoint_names: list[str] = []
    if item.get("item_kind") == "edge":
        for name in [
            context.get("source_name", ""),
            context.get("target_name", ""),
            source.get("source_name", ""),
            source.get("target_name", ""),
        ]:
            name = str(name or "").strip()
            if name and name not in allowed_rewrite_endpoint_names:
                allowed_rewrite_endpoint_names.append(name)
    return {
        "review_item_id": item.get("review_item_id", ""),
        "item_kind": item.get("item_kind", ""),
        "title": item.get("title", ""),
        "allowed_actions": item.get("allowed_actions", []),
        "default_action": item.get("default_action", "defer"),
        "risk_flags": item.get("risk_flags", []),
        "source_code": item.get("source_code", ""),
        "context": context,
        "source_item_brief": {
            "name": source.get("name", ""),
            "type": source.get("type", ""),
            "source_name": source.get("source_name", ""),
            "target_name": source.get("target_name", ""),
            "owner_name": source.get("owner_name", ""),
            "case_name": source.get("case_name", ""),
            "definition": source.get("definition", ""),
            "description": source.get("description", ""),
            "evidence_span": source.get("evidence_span", ""),
            "validation_warnings": source.get("validation_warnings", []),
        },
        "rewrite_constraints": {
            "edge_endpoint_policy": "edge rewrite 的 source_name / target_name 必须逐字使用 allowed_rewrite_endpoint_names 中的名称；如果想换到列表外端点，必须 defer。",
            "allowed_rewrite_endpoint_names": allowed_rewrite_endpoint_names,
        },
    }


def normalize_action(raw_action: Any, item: dict[str, Any]) -> str:
    action = str(raw_action or "").strip().lower()
    allowed = set(item.get("allowed_actions") or [])
    if action in allowed:
        return action
    if item.get("item_kind") == "merge_candidate":
        return "defer"
    return "defer"


def normalize_target_layer(action: str, item_kind: str, raw_target: Any) -> str:
    target = str(raw_target or "").strip()
    if action == "accept_merge":
        return "merge_plan"
    if action == "reject_merge":
        return "rejected_archive"
    if action == "reject":
        return "rejected_archive"
    if action == "defer":
        return "review_pending"
    if action == "accept" and item_kind == "rule_case":
        return "rule_case"
    if action == "accept" and target:
        return target
    if action == "rewrite" and target:
        return target
    return "core"


def default_decision(item: dict[str, Any], action: str, detail: str, basis: str) -> dict[str, Any]:
    action = normalize_action(action, item)
    return {
        "review_item_id": item.get("review_item_id", ""),
        "item_kind": item.get("item_kind", ""),
        "item_id": item.get("item_id", ""),
        "title": item.get("title", ""),
        "action": action,
        "target_layer": normalize_target_layer(action, str(item.get("item_kind") or ""), ""),
        "action_detail": detail,
        "basis": basis,
        "rewritten_item": None,
        "source_item": item.get("source_item", {}),
        "review_item": item,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def mock_decision(item: dict[str, Any]) -> dict[str, Any]:
    kind = str(item.get("item_kind") or "")
    if kind == "merge_candidate":
        return default_decision(item, "defer", "mock_defer_merge_candidate", "Mock: 合并候选需要专门复核。")
    if kind == "edge" and (item.get("context") or {}).get("edge_type") == "DERIVES":
        return default_decision(item, "defer", "mock_defer_derives", "Mock: DERIVES 方向需要复核。")
    if kind == "rule_case":
        evidence = str((item.get("context") or {}).get("evidence_span") or "")
        if len(evidence.strip()) < 8:
            return default_decision(item, "reject", "mock_reject_short_rule_case", "Mock: 规则案例证据过短。")
    return default_decision(item, "accept", f"mock_accept_{kind}", "Mock: 候选项暂按可接受处理。")


def normalize_llm_decisions(raw: dict[str, Any], batch: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_by_id = {str(row.get("review_item_id") or ""): row for row in batch}
    raw_rows = raw.get("decisions") if isinstance(raw.get("decisions"), list) else []
    output: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            warnings.append({"warning": "raw_decision_not_object", "raw": raw_row})
            continue
        review_item_id = str(raw_row.get("review_item_id") or "")
        item = source_by_id.get(review_item_id)
        if not item:
            warnings.append({"warning": "unknown_review_item_id", "review_item_id": review_item_id})
            continue
        action = normalize_action(raw_row.get("action"), item)
        decision = {
            "review_item_id": review_item_id,
            "item_kind": item.get("item_kind", ""),
            "item_id": item.get("item_id", ""),
            "title": item.get("title", ""),
            "action": action,
            "target_layer": normalize_target_layer(action, str(item.get("item_kind") or ""), raw_row.get("target_layer")),
            "action_detail": str(raw_row.get("action_detail") or f"ai_suggest_{action}")[:200],
            "basis": str(raw_row.get("basis") or "").strip(),
            "rewritten_item": raw_row.get("rewritten_item") if action == "rewrite" else None,
            "source_item": item.get("source_item", {}),
            "review_item": item,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
        if str(raw_row.get("action") or "").strip().lower() != action:
            decision["ai_review_normalization_warning"] = "invalid_action_for_item_kind_forced_defer"
            warnings.append({"warning": "invalid_action_for_item_kind", "review_item_id": review_item_id})
        output.append(decision)
        seen.add(review_item_id)
    for item in batch:
        review_item_id = str(item.get("review_item_id") or "")
        if review_item_id not in seen:
            output.append(default_decision(item, "defer", "ai_missing_decision", "AI 未返回该项，按保守策略暂缓。"))
            warnings.append({"warning": "missing_decision_from_ai", "review_item_id": review_item_id})
    return output, warnings


def batch_failed_decisions(batch: list[dict[str, Any]], error: Exception) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    warnings = [{
        "warning": "batch_failed_no_decision",
        "error": str(error)[:500],
        "items": [row.get("review_item_id", "") for row in batch],
    }]
    return [], warnings


def process_batch(batch: list[dict[str, Any]], args: argparse.Namespace, prompt: str, api: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if args.mock:
        return [mock_decision(item) for item in batch], []
    payload = {"review_items": [compact_item(item) for item in batch]}
    try:
        raw = call_llm(api["api_key"], api["base_url"], api["model"], prompt, payload, api["temperature"], api["timeout"])
        return normalize_llm_decisions(raw, batch)
    except Exception as exc:  # noqa: BLE001
        return batch_failed_decisions(batch, exc)


def write_summary(path: Path, decisions: list[dict[str, Any]], warnings: list[dict[str, Any]], model: str, mock: bool) -> None:
    counts = Counter((row.get("item_kind", ""), row.get("action", "")) for row in decisions)
    lines = [
        "# v4.4 Step 7B AI Review Summary",
        "",
        f"- model: {model}",
        f"- mock: {mock}",
        f"- decisions: {len(decisions)}",
        f"- warnings: {len(warnings)}",
        "",
        "## Counts",
    ]
    for (kind, action), count in sorted(counts.items()):
        lines.append(f"- {kind} / {action}: {count}")
    if warnings:
        lines.extend(["", "## Warnings"])
        for warning in warnings[:100]:
            lines.append(f"- {json.dumps(warning, ensure_ascii=False)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    config = read_json(args.config, required=False)
    llm_config = config.get("llm", {}) if isinstance(config.get("llm"), dict) else {}
    model = args.model or llm_config.get("review_model") or llm_config.get("high_risk_model") or SAFE_DEFAULT_MODEL
    if is_pro_model(model) and not (args.allow_pro or llm_config.get("allow_pro")):
        raise SystemExit(f"Pro model blocked by default: {model}. Use --allow-pro or config llm.allow_pro=true.")

    items = select_items(read_jsonl(args.review_items), args.item_kind, args.limit)
    if args.resume:
        done = completed_ids(args.out)
        items = [row for row in items if str(row.get("review_item_id") or "") not in done]
    batches = batched(items, args.batch_size)

    api = {
        "api_key": load_api_key(llm_config),
        "base_url": resolve_base_url(args.base_url, llm_config),
        "model": model,
        "temperature": args.temperature if args.temperature is not None else float(llm_config.get("temperature", 0.0)),
        "timeout": resolve_timeout(args.timeout, llm_config),
    }
    if not args.mock and not api["api_key"]:
        raise SystemExit("Missing API key. Set OPENAI_API_KEY or LLM_API_KEY, or use --mock.")
    prompt = args.prompt.read_text(encoding="utf-8")

    all_decisions: list[dict[str, Any]] = []
    all_warnings: list[dict[str, Any]] = []
    if args.max_workers <= 1 or len(batches) <= 1:
        append_mode = args.append or args.resume
        first_write = True
        for index, batch in enumerate(batches, start=1):
            decisions, warnings = process_batch(batch, args, prompt, api)
            all_decisions.extend(decisions)
            all_warnings.extend(warnings)
            write_jsonl(args.out, decisions, append=append_mode or not first_write)
            first_write = False
            section = ""
            if batch:
                source = batch[0].get("source_item") or {}
                section = str(source.get("section_node_id") or "")
            print(
                f"[OK] batch={index}/{len(batches)} section={section} "
                f"decisions={len(decisions)} warnings={len(warnings)}"
            )
    else:
        with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            futures = [executor.submit(process_batch, batch, args, prompt, api) for batch in batches]
            append_mode = args.append or args.resume
            first_write = True
            completed_batches = 0
            for future in as_completed(futures):
                decisions, warnings = future.result()
                all_decisions.extend(decisions)
                all_warnings.extend(warnings)
                write_jsonl(args.out, decisions, append=append_mode or not first_write)
                first_write = False
                completed_batches += 1
                print(
                    f"[OK] completed_batch={completed_batches}/{len(batches)} "
                    f"decisions={len(decisions)} warnings={len(warnings)}"
                )
    warnings_path = args.out.with_name("ai_review_warnings.jsonl")
    write_jsonl(warnings_path, all_warnings)
    write_summary(args.summary, all_decisions, all_warnings, model, args.mock)
    print(f"[OK] AI review decisions -> {args.out}")
    print(f"[OK] warnings -> {warnings_path}")
    print(f"[INFO] decisions={len(all_decisions)} warnings={len(all_warnings)}")


if __name__ == "__main__":
    main()

