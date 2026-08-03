"""Run fixed Chinese formula benchmarks against OpenAI-compatible providers."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import subprocess
import threading
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import httpx

from app.services.formula_conversion_service import (
    FORMULA_JSON_OBJECT_FORMAT,
    FORMULA_JSON_SCHEMA_FORMAT,
    build_formula_completion_request,
    sanitize_latex,
)
from benchmarks.formula.dataset import FormulaCase, build_cases

ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_CHECKER = Path(__file__).with_name("semantic_check.mjs")

SCREENING_LIMITS = {
    "success_rate": 0.99,
    "renderable_rate": 0.99,
    "semantic_rate": 0.95,
    "category_semantic_rate": 0.90,
    "latency_p95_ms": 3000,
    "peak_memory_mb": 1024,
    "minimum_mem_available_mb": 256,
    "swap_delta_mb": 64,
}


def normalize_latex(value: str) -> str:
    replacements = {
        r"\left": "", r"\right": "", r"\dfrac": r"\frac",
        r"\tfrac": r"\frac", r"\leqslant": r"\le", r"\geqslant": r"\ge",
        r"\leq": r"\le", r"\geq": r"\ge", r"\neq": r"\ne",
        r"\emptyset": r"\varnothing",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return "".join(value.split())


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))]


def _read_status_value(pid: int, key: str) -> float | None:
    status = Path(f"/proc/{pid}/status")
    if not status.exists():
        return None
    for line in status.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}:"):
            return int(line.split()[1]) / 1024
    return None


def _read_mem_available_mb() -> float | None:
    meminfo = Path("/proc/meminfo")
    if not meminfo.exists():
        return None
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) / 1024
    return None


def _read_swap_events() -> int | None:
    vmstat = Path("/proc/vmstat")
    if not vmstat.exists():
        return None
    values: dict[str, int] = {}
    for line in vmstat.read_text(encoding="utf-8").splitlines():
        key, value = line.split()
        if key in {"pswpin", "pswpout"}:
            values[key] = int(value)
    if len(values) != 2:
        return None
    return values["pswpin"] + values["pswpout"]


class ResourceSampler:
    """Collect Linux-only memory signals without storing benchmark content."""

    def __init__(self, pid: int | None, interval_seconds: float = 0.2) -> None:
        self.pid = pid
        self.interval_seconds = interval_seconds
        self.peak_rss_mb: float | None = None
        self.minimum_mem_available_mb: float | None = None
        self.swap_before = _read_swap_events()
        self.swap_after: int | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        if self.pid:
            rss = _read_status_value(self.pid, "VmHWM")
            if rss is not None:
                self.peak_rss_mb = max(self.peak_rss_mb or 0, rss)
        available = _read_mem_available_mb()
        if available is not None:
            self.minimum_mem_available_mb = min(self.minimum_mem_available_mb or available, available)

    def start(self) -> None:
        self._sample()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def stop(self) -> dict[str, float | None]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)
        self._sample()
        self.swap_after = _read_swap_events()
        page_size = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
        swap_delta_mb = None
        if self.swap_before is not None and self.swap_after is not None:
            swap_delta_mb = (self.swap_after - self.swap_before) * page_size / 1024 / 1024
        return {
            "peak_memory_mb": self.peak_rss_mb,
            "minimum_mem_available_mb": self.minimum_mem_available_mb,
            "swap_delta_mb": swap_delta_mb,
        }


def renderable_flags(formulas: list[str]) -> list[bool]:
    completed = subprocess.run(
        ["node", str(Path(__file__).with_name("render_check.mjs"))],
        input=json.dumps(formulas), text=True, capture_output=True, check=True, cwd=ROOT,
    )
    return json.loads(completed.stdout)


def semantic_equivalence_pairs(pairs: Iterable[tuple[str, str]]) -> list[dict[str, Any]]:
    payload = [{"actual": actual, "expected": expected} for actual, expected in pairs]
    completed = subprocess.run(
        ["node", str(SEMANTIC_CHECKER)], input=json.dumps(payload), text=True,
        capture_output=True, check=True, cwd=ROOT,
    )
    return json.loads(completed.stdout)


def semantic_flags(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return semantic_equivalence_pairs(
        (row["latex"], row["expected_latex"]) for row in rows
    )


def _request_payload(provider: dict[str, Any], description: str, response_format: dict[str, Any]) -> dict[str, Any]:
    request = build_formula_completion_request(description)
    extra_body = request.pop("extra_body", {})
    if provider.get("llama_cpp"):
        extra_body = {
            **extra_body,
            "chat_template_kwargs": {"enable_thinking": False},
        }
    return {
        "model": provider["model"],
        **request,
        **extra_body,
        "response_format": response_format,
    }


def query_provider(
    client: httpx.Client,
    provider: dict[str, Any],
    description: str,
    timeout_seconds: float = 8.0,
) -> tuple[str, float, str]:
    """Use one deadline for Schema and JSON Object attempts together."""
    api_key = os.getenv(provider.get("api_key_env", ""), "local")
    url = f"{provider['base_url'].rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    started = time.perf_counter()
    deadline = started + timeout_seconds

    def post(response_format: dict[str, Any]) -> httpx.Response:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            raise httpx.TimeoutException("formula conversion exceeded its total deadline")
        return client.post(
            url, headers=headers,
            json=_request_payload(provider, description, response_format),
            timeout=remaining,
        )

    response = post(FORMULA_JSON_SCHEMA_FORMAT)
    format_used = "json_schema"
    if response.status_code == 400:
        response = post(FORMULA_JSON_OBJECT_FORMAT)
        format_used = "json_object"
    response.raise_for_status()
    content = response.json()["choices"][0]["message"].get("content", "")
    return sanitize_latex(content), (time.perf_counter() - started) * 1000, format_used


def probe_response_formats(provider: dict[str, Any], description: str = "x平方") -> dict[str, Any]:
    """Record protocol support without requiring JSON Schema compatibility."""
    url = f"{provider['base_url'].rstrip('/')}/chat/completions"
    api_key = os.getenv(provider.get("api_key_env", ""), "local")
    headers = {"Authorization": f"Bearer {api_key}"}
    rows: dict[str, dict[str, Any]] = {}
    with httpx.Client(timeout=8.0) as client:
        for name, response_format in (
            ("json_schema", FORMULA_JSON_SCHEMA_FORMAT),
            ("json_object", FORMULA_JSON_OBJECT_FORMAT),
        ):
            try:
                response = client.post(
                    url, headers=headers,
                    json=_request_payload(provider, description, response_format),
                    timeout=8.0,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"].get("content", "")
                sanitize_latex(content)
                rows[name] = {"passed": True, "status_code": response.status_code}
            except Exception as exc:
                status_code = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                rows[name] = {
                    "passed": False, "status_code": status_code,
                    "error_type": type(exc).__name__,
                }
    return {
        "formats": rows,
        "fallback_required": not rows["json_schema"]["passed"] and rows["json_object"]["passed"],
        "passed": rows["json_schema"]["passed"] or rows["json_object"]["passed"],
    }


def cases_for_profile(profile: str) -> list[FormulaCase]:
    cases = build_cases()
    if profile == "full":
        return cases
    per_category = defaultdict(list)
    for case in cases:
        per_category[case.category].append(case)
    indexes = {"smoke": (0, 12, 24), "determinism": (0, 6, 12, 18, 24), "integration": (0, 12)}[profile]
    return [case_list[index] for case_list in per_category.values() for index in indexes]


def run_cases(
    provider: dict[str, Any], cases: Iterable[FormulaCase], timeout_seconds: float = 8.0,
    server_pid: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, float | None]]:
    sampler = ResourceSampler(server_pid)
    rows: list[dict[str, Any]] = []
    sampler.start()
    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            for case in cases:
                row: dict[str, Any] = {
                    "provider": provider["name"], "case_id": case.id,
                    "category": case.category, "description": case.description,
                    "expected_latex": case.expected_latex, "expected_display": case.expected_display,
                    "status": "error", "latex": "", "latency_ms": 0.0,
                    "error_type": None, "response_format": None,
                }
                try:
                    latex, latency_ms, response_format = query_provider(
                        client, provider, case.description, timeout_seconds
                    )
                    row.update(status="success", latex=latex, latency_ms=latency_ms, response_format=response_format)
                except Exception as exc:
                    row["error_type"] = type(exc).__name__
                rows.append(row)
    finally:
        resources = sampler.stop()

    renderable = renderable_flags([row["latex"] for row in rows])
    semantic = semantic_flags(rows)
    for row, is_renderable, semantic_result in zip(rows, renderable, semantic):
        row["renderable"] = bool(is_renderable and row["status"] == "success")
        row["exact_match"] = row["status"] == "success" and normalize_latex(row["latex"]) == normalize_latex(row["expected_latex"])
        row["automatic_semantic_correct"] = bool(row["status"] == "success" and semantic_result["equivalent"])
        row["automatic_semantic_method"] = semantic_result["method"]
    return rows, resources


def summarize(provider: dict[str, Any], rows: list[dict[str, Any]], resources: dict[str, float | None] | None = None) -> dict[str, Any]:
    resources = resources or {}
    succeeded = [row for row in rows if row["status"] == "success"]
    category_semantics: dict[str, list[bool]] = defaultdict(list)
    for row in rows:
        category_semantics[row["category"]].append(row["automatic_semantic_correct"])
    latencies = [row["latency_ms"] for row in succeeded]
    timeout_count = sum(row["error_type"] in {"ReadTimeout", "TimeoutException"} for row in rows)
    unsafe_count = sum(row["error_type"] == "UnsafeFormulaError" for row in rows)
    summary = {
        "provider": provider["name"], "cases": len(rows),
        "success_rate": len(succeeded) / len(rows) if rows else 0,
        "exact_match_rate": sum(row["exact_match"] for row in rows) / len(rows) if rows else 0,
        "renderable_rate": sum(row["renderable"] for row in rows) / len(rows) if rows else 0,
        "automatic_semantic_rate": sum(row["automatic_semantic_correct"] for row in rows) / len(rows) if rows else 0,
        "category_automatic_semantic_rates": {
            key: sum(values) / len(values) for key, values in sorted(category_semantics.items())
        },
        "latency_p50_ms": statistics.median(latencies) if latencies else None,
        "latency_p95_ms": percentile(latencies, .95),
        "timeout_count": timeout_count, "unsafe_output_count": unsafe_count,
        "peak_memory_mb": resources.get("peak_memory_mb"),
        "minimum_mem_available_mb": resources.get("minimum_mem_available_mb"),
        "swap_delta_mb": resources.get("swap_delta_mb"),
        "startup_seconds": provider.get("startup_seconds"),
    }
    category_gate = len(category_semantics) == 13 and all(
        rate >= SCREENING_LIMITS["category_semantic_rate"]
        for rate in summary["category_automatic_semantic_rates"].values()
    )
    measurable_resources = all(summary[key] is not None for key in (
        "peak_memory_mb", "minimum_mem_available_mb", "swap_delta_mb",
    ))
    summary["screening_gate_passed"] = bool(
        summary["success_rate"] >= SCREENING_LIMITS["success_rate"]
        and summary["timeout_count"] == 0
        and summary["renderable_rate"] >= SCREENING_LIMITS["renderable_rate"]
        and summary["automatic_semantic_rate"] >= SCREENING_LIMITS["semantic_rate"]
        and category_gate
        and summary["unsafe_output_count"] == 0
        and summary["latency_p95_ms"] is not None
        and summary["latency_p95_ms"] <= SCREENING_LIMITS["latency_p95_ms"]
        and measurable_resources
        and summary["peak_memory_mb"] <= SCREENING_LIMITS["peak_memory_mb"]
        and summary["minimum_mem_available_mb"] >= SCREENING_LIMITS["minimum_mem_available_mb"]
        and summary["swap_delta_mb"] <= SCREENING_LIMITS["swap_delta_mb"]
    )
    # Human annotations remain mandatory for the existing production gate.
    summary["production_gate_passed"] = False
    return summary


def prompt_hash() -> str:
    request = build_formula_completion_request("benchmark")
    return hashlib.sha256(json.dumps(request, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def write_results(output: Path, provider: dict[str, Any], rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / f"{provider['name']}.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps([summary], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--providers", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("benchmark-results"))
    parser.add_argument("--profile", choices=("smoke", "full", "determinism", "integration"), default="full")
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--limit", type=int, default=0, help="Smoke-test only; never use for screening promotion")
    args = parser.parse_args()

    providers = json.loads(args.providers.read_text(encoding="utf-8"))
    cases = cases_for_profile(args.profile)
    if args.limit:
        cases = cases[:args.limit]
    summaries = []
    for provider in providers:
        rows, resources = run_cases(provider, cases, args.timeout_seconds, provider.get("server_pid"))
        summary = summarize(provider, rows, resources)
        write_results(args.output / provider["name"], provider, rows, summary)
        summaries.append(summary)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(
        json.dumps({"prompt_hash": prompt_hash(), "profile": args.profile, "providers": summaries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output / "summary.json")


if __name__ == "__main__":
    main()
