import unittest
from collections import Counter
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import httpx

from benchmarks.formula.dataset import build_cases
from benchmarks.formula.run import (
    ResourceSampler,
    _request_payload,
    cases_for_profile,
    query_provider,
    probe_response_formats,
    semantic_equivalence_pairs,
    summarize,
)
from benchmarks.formula.server_matrix import (
    application_baseline,
    candidate_command,
    merge_resources,
    select_winner,
    should_run,
    verify_candidate,
)


class FormulaBenchmarkDatasetTests(unittest.TestCase):
    def test_fixed_suite_has_at_least_300_balanced_unique_cases(self) -> None:
        cases = build_cases()
        self.assertGreaterEqual(len(cases), 300)
        self.assertEqual(len({case.id for case in cases}), len(cases))
        self.assertEqual(set(Counter(case.category for case in cases).values()), {25})

    def test_stage_profiles_have_fixed_balanced_sizes(self) -> None:
        self.assertEqual(len(cases_for_profile("smoke")), 39)
        self.assertEqual(len(cases_for_profile("determinism")), 65)
        self.assertEqual(len(cases_for_profile("integration")), 26)
        self.assertEqual(set(Counter(case.category for case in cases_for_profile("smoke")).values()), {3})


class FormulaBenchmarkProtocolTests(unittest.TestCase):
    def test_llama_cpp_payload_disables_thinking_in_chat_template(self) -> None:
        payload = _request_payload(
            {"model": "formula-model", "llama_cpp": True},
            "x骞虫柟",
            {"type": "json_object"},
        )

        self.assertFalse(payload["enable_thinking"])
        self.assertEqual(payload["chat_template_kwargs"], {"enable_thinking": False})

    def test_protocol_probe_allows_json_object_only_servers(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            if payload["response_format"]["type"] == "json_schema":
                return httpx.Response(400, json={"error": "unsupported"})
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"latex":"x^2"}'}}]})

        provider = {"name": "local", "base_url": "http://formula.test/v1", "model": "formula-model"}
        mock_client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch("benchmarks.formula.run.httpx.Client") as client_class:
            client_class.return_value.__enter__.return_value = mock_client
            result = probe_response_formats(provider)
        mock_client.close()
        self.assertTrue(result["passed"])
        self.assertTrue(result["fallback_required"])

    def test_schema_rejection_retries_json_object_with_production_payload(self) -> None:
        formats: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            payload = json.loads(request.content)
            formats.append(payload["response_format"]["type"])
            self.assertEqual(payload["temperature"], 0)
            self.assertEqual(payload["max_tokens"], 128)
            self.assertFalse(payload["enable_thinking"])
            if len(formats) == 1:
                return httpx.Response(400, json={"error": "schema unsupported"})
            return httpx.Response(200, json={"choices": [{"message": {"content": '{"latex":"x^2"}'}}]})

        provider = {"name": "local", "base_url": "http://formula.test/v1", "model": "formula-model"}
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            latex, _, response_format = query_provider(client, provider, "x平方")
        self.assertEqual(latex, "x^2")
        self.assertEqual(response_format, "json_object")
        self.assertEqual(formats, ["json_schema", "json_object"])


class FormulaSemanticTests(unittest.TestCase):
    def test_automatic_semantics_handles_aliases_and_commutative_math(self) -> None:
        flags = semantic_equivalence_pairs([
            (r"\frac{a}{b}", r"\dfrac{a}{b}"),
            ("x+y", "y+x"),
            (r"\begin{pmatrix}a&b\\c&d\end{pmatrix}", r"\begin{bmatrix}a&b\\c&d\end{bmatrix}"),
        ])
        self.assertTrue(flags[0]["equivalent"])
        self.assertTrue(flags[1]["equivalent"])
        self.assertFalse(flags[2]["equivalent"])

    def test_summary_requires_every_category_to_pass(self) -> None:
        rows = []
        for index in range(13):
            rows.append({
                "status": "success", "category": f"category-{index}", "latency_ms": 100,
                "exact_match": True, "renderable": True, "automatic_semantic_correct": True,
                "error_type": None,
            })
        provider = {"name": "candidate"}
        resources = {"peak_memory_mb": 900, "minimum_mem_available_mb": 300, "swap_delta_mb": 0}
        self.assertTrue(summarize(provider, rows, resources)["screening_gate_passed"])
        rows[0]["automatic_semantic_correct"] = False
        self.assertFalse(summarize(provider, rows, resources)["screening_gate_passed"])


class FormulaServerMatrixTests(unittest.TestCase):
    def test_startup_sampler_can_attach_after_process_spawn(self) -> None:
        sampler = ResourceSampler(None)
        sampler.pid = 1234
        self.assertEqual(sampler.pid, 1234)

    def test_application_baseline_reads_process_rss(self) -> None:
        with (
            patch("benchmarks.formula.server_matrix._application_healthy", return_value=False),
            patch("benchmarks.formula.server_matrix._read_status_value", return_value=12.5) as read_status,
        ):
            baseline = application_baseline({"application_pid": 1234, "health_url": "http://app.test/health"})

        read_status.assert_called_once_with(1234, "VmRSS")
        self.assertEqual(baseline["rss_mb"], 12.5)
        self.assertFalse(baseline["healthy"])

    def test_server_command_is_cpu_constrained(self) -> None:
        command = candidate_command(
            {"binary": "/opt/llama-server", "threads": 2, "ctx_size": 1024},
            {"model_path": "/models/formula.gguf"},
        )
        self.assertIn("--parallel", command)
        self.assertIn("--threads", command)
        self.assertNotIn("--mlock", command)
        self.assertEqual(command[command.index("--threads") + 1], "2")

    def test_candidate_requires_verified_metadata_and_sha256(self) -> None:
        with TemporaryDirectory() as directory:
            model = Path(directory) / "candidate.gguf"
            model.write_bytes(b"test-model")
            with self.assertRaises(ValueError):
                verify_candidate({
                    "name": "candidate", "model_path": str(model), "sha256": "not-a-sha",
                    "source_url": "https://example.test/model", "revision": "abc123",
                })

    def test_conditional_candidates_are_only_run_when_eligible(self) -> None:
        baseline = {"memory_mb": {"MemAvailable": 1500}}
        completed = {
            "small": {"candidate_role": "primary", "screening_gate_passed": False},
            "medium": {"candidate_role": "primary", "screening_gate_passed": False},
        }
        allowed, _ = should_run({"run_if": "all_primary_failed_and_mem_available_1400"}, completed, baseline)
        self.assertTrue(allowed)
        completed["medium"]["screening_gate_passed"] = True
        allowed, _ = should_run({"run_if": "all_primary_failed_and_mem_available_1400"}, completed, baseline)
        self.assertFalse(allowed)

    def test_ranking_never_selects_a_smaller_failed_model(self) -> None:
        winner = select_winner([
            {
                "name": "small-failed", "screening_gate_passed": False,
                "peak_memory_mb": 400, "latency_p95_ms": 100, "automatic_semantic_rate": .80,
            },
            {
                "name": "passing", "screening_gate_passed": True,
                "peak_memory_mb": 700, "latency_p95_ms": 1000, "automatic_semantic_rate": .96,
            },
        ])
        self.assertEqual(winner["name"], "passing")

    def test_models_within_64mb_are_ranked_by_latency(self) -> None:
        winner = select_winner([
            {
                "name": "lowest-rss", "screening_gate_passed": True,
                "peak_memory_mb": 700, "latency_p95_ms": 1500, "automatic_semantic_rate": .98,
            },
            {
                "name": "faster-nearby", "screening_gate_passed": True,
                "peak_memory_mb": 750, "latency_p95_ms": 900, "automatic_semantic_rate": .96,
            },
        ])
        self.assertEqual(winner["name"], "faster-nearby")

    def test_startup_and_execution_resources_are_combined_conservatively(self) -> None:
        result = merge_resources([
            {"peak_memory_mb": 700, "minimum_mem_available_mb": 500, "swap_delta_mb": 2},
            {"peak_memory_mb": 680, "minimum_mem_available_mb": 300, "swap_delta_mb": 3},
        ])
        self.assertEqual(result, {
            "peak_memory_mb": 700, "minimum_mem_available_mb": 300, "swap_delta_mb": 5,
        })


if __name__ == "__main__":
    unittest.main()
