"""Linux-only candidate matrix for the 2 vCPU / 2GB formula-model screen."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import signal
import socket
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

from benchmarks.formula.run import (
    ResourceSampler,
    SCREENING_LIMITS,
    _read_status_value,
    cases_for_profile,
    percentile,
    probe_response_formats,
    prompt_hash,
    query_provider,
    run_cases,
    semantic_equivalence_pairs,
    summarize,
)

ROOT = Path(__file__).resolve().parents[2]


def read_meminfo_mb() -> dict[str, float]:
    values: dict[str, float] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value, *_ = line.replace(":", "").split()
        if key in {"MemTotal", "MemAvailable", "SwapTotal", "SwapFree"}:
            values[key] = int(value) / 1024
    return values


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_revision() -> str | None:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, capture_output=True
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def llama_version(binary: str) -> str | None:
    completed = subprocess.run([binary, "--version"], text=True, capture_output=True)
    if completed.returncode != 0:
        return None
    return (completed.stdout or completed.stderr).strip()


def system_metadata(binary: str) -> dict[str, Any]:
    os_release = Path("/etc/os-release")
    cpu_model = None
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        for line in cpuinfo.read_text(encoding="utf-8").splitlines():
            if line.lower().startswith("model name"):
                cpu_model = line.split(":", 1)[1].strip()
                break
    return {
        "platform": platform.platform(),
        "os_release": os_release.read_text(encoding="utf-8") if os_release.exists() else None,
        "cpu_count": os.cpu_count(),
        "cpu_model": cpu_model,
        "memory_mb": read_meminfo_mb(),
        "git_revision": git_revision(),
        "llama_server_version": llama_version(binary),
    }


def assert_port_free(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
        client.settimeout(0.25)
        if client.connect_ex((host, port)) == 0:
            raise RuntimeError(f"{host}:{port} is already occupied; do not benchmark over another service")


def wait_for_port_free(host: str, port: int, timeout_seconds: float = 10) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            assert_port_free(host, port)
            return
        except RuntimeError:
            time.sleep(0.25)
    assert_port_free(host, port)


class LlamaServer:
    def __init__(self, command: list[str], host: str, port: int, log_path: Path) -> None:
        self.command = command
        self.host = host
        self.port = port
        self.log_path = log_path
        self.process: subprocess.Popen[str] | None = None
        self._log_handle: Any | None = None

    def start(self, timeout_seconds: float, on_spawn: Any | None = None) -> float:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = self.log_path.open("w", encoding="utf-8")
        started = time.monotonic()
        self.process = subprocess.Popen(
            self.command, stdout=self._log_handle, stderr=subprocess.STDOUT, text=True,
        )
        if on_spawn:
            on_spawn(self.process.pid)
        health_url = f"http://{self.host}:{self.port}/health"
        while time.monotonic() - started < timeout_seconds:
            if self.process.poll() is not None:
                return_code = self.stop()
                raise RuntimeError(f"llama-server exited with {return_code}; inspect {self.log_path}")
            try:
                if httpx.get(health_url, timeout=0.5).is_success:
                    return time.monotonic() - started
            except httpx.HTTPError:
                pass
            time.sleep(0.25)
        self.stop()
        raise TimeoutError(f"llama-server health check exceeded {timeout_seconds}s")

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None

    def alive(self) -> bool:
        return bool(self.process and self.process.poll() is None)

    def stop(self) -> int | None:
        if not self.process:
            return None
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        return_code = self.process.returncode
        if self._log_handle:
            self._log_handle.close()
            self._log_handle = None
        return return_code


def candidate_command(server: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    return [
        server["binary"], "--host", server.get("host", "127.0.0.1"),
        "--port", str(server.get("port", 8080)), "--model", candidate["model_path"],
        "--alias", server.get("model_alias", "formula-model"),
        "--ctx-size", str(server.get("ctx_size", 1024)),
        "--parallel", "1", "--threads", str(server.get("threads", 2)), "--no-webui",
    ]


def verify_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    path = Path(candidate["model_path"])
    if not path.is_file():
        raise FileNotFoundError(path)
    expected_sha = candidate.get("sha256")
    source_url = candidate.get("source_url")
    revision = candidate.get("revision")
    if (
        not expected_sha
        or not isinstance(expected_sha, str)
        or not re.fullmatch(r"[A-Fa-f0-9]{64}", expected_sha)
    ):
        raise ValueError(f"{candidate['name']} requires a 64-character pinned sha256")
    if not source_url or str(source_url).startswith("REPLACE_"):
        raise ValueError(f"{candidate['name']} requires a verified source_url")
    if not str(source_url).startswith(("https://", "http://")):
        raise ValueError(f"{candidate['name']} source_url must be an HTTP(S) URL")
    if not revision or str(revision).startswith("REPLACE_"):
        raise ValueError(f"{candidate['name']} requires a source revision")
    actual_sha = sha256(path)
    if actual_sha.lower() != expected_sha.lower():
        raise ValueError(f"sha256 mismatch for {candidate['name']}")
    return {
        "model_path": str(path), "model_size_mb": path.stat().st_size / 1024 / 1024,
        "sha256": actual_sha, "source_url": source_url,
        "revision": revision, "quantization": candidate.get("quantization"),
    }


def warm_up(provider: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    with httpx.Client(timeout=8.0) as client:
        for case in cases_for_profile("smoke")[:5]:
            try:
                query_provider(client, provider, case.description)
            except Exception as exc:
                errors.append(type(exc).__name__)
    return errors


def smoke_passed(summary: dict[str, Any]) -> bool:
    return bool(
        summary["unsafe_output_count"] == 0
        and summary["timeout_count"] / max(summary["cases"], 1) <= 0.05
        and summary["renderable_rate"] >= 0.95
    )


def merge_resources(samples: list[dict[str, float | None]]) -> dict[str, float | None]:
    """Aggregate non-overlapping startup and execution resource observations."""
    peaks = [sample["peak_memory_mb"] for sample in samples if sample["peak_memory_mb"] is not None]
    minimums = [sample["minimum_mem_available_mb"] for sample in samples if sample["minimum_mem_available_mb"] is not None]
    swaps = [sample["swap_delta_mb"] for sample in samples if sample["swap_delta_mb"] is not None]
    return {
        "peak_memory_mb": max(peaks) if peaks else None,
        "minimum_mem_available_mb": min(minimums) if minimums else None,
        "swap_delta_mb": sum(swaps) if len(swaps) == len(samples) else None,
    }


def determinism_check(provider: dict[str, Any], pid: int) -> dict[str, Any]:
    first, _ = run_cases(provider, cases_for_profile("determinism"), server_pid=None)
    second, _ = run_cases(provider, cases_for_profile("determinism"), server_pid=None)
    pairs = [(one["latex"], two["latex"]) for one, two in zip(first, second)]
    flags = semantic_equivalence_pairs(pairs)
    return {
        "cases": len(pairs),
        "equivalent_rate": sum(flag["equivalent"] for flag in flags) / len(flags) if flags else 0,
        "passed": bool(flags) and all(flag["equivalent"] for flag in flags),
    }


def _concurrent_request(provider: dict[str, Any], description: str) -> dict[str, Any]:
    with httpx.Client(timeout=8.0) as client:
        try:
            _, latency_ms, _ = query_provider(client, provider, description)
            return {"success": True, "latency_ms": latency_ms, "error_type": None}
        except Exception as exc:
            return {"success": False, "latency_ms": 8000.0, "error_type": type(exc).__name__}


def concurrency_check(provider: dict[str, Any]) -> dict[str, Any]:
    descriptions = [case.description for case in cases_for_profile("integration")]
    futures = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        for description in descriptions:
            futures.extend(executor.submit(_concurrent_request, provider, description) for _ in range(2))
        rows = [future.result() for future in as_completed(futures)]
    latencies = [row["latency_ms"] for row in rows]
    return {
        "requests": len(rows),
        "success_rate": sum(row["success"] for row in rows) / len(rows) if rows else 0,
        "timeout_count": sum(row["error_type"] in {"ReadTimeout", "TimeoutException"} for row in rows),
        "latency_p95_ms": percentile(latencies, .95),
        "passed": bool(rows)
        and all(row["success"] for row in rows)
        and percentile(latencies, .95) is not None
        and percentile(latencies, .95) <= 6000,
    }


def _application_pid(config: dict[str, Any]) -> int | None:
    if config.get("application_pid"):
        return int(config["application_pid"])
    pid_file = config.get("application_pid_file")
    if pid_file and Path(pid_file).is_file():
        return int(Path(pid_file).read_text(encoding="utf-8").strip())
    service = config.get("application_service")
    if service:
        completed = subprocess.run(
            ["systemctl", "show", "--property=MainPID", "--value", service],
            text=True, capture_output=True,
        )
        if completed.returncode == 0 and completed.stdout.strip().isdigit():
            pid = int(completed.stdout.strip())
            return pid or None
    return None


def _application_healthy(config: dict[str, Any], expected_pid: int | None) -> bool:
    current_pid = _application_pid(config)
    if not expected_pid or current_pid != expected_pid or not Path(f"/proc/{expected_pid}").exists():
        return False
    health_url = config.get("health_url")
    if not health_url:
        api_base_url = config.get("api_base_url", "").rstrip("/")
        health_url = api_base_url.removesuffix("/api") + "/health"
    try:
        return httpx.get(health_url, timeout=2).is_success
    except httpx.HTTPError:
        return False


def application_baseline(config: dict[str, Any]) -> dict[str, Any]:
    pid = _application_pid(config)
    healthy = _application_healthy(config, pid)
    latencies: list[float] = []
    health_url = config.get("health_url")
    if not health_url:
        api_base_url = config.get("api_base_url", "").rstrip("/")
        health_url = api_base_url.removesuffix("/api") + "/health"
    if healthy:
        for _ in range(5):
            started = time.perf_counter()
            try:
                response = httpx.get(health_url, timeout=2)
                if response.is_success:
                    latencies.append((time.perf_counter() - started) * 1000)
            except httpx.HTTPError:
                break
    return {
        "pid": pid,
        "rss_mb": _read_status_value(pid, "VmRSS") if pid else None,
        "healthy": healthy,
        "health_url": health_url,
        "idle_api_latency_p50_ms": percentile(latencies, .5),
        "idle_api_latency_p95_ms": percentile(latencies, .95),
    }


class ApplicationMonitor:
    """Poll the existing application without recording request content."""

    def __init__(self, config: dict[str, Any], expected_pid: int, interval_seconds: float = 1.0) -> None:
        self.config = config
        self.expected_pid = expected_pid
        self.interval_seconds = interval_seconds
        self.latencies_ms: list[float] = []
        self.failures = 0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample(self) -> None:
        started = time.perf_counter()
        if _application_healthy(self.config, self.expected_pid):
            self.latencies_ms.append((time.perf_counter() - started) * 1000)
        else:
            self.failures += 1

    def start(self) -> None:
        self._sample()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.wait(self.interval_seconds):
            self._sample()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._sample()
        return {
            "checks": len(self.latencies_ms) + self.failures,
            "failures": self.failures,
            "latency_p95_ms": percentile(self.latencies_ms, .95),
            "passed": self.failures == 0 and bool(self.latencies_ms),
        }


def integration_check(config: dict[str, Any], cases: list[Any], expected_app_pid: int | None) -> dict[str, Any]:
    api_base_url = config.get("api_base_url")
    token = os.getenv(config.get("token_env", ""))
    if not api_base_url or not token or not _application_healthy(config, expected_app_pid):
        return {"status": "not_configured", "passed": False}
    rows = []
    protocol_checks: list[bool] = []
    with httpx.Client(timeout=8.5) as client:
        protocol_checks.append(client.post(
            f"{api_base_url.rstrip('/')}/formula/convert",
            json={"description": "x平方"},
        ).status_code == 401)
        protocol_checks.append(client.post(
            f"{api_base_url.rstrip('/')}/formula/convert",
            headers={"Authorization": f"Bearer {token}"}, json={"description": "x" * 501},
        ).status_code == 422)
        for case in cases:
            started = time.perf_counter()
            try:
                response = client.post(
                    f"{api_base_url.rstrip('/')}/formula/convert",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"description": case.description, "preferred_display": "auto"},
                )
                response.raise_for_status()
                payload = response.json()
                rows.append({
                    "success": (
                        payload.get("display_mode") == case.expected_display
                        and (time.perf_counter() - started) <= 8.0
                    ),
                    "latex": payload.get("latex", ""), "expected": case.expected_latex,
                })
            except Exception as exc:
                rows.append({"success": False, "latex": "", "expected": case.expected_latex, "error_type": type(exc).__name__})
    flags = semantic_equivalence_pairs((row["latex"], row["expected"]) for row in rows)
    passed = bool(rows) and all(protocol_checks) and all(
        row["success"] and flag["equivalent"] for row, flag in zip(rows, flags)
    ) and _application_healthy(config, expected_app_pid)
    return {
        "status": "completed", "cases": len(rows), "passed": passed,
        "protocol_checks_passed": all(protocol_checks),
        "application_healthy_after": _application_healthy(config, expected_app_pid),
    }


def should_run(candidate: dict[str, Any], completed: dict[str, dict[str, Any]], baseline: dict[str, Any]) -> tuple[bool, str | None]:
    condition = candidate.get("run_if")
    if not condition:
        return True, None
    if condition == "all_primary_failed_and_mem_available_1400":
        primary = [result for result in completed.values() if result.get("candidate_role") == "primary"]
        available = baseline["memory_mb"].get("MemAvailable", 0)
        return bool(primary and all(not result.get("screening_gate_passed") for result in primary) and available >= 1400), "memory_or_primary_gate"
    if condition == "base_near_miss":
        base = completed.get(candidate.get("base_candidate", ""), {})
        rate = base.get("automatic_semantic_rate", 0)
        return bool(.93 <= rate < .95 and (base.get("peak_memory_mb") or float("inf")) <= 850), "base_not_near_miss"
    return False, f"unknown_condition:{condition}"


def candidate_gate(summary: dict[str, Any], startup_seconds: list[float], deterministic: dict[str, Any], concurrent: dict[str, Any], integration: dict[str, Any], server_return_code: int | None, application_healthy: bool) -> bool:
    oom_detected = server_return_code in {-signal.SIGKILL, 137}
    return bool(
        summary["screening_gate_passed"]
        and startup_seconds and max(startup_seconds) <= 60
        and deterministic["passed"]
        and concurrent["passed"]
        and integration["passed"]
        and application_healthy
        and not oom_detected
    )


def write_candidate_result(output: Path, result: dict[str, Any]) -> None:
    result["production_gate_passed"] = False
    output.mkdir(parents=True, exist_ok=True)
    (output / "candidate-summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_rows(output: Path, stage: str, rows: list[dict[str, Any]]) -> None:
    (output / f"{stage}.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def select_winner(results: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [result for result in results if result.get("screening_gate_passed")]
    if not eligible:
        return None
    lowest_memory = min(result["peak_memory_mb"] for result in eligible)
    near_memory = [result for result in eligible if result["peak_memory_mb"] - lowest_memory < 64]
    return min(near_memory, key=lambda result: (result["latency_p95_ms"], -result["automatic_semantic_rate"]))


def decision_report(results: list[dict[str, Any]], output: Path) -> None:
    winner = select_winner(results)
    lines = ["# Formula Model Screening Decision", "", "| Candidate | Result | Peak RSS MB | P95 ms | Semantic |", "|---|---:|---:|---:|---:|"]
    for result in results:
        lines.append(
            f"| {result['name']} | {'PASS' if result.get('screening_gate_passed') else result.get('status', 'FAIL')} | "
            f"{result.get('peak_memory_mb', 'n/a')} | {result.get('latency_p95_ms', 'n/a')} | {result.get('automatic_semantic_rate', 'n/a')} |"
        )
    lines.extend([
        "",
        f"Recommendation: `{winner['name']}`" if winner else "Recommendation: no local model passed; use Cloudflare as primary.",
        "",
        "Automated screening only. `production_gate_passed` remains `false` until a separate human semantic review is complete.",
    ])
    (output / "decision.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_candidate(candidate: dict[str, Any], server_config: dict[str, Any], integration: dict[str, Any], output: Path, application: dict[str, Any]) -> dict[str, Any]:
    verification: dict[str, Any] = {}
    provider = {
        "name": candidate["name"],
        "base_url": f"http://{server_config.get('host', '127.0.0.1')}:{server_config.get('port', 8080)}/v1",
        "model": server_config.get("model_alias", "formula-model"),
        "api_key_env": server_config.get("api_key_env", "FORMULA_LOCAL_API_KEY"),
        "llama_cpp": True,
    }
    command = candidate_command(server_config, candidate)
    starts: list[float] = []
    startup_resources: list[dict[str, float | None]] = []
    server: LlamaServer | None = None
    return_code: int | None = None
    sampler: ResourceSampler | None = None
    app_monitor: ApplicationMonitor | None = None
    try:
        verification = verify_candidate(candidate)
        app_monitor = ApplicationMonitor(integration, application["pid"])
        app_monitor.start()
        for attempt in range(3):
            wait_for_port_free(server_config.get("host", "127.0.0.1"), server_config.get("port", 8080))
            server = LlamaServer(command, server_config.get("host", "127.0.0.1"), server_config.get("port", 8080), output / f"server-{attempt + 1}.log")
            startup_sampler = ResourceSampler(None)
            startup_sampler.start()
            try:
                starts.append(server.start(60, lambda pid: setattr(startup_sampler, "pid", pid)))
            finally:
                startup_resources.append(startup_sampler.stop())
            if attempt < 2:
                return_code = server.stop()
                time.sleep(1)

        provider["server_pid"] = server.pid
        # Keep one sampler across warm-up through application integration so a burst
        # cannot hide a short-lived memory or swap regression.
        sampler = ResourceSampler(server.pid)
        sampler.start()
        protocol = probe_response_formats(provider)
        warmup_errors = warm_up(provider)
        smoke_rows, _ = run_cases(provider, cases_for_profile("smoke"), server_pid=server.pid)
        write_rows(output, "smoke", smoke_rows)
        smoke_summary = summarize(provider, smoke_rows)
        if not protocol["passed"] or warmup_errors or not smoke_passed(smoke_summary):
            resources = merge_resources(startup_resources + [sampler.stop()])
            sampler = None
            application_monitor = app_monitor.stop()
            app_monitor = None
            return {
                "name": candidate["name"], "candidate_role": candidate.get("role", "primary"),
                "status": "smoke_failed", "screening_gate_passed": False,
                "warmup_errors": warmup_errors, "smoke": smoke_summary,
                "startup_seconds": starts, "model": verification, "server_command": command,
                "protocol": protocol, "resources": resources,
                "application_monitor": application_monitor,
            }

        full_rows, _ = run_cases(provider, cases_for_profile("full"), server_pid=None)
        write_rows(output, "full", full_rows)
        deterministic = determinism_check(provider, server.pid)
        concurrent = concurrency_check(provider)
        integration_result = integration_check(integration, cases_for_profile("integration"), application.get("pid"))
        resources = merge_resources(startup_resources + [sampler.stop()])
        sampler = None
        application_monitor = app_monitor.stop()
        app_monitor = None
        summary = summarize(provider, full_rows, resources)
        return_code = server.stop()
        summary.update({
            "name": candidate["name"], "candidate_role": candidate.get("role", "primary"),
            "startup_seconds": starts, "startup_max_seconds": max(starts),
            "determinism": deterministic, "concurrency": concurrent, "integration": integration_result,
            "model": verification, "server_command": command,
            "protocol": protocol, "application_monitor": application_monitor,
            "application_healthy_after": (
                application_monitor["passed"]
                and _application_healthy(integration, application.get("pid"))
            ),
        })
        summary["screening_gate_passed"] = candidate_gate(
            summary, starts, deterministic, concurrent, integration_result, return_code,
            summary["application_healthy_after"],
        )
        return summary
    except Exception as exc:
        return {
            "name": candidate["name"], "candidate_role": candidate.get("role", "primary"),
            "status": "error", "screening_gate_passed": False,
            "error_type": type(exc).__name__, "error": str(exc),
            "startup_seconds": starts, "model": verification, "server_command": command,
        }
    finally:
        if sampler:
            sampler.stop()
        if app_monitor:
            app_monitor.stop()
        if server and server.alive():
            server.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if platform.system() != "Linux":
        raise SystemExit("server_matrix.py must run on the target Linux server")

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    server_config = manifest["server"]
    baseline = system_metadata(server_config["binary"])
    application = application_baseline(manifest.get("integration", {}))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "baseline.json").write_text(
        json.dumps({**baseline, "application": application, "prompt_hash": prompt_hash()}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if not application["healthy"]:
        raise SystemExit(
            "the production application must be running and healthy before the server matrix starts"
        )
    completed: dict[str, dict[str, Any]] = {}
    results: list[dict[str, Any]] = []
    for candidate in manifest["candidates"]:
        candidate_output = args.output / candidate["name"]
        previous = candidate_output / "candidate-summary.json"
        if previous.exists() and not args.force:
            result = json.loads(previous.read_text(encoding="utf-8"))
        else:
            allowed, reason = should_run(candidate, completed, baseline)
            if not allowed:
                result = {
                    "name": candidate["name"], "candidate_role": candidate.get("role", "primary"),
                    "status": "skipped", "skip_reason": reason, "screening_gate_passed": False,
                }
            else:
                result = run_candidate(candidate, server_config, manifest.get("integration", {}), candidate_output, application)
            write_candidate_result(candidate_output, result)
        completed[candidate["name"]] = result
        results.append(result)
    (args.output / "summary.json").write_text(
        json.dumps({
            "baseline": baseline, "application": application,
            "prompt_hash": prompt_hash(), "production_gate_passed": False,
            "candidates": results,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    decision_report(results, args.output)
    print(args.output / "decision.md")


if __name__ == "__main__":
    main()
