# -*- coding: utf-8 -*-
"""
Run a two-chapter v4.4 high-math extraction batch.

The core extraction scripts are single-section capable. This runner filters
leaf sections by chapter, runs section-level LLM steps in parallel, merges their
JSONL outputs deterministically, then runs Step 5-8 for the batch.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from llm_env import load_env_value


SCRIPT_DIR = Path(__file__).resolve().parent
PYTHON = sys.executable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v4.4 lower-volume chapter batch.")
    parser.add_argument("--config", type=Path, default=SCRIPT_DIR / "v4_4_gaoshu_config.json")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--chapters", nargs="+", type=int, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--review-workers", type=int, default=4)
    parser.add_argument("--timeout", type=str, default="300")
    parser.add_argument("--skip-step7", action="store_true")
    parser.add_argument(
        "--resume-from",
        choices=["step1", "step2", "step3", "step3e", "step4a", "step4b", "step4e", "step5", "step6", "step7", "step8"],
        default="step1",
        help="Resume an existing batch from the named step. step1 refuses to overwrite an existing output directory.",
    )
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


def section_ids_from_jsonl(path: Path) -> list[str]:
    rows = read_jsonl(path, required=False)
    ids = sorted({str(row.get("section_node_id") or "") for row in rows if row.get("section_node_id")})
    return ids


def relation_section_ids(edges_path: Path, rule_cases_path: Path) -> list[str]:
    ids = set(section_ids_from_jsonl(edges_path))
    ids.update(section_ids_from_jsonl(rule_cases_path))
    return sorted(ids)


STEP_ORDER = {
    "step1": 1,
    "step2": 2,
    "step3": 3,
    "step3e": 4,
    "step4a": 5,
    "step4b": 6,
    "step4e": 7,
    "step5": 8,
    "step6": 9,
    "step7": 10,
    "step8": 11,
}


def should_run(args: argparse.Namespace, step: str) -> bool:
    return STEP_ORDER[step] >= STEP_ORDER[args.resume_from]


def model_for(env_name: str, fallback: str) -> str:
    return load_env_value(env_name) or fallback


def run(cmd: list[str], cwd: Path = SCRIPT_DIR) -> str:
    started = time.time()
    proc = subprocess.run(cmd, cwd=str(cwd), text=True, encoding="utf-8", errors="replace", capture_output=True)
    elapsed = time.time() - started
    if proc.returncode != 0:
        message = "\n".join(
            [
                f"Command failed after {elapsed:.1f}s:",
                " ".join(cmd),
                "--- stdout ---",
                proc.stdout[-4000:],
                "--- stderr ---",
                proc.stderr[-4000:],
            ]
        )
        raise RuntimeError(message)
    output = (proc.stdout + proc.stderr).strip()
    if output:
        print(output[-3000:], flush=True)
    print(f"[OK] elapsed={elapsed:.1f}s {' '.join(cmd[:2])}", flush=True)
    return output


def run_section_step(
    script: str,
    section_id: str,
    out_dir: Path,
    base_args: list[str],
    output_specs: dict[str, str],
    timeout: str,
) -> tuple[str, bool, str]:
    section_dir = out_dir / "parallel" / Path(script).stem / section_id.replace(":", "_")
    section_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        PYTHON,
        str(SCRIPT_DIR / script),
        *base_args,
        "--chunk-id",
        section_id,
        "--timeout",
        timeout,
    ]
    for flag, filename in output_specs.items():
        cmd.extend([flag, str(section_dir / filename)])
    try:
        run(cmd)
        return section_id, True, ""
    except Exception as exc:  # noqa: BLE001 - keep other sections running; caller records failures.
        error_path = section_dir / "error.txt"
        error_path.write_text(str(exc), encoding="utf-8")
        return section_id, False, str(exc)[-1000:]


def parallel_sections(
    label: str,
    script: str,
    section_ids: list[str],
    out_dir: Path,
    workers: int,
    base_args: list[str],
    output_specs: dict[str, str],
    merge_specs: dict[str, str],
    timeout: str,
) -> None:
    print(f"[INFO] {label} sections={len(section_ids)} workers={workers}", flush=True)
    pending = list(section_ids)
    failures: list[tuple[str, str]] = []
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        if not pending:
            break
        failures = []
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(run_section_step, script, section_id, out_dir, base_args, output_specs, timeout): section_id
                for section_id in pending
            }
            for future in as_completed(futures):
                section_id, ok, message = future.result()
                if ok:
                    print(f"[OK] {label} {section_id}", flush=True)
                else:
                    failures.append((section_id, message))
                    print(f"[FAIL] {label} {section_id}: {message[:300]}", flush=True)
        pending = [section_id for section_id, _ in failures]
        if pending and attempt < max_attempts:
            print(f"[RETRY] {label} attempt {attempt + 1}/{max_attempts} for {len(pending)} sections: {pending}", flush=True)
            time.sleep(5)
    if failures:
        fail_path = out_dir / f"{label}_failures.jsonl"
        write_jsonl(fail_path, [{"section_node_id": sid, "error": msg} for sid, msg in failures])
        raise RuntimeError(f"{label} failed for {len(failures)} sections; see {fail_path}")

    parallel_root = out_dir / "parallel" / Path(script).stem
    for merged_name, per_section_name in merge_specs.items():
        rows: list[dict[str, Any]] = []
        for section_id in section_ids:
            section_dir = parallel_root / section_id.replace(":", "_")
            rows.extend(read_jsonl(section_dir / per_section_name, required=False))
        write_jsonl(out_dir / merged_name, rows)
        print(f"[OK] merged {merged_name}: {len(rows)}", flush=True)


def filter_leaf_sections(config: Path, out_dir: Path, chapters: set[int]) -> list[dict[str, Any]]:
    all_leaf = out_dir / "leaf_sections_all.jsonl"
    run(
        [
            PYTHON,
            str(SCRIPT_DIR / "01_build_textbook_tree.py"),
            "--config",
            str(config),
            "--output-dir",
            str(out_dir / "tree_all"),
        ]
    )
    source_leaf = out_dir / "tree_all" / "leaf_sections.jsonl"
    if not source_leaf.exists():
        source_leaf = out_dir / "tree_all" / "leaf_sections_all.jsonl"
    shutil.copyfile(source_leaf, all_leaf)
    rows = read_jsonl(all_leaf)
    selected = [row for row in rows if int(row.get("chapter_order") or 0) in chapters]
    selected.sort(key=lambda row: (int(row.get("chapter_order") or 0), int(row.get("section_order") or 0), int(row.get("subsection_order") or 0), int(row.get("line_start") or 0)))
    write_jsonl(out_dir / "leaf_sections.jsonl", selected)
    print(f"[INFO] selected leaf sections={len(selected)} chapters={sorted(chapters)}", flush=True)
    return selected


def load_existing_leaf_sections(out_dir: Path) -> list[dict[str, Any]]:
    leaf_path = out_dir / "leaf_sections.jsonl"
    rows = read_jsonl(leaf_path)
    print(f"[INFO] loaded existing leaf sections={len(rows)}", flush=True)
    return rows


def main() -> None:
    args = parse_args()
    out_dir: Path = args.out_dir
    if out_dir.exists() and args.resume_from == "step1":
        raise RuntimeError(f"Output dir already exists, refusing to overwrite: {out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    chapters = set(args.chapters)

    if should_run(args, "step1"):
        sections = filter_leaf_sections(args.config, out_dir, chapters)
    else:
        sections = load_existing_leaf_sections(out_dir)
    core_sections = [str(row["section_node_id"]) for row in sections if row.get("source_scope") == "core_content"]
    print(f"[INFO] core sections={len(core_sections)}", flush=True)

    common = ["--config", str(args.config), "--leaf-sections", str(out_dir / "leaf_sections.jsonl")]
    summary_model = model_for("OPENAI_SUMMARY_MODEL", "gpt-5.4-mini")
    node_model = model_for("OPENAI_NODE_MODEL", "gpt-5.4")
    edge_model = model_for("OPENAI_EDGE_MODEL", "gpt-5.5")
    rule_case_model = model_for("OPENAI_RULE_CASE_MODEL", edge_model)
    node_audit_model = model_for("OPENAI_NODE_AUDIT_MODEL", "gpt-5.5")
    relation_audit_model = model_for("OPENAI_RELATION_AUDIT_MODEL", "gpt-5.5")
    review_model = model_for("OPENAI_REVIEW_MODEL", "gpt-5.5")
    print(
        "[INFO] models "
        f"summary={summary_model} node={node_model} edge={edge_model} "
        f"rule_case={rule_case_model} node_audit={node_audit_model} "
        f"relation_audit={relation_audit_model} review={review_model}",
        flush=True,
    )

    if should_run(args, "step2"):
        parallel_sections(
            "step2",
            "02_generate_section_summaries.py",
            core_sections,
            out_dir,
            args.workers,
            [*common, "--model", summary_model],
            {"--output": "section_summaries.jsonl", "--warnings": "section_summary_warnings.jsonl"},
            {"section_summaries.jsonl": "section_summaries.jsonl", "section_summary_warnings.jsonl": "section_summary_warnings.jsonl"},
            args.timeout,
        )

    if should_run(args, "step3"):
        parallel_sections(
            "step3",
            "03_extract_explicit_nodes.py",
            core_sections,
            out_dir,
            args.workers,
            [*common, "--summaries", str(out_dir / "section_summaries.jsonl"), "--model", node_model],
            {
                "--raw-output": "raw_explicit_node_candidates.jsonl",
                "--nodes": "nodes.jsonl",
                "--review": "node_pre_audit_review_queue.jsonl",
                "--warnings": "node_extraction_warnings.jsonl",
                "--report": "node_extraction_report.md",
            },
            {
                "raw_explicit_node_candidates.jsonl": "raw_explicit_node_candidates.jsonl",
                "nodes.jsonl": "nodes.jsonl",
                "node_pre_audit_review_queue.jsonl": "node_pre_audit_review_queue.jsonl",
                "node_extraction_warnings.jsonl": "node_extraction_warnings.jsonl",
            },
            args.timeout,
        )

    node_sections = section_ids_from_jsonl(out_dir / "nodes.jsonl")
    print(f"[INFO] node sections={len(node_sections)}", flush=True)

    if should_run(args, "step3e"):
        parallel_sections(
            "step3e",
            "03e_audit_nodes.py",
            node_sections,
            out_dir,
            args.workers,
            [*common, "--nodes", str(out_dir / "nodes.jsonl"), "--model", node_audit_model, "--batch-size", "12"],
            {
                "--raw-output": "raw_node_quality_audit.jsonl",
                "--audited-nodes": "nodes_audited.jsonl",
                "--review": "node_review_queue.jsonl",
                "--warnings": "node_quality_audit_warnings.jsonl",
                "--report": "node_quality_audit_report.md",
            },
            {
                "raw_node_quality_audit.jsonl": "raw_node_quality_audit.jsonl",
                "nodes_audited.jsonl": "nodes_audited.jsonl",
                "node_review_queue.jsonl": "node_review_queue.jsonl",
                "node_quality_audit_warnings.jsonl": "node_quality_audit_warnings.jsonl",
            },
            args.timeout,
        )

    if should_run(args, "step4a"):
        parallel_sections(
            "step4a",
            "04_extract_explicit_edges.py",
            core_sections,
            out_dir,
            args.workers,
            [*common, "--nodes", str(out_dir / "nodes_audited.jsonl"), "--model", edge_model],
            {
                "--raw-output": "raw_explicit_edge_candidates.jsonl",
                "--edges": "edges.jsonl",
                "--review": "edge_pre_audit_review_queue.jsonl",
                "--warnings": "edge_extraction_warnings.jsonl",
                "--report": "edge_extraction_report.md",
            },
            {
                "raw_explicit_edge_candidates.jsonl": "raw_explicit_edge_candidates.jsonl",
                "edges.jsonl": "edges.jsonl",
                "edge_pre_audit_review_queue.jsonl": "edge_pre_audit_review_queue.jsonl",
                "edge_extraction_warnings.jsonl": "edge_extraction_warnings.jsonl",
            },
            args.timeout,
        )

    if should_run(args, "step4b"):
        parallel_sections(
            "step4b",
            "04b_extract_rule_cases.py",
            core_sections,
            out_dir,
            args.workers,
            [*common, "--nodes", str(out_dir / "nodes_audited.jsonl"), "--model", rule_case_model],
            {
                "--raw-output": "raw_rule_case_candidates.jsonl",
                "--rule-cases": "rule_cases.jsonl",
                "--review": "rule_case_pre_audit_review_queue.jsonl",
                "--warnings": "rule_case_extraction_warnings.jsonl",
                "--report": "rule_case_extraction_report.md",
            },
            {
                "raw_rule_case_candidates.jsonl": "raw_rule_case_candidates.jsonl",
                "rule_cases.jsonl": "rule_cases.jsonl",
                "rule_case_pre_audit_review_queue.jsonl": "rule_case_pre_audit_review_queue.jsonl",
                "rule_case_extraction_warnings.jsonl": "rule_case_extraction_warnings.jsonl",
            },
            args.timeout,
        )

    relation_sections = relation_section_ids(out_dir / "edges.jsonl", out_dir / "rule_cases.jsonl")
    print(f"[INFO] relation sections={len(relation_sections)}", flush=True)

    if should_run(args, "step4e"):
        parallel_sections(
            "step4e",
            "04e_audit_relations.py",
            relation_sections,
            out_dir,
            args.workers,
            [
                *common,
                "--nodes",
                str(out_dir / "nodes_audited.jsonl"),
                "--edges",
                str(out_dir / "edges.jsonl"),
                "--rule-cases",
                str(out_dir / "rule_cases.jsonl"),
                "--model",
                relation_audit_model,
                "--batch-size",
                "10",
            ],
            {
                "--raw-output": "raw_relation_quality_audit.jsonl",
                "--audited-edges": "edges_audited.jsonl",
                "--audited-rule-cases": "rule_cases_audited.jsonl",
                "--edge-review": "edge_review_queue.jsonl",
                "--rule-case-review": "rule_case_review_queue.jsonl",
                "--warnings": "relation_quality_audit_warnings.jsonl",
                "--report": "relation_quality_audit_report.md",
            },
            {
                "raw_relation_quality_audit.jsonl": "raw_relation_quality_audit.jsonl",
                "edges_audited.jsonl": "edges_audited.jsonl",
                "rule_cases_audited.jsonl": "rule_cases_audited.jsonl",
                "edge_review_queue.jsonl": "edge_review_queue.jsonl",
                "rule_case_review_queue.jsonl": "rule_case_review_queue.jsonl",
                "relation_quality_audit_warnings.jsonl": "relation_quality_audit_warnings.jsonl",
            },
            args.timeout,
        )

    if should_run(args, "step5"):
        run(
            [
                PYTHON,
                str(SCRIPT_DIR / "05_global_normalize_and_review.py"),
                "--nodes",
                str(out_dir / "nodes_audited.jsonl"),
                "--edges",
                str(out_dir / "edges_audited.jsonl"),
                "--rule-case-candidates",
                str(out_dir / "rule_cases_audited.jsonl"),
                "--main-nodes-out",
                str(out_dir / "kg_main_nodes.jsonl"),
                "--main-edges-out",
                str(out_dir / "kg_main_edges.jsonl"),
                "--rule-cases-out",
                str(out_dir / "kg_rule_cases.jsonl"),
                "--review-nodes-out",
                str(out_dir / "step5_review_nodes.jsonl"),
                "--review-edges-out",
                str(out_dir / "step5_review_edges.jsonl"),
                "--review-rule-cases-out",
                str(out_dir / "step5_review_rule_cases.jsonl"),
                "--rejected-out",
                str(out_dir / "step5_rejected_items.jsonl"),
                "--report",
                str(out_dir / "step5_global_normalization_report.md"),
                "--review-md",
                str(out_dir / "step5_review_checklist.md"),
            ]
        )
        run(
            [
                PYTHON,
                str(SCRIPT_DIR / "05a_generate_merge_candidates.py"),
                "--main-nodes",
                str(out_dir / "kg_main_nodes.jsonl"),
                "--review-nodes",
                str(out_dir / "step5_review_nodes.jsonl"),
                "--main-edges",
                str(out_dir / "kg_main_edges.jsonl"),
                "--review-edges",
                str(out_dir / "step5_review_edges.jsonl"),
                "--out",
                str(out_dir / "step5_merge_candidates.jsonl"),
                "--report",
                str(out_dir / "merge_candidate_report.md"),
            ]
        )
        run(
            [
                PYTHON,
                str(SCRIPT_DIR / "05b_prepare_merge_review.py"),
                "--merge-candidates",
                str(out_dir / "step5_merge_candidates.jsonl"),
                "--out",
                str(out_dir / "step5_review_merge_candidates.jsonl"),
                "--checklist",
                str(out_dir / "step5_merge_review_checklist.md"),
            ]
        )

    if should_run(args, "step6"):
        run(
            [
                PYTHON,
                str(SCRIPT_DIR / "06_build_layered_candidates.py"),
                "--main-nodes",
                str(out_dir / "kg_main_nodes.jsonl"),
                "--main-edges",
                str(out_dir / "kg_main_edges.jsonl"),
                "--rule-cases",
                str(out_dir / "kg_rule_cases.jsonl"),
                "--review-nodes",
                str(out_dir / "step5_review_nodes.jsonl"),
                "--review-edges",
                str(out_dir / "step5_review_edges.jsonl"),
                "--review-rule-cases",
                str(out_dir / "step5_review_rule_cases.jsonl"),
                "--review-merge-candidates",
                str(out_dir / "step5_review_merge_candidates.jsonl"),
                "--rejected",
                str(out_dir / "step5_rejected_items.jsonl"),
                "--out-dir",
                str(out_dir / "step6_layers"),
            ]
        )

    if should_run(args, "step7"):
        run([PYTHON, str(SCRIPT_DIR / "07a_build_review_items.py"), "--layer-dir", str(out_dir / "step6_layers"), "--out-dir", str(out_dir / "step7_review")])
        if not args.skip_step7:
            run([PYTHON, str(SCRIPT_DIR / "07b_ai_review_suggestions.py"), "--config", str(args.config), "--review-items", str(out_dir / "step7_review" / "review_items.jsonl"), "--out", str(out_dir / "step7_review" / "ai_review_decisions.jsonl"), "--summary", str(out_dir / "step7_review" / "ai_review_summary.md"), "--model", review_model, "--batch-size", "8", "--max-workers", str(args.review_workers), "--timeout", args.timeout, "--resume", "--allow-pro"])
            run([
                PYTHON,
                str(SCRIPT_DIR / "07c_validate_review_decisions.py"),
                "--layer-dir",
                str(out_dir / "step6_layers"),
                "--ai-decisions",
                str(out_dir / "step7_review" / "ai_review_decisions.jsonl"),
                "--validated-out",
                str(out_dir / "step7_review" / "validated_review_decisions.jsonl"),
                "--conflict-items-out",
                str(out_dir / "step7_review" / "conflict_review_items.jsonl"),
                "--conflict-decisions-out",
                str(out_dir / "step7_review" / "conflict_review_decisions.jsonl"),
                "--errors-out",
                str(out_dir / "step7_review" / "decision_validation_errors.jsonl"),
                "--summary",
                str(out_dir / "step7_review" / "decision_validation_summary.md"),
            ])
            run([
                PYTHON,
                str(SCRIPT_DIR / "07d_apply_review_decisions.py"),
                "--layer-dir",
                str(out_dir / "step6_layers"),
                "--decisions",
                str(out_dir / "step7_review" / "validated_review_decisions.jsonl"),
                "--out-dir",
                str(out_dir / "step7_final"),
            ])
            run([PYTHON, str(SCRIPT_DIR / "07e_build_review_report.py"), "--review-dir", str(out_dir / "step7_final"), "--audit-dir", str(out_dir / "step7_review"), "--report", str(out_dir / "step7_final" / "review_report.md")])

    if should_run(args, "step8") and not args.skip_step7:
        run([PYTHON, str(SCRIPT_DIR / "08a_assemble_final_graph.py"), "--review-dir", str(out_dir / "step7_final"), "--out-dir", str(out_dir / "step8_final_graph")])

    print(f"[DONE] batch chapters={sorted(chapters)} out_dir={out_dir}", flush=True)


if __name__ == "__main__":
    main()
