"""
v4.4 Step 7E: build review report and trace index.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REVIEW_DIR = SCRIPT_DIR / "中间产物" / "step7_review"
DEFAULT_REPORT = DEFAULT_REVIEW_DIR / "review_report.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build v4.4 Step 7E review report.")
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument(
        "--audit-dir",
        type=Path,
        default=None,
        help="Directory containing Step 7A-7C files. If omitted, infer a sibling step7_review directory when needed.",
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def read_jsonl(path: Path, required: bool = False) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSONL not found: {path}")
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def count_by(rows: list[dict[str, Any]], *fields: str) -> Counter[tuple[str, ...]]:
    return Counter(tuple(str(row.get(field) or "") for field in fields) for row in rows)


def infer_audit_dir(review_dir: Path, audit_dir: Path | None) -> Path:
    if audit_dir is not None:
        return audit_dir
    if (review_dir / "review_items.jsonl").exists():
        return review_dir
    sibling = review_dir.parent / "step7_review"
    if sibling.exists():
        return sibling
    return review_dir


def write_report(path: Path, review_dir: Path, audit_dir: Path | None = None) -> None:
    source_review_dir = infer_audit_dir(review_dir, audit_dir)

    review_items = read_jsonl(source_review_dir / "review_items.jsonl")
    ai_decisions = read_jsonl(source_review_dir / "ai_review_decisions.jsonl")
    validated = read_jsonl(source_review_dir / "validated_review_decisions.jsonl")
    conflict_items = read_jsonl(source_review_dir / "conflict_review_items.jsonl")
    conflict_decisions = read_jsonl(source_review_dir / "conflict_review_decisions.jsonl")
    errors = read_jsonl(source_review_dir / "decision_validation_errors.jsonl")

    approved_nodes = read_jsonl(review_dir / "approved_nodes.jsonl")
    approved_app_nodes = read_jsonl(review_dir / "approved_application_nodes.jsonl")
    approved_edges = read_jsonl(review_dir / "approved_edges.jsonl")
    approved_app_edges = read_jsonl(review_dir / "approved_application_edges.jsonl")
    approved_rule_cases = read_jsonl(review_dir / "approved_rule_cases.jsonl")
    merge_plans = read_jsonl(review_dir / "merge_plans.jsonl")
    archive = read_jsonl(review_dir / "review_archive.jsonl")
    deferred = read_jsonl(review_dir / "deferred_items.jsonl")
    trace = read_jsonl(review_dir / "decision_trace.jsonl")

    lines = [
        "# v4.4 Step 7E 审核报告与决策追踪",
        "",
        "Step 7 只负责审核与决策落盘，不执行最终图谱合并，不生成 KnowledgeGroup。",
        "",
        f"- Step 7A-7C 来源目录：`{source_review_dir}`",
        f"- Step 7D 落地目录：`{review_dir}`",
        "",
        "## 文件清单",
        "",
        "- review_items.jsonl",
        "- ai_review_decisions.jsonl",
        "- validated_review_decisions.jsonl",
        "- conflict_review_items.jsonl",
        "- conflict_review_decisions.jsonl",
        "- decision_validation_errors.jsonl",
        "- approved_nodes.jsonl",
        "- approved_edges.jsonl",
        "- approved_application_nodes.jsonl",
        "- approved_application_edges.jsonl",
        "- approved_rule_cases.jsonl",
        "- merge_plans.jsonl",
        "- review_archive.jsonl",
        "- deferred_items.jsonl",
        "- decision_trace.jsonl",
        "",
        "## 总览",
        "",
        f"- review_items: {len(review_items)}",
        f"- ai_review_decisions: {len(ai_decisions)}",
        f"- validated_review_decisions: {len(validated)}",
        f"- conflict_review_items: {len(conflict_items)}",
        f"- conflict_review_decisions: {len(conflict_decisions)}",
        f"- decision_validation_errors: {len(errors)}",
        f"- approved_nodes: {len(approved_nodes)}",
        f"- approved_application_nodes: {len(approved_app_nodes)}",
        f"- approved_edges: {len(approved_edges)}",
        f"- approved_application_edges: {len(approved_app_edges)}",
        f"- approved_rule_cases: {len(approved_rule_cases)}",
        f"- merge_plans: {len(merge_plans)}",
        f"- review_archive: {len(archive)}",
        f"- deferred_items: {len(deferred)}",
        f"- decision_trace: {len(trace)}",
        "",
        "## 审核项类型",
    ]
    for (kind,), count in sorted(count_by(review_items, "item_kind").items()):
        lines.append(f"- {kind}: {count}")

    lines.extend(["", "## AI 建议分布"])
    for (kind, action), count in sorted(count_by(ai_decisions, "item_kind", "action").items()):
        lines.append(f"- {kind} / {action}: {count}")

    lines.extend(["", "## 校验后决策分布"])
    for (kind, action, status), count in sorted(count_by(validated, "item_kind", "action", "validation_status").items()):
        lines.append(f"- {kind} / {action} / {status}: {count}")

    if errors:
        lines.extend(["", "## 校验错误样例"])
        for row in errors[:50]:
            lines.append(f"- {json.dumps(row, ensure_ascii=False)}")

    lines.extend(["", "## Step 8A 输入"])
    lines.append("Step 8A 将读取 approved_* 与 merge_plans.jsonl，执行最终图谱组装、合并计划和 KnowledgeGroup 生成。")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    write_report(args.report, args.review_dir, args.audit_dir)
    print(f"[OK] review report -> {args.report}")


if __name__ == "__main__":
    main()
