"""
v4.4 Step 5B: prepare merge candidates for review.

Step 5B is deliberately conservative. It converts Step 5A possible-merge pairs
into review records and does not modify nodes, edges, aliases, or ids.
Accepted merges are applied only in Step 7B after an explicit review decision.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DIR = SCRIPT_DIR / "中间产物"

DEFAULT_CANDIDATES = DEFAULT_DIR / "merge_candidates.jsonl"
DEFAULT_OUT = DEFAULT_DIR / "step5_review_merge_candidates.jsonl"
DEFAULT_CHECKLIST = DEFAULT_DIR / "step5_merge_review_checklist.md"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare v4.4 Step 5B merge-candidate review records.")
    parser.add_argument("--merge-candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--checklist", type=Path, default=DEFAULT_CHECKLIST)
    parser.add_argument("--min-score", type=float, default=0.74)
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


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def prepare_review_item(candidate: dict[str, Any], min_score: float) -> dict[str, Any]:
    item = dict(candidate)
    item["item_kind"] = "merge_candidate"
    item["item_type"] = "MergeCandidate"
    item["kg_layer"] = "review_pending_merge"
    item["step5_status"] = "review"
    item["review_status"] = "review"
    item["step5b_policy"] = "review_only_no_auto_merge"
    item["step5b_generated_at"] = now_iso()
    reasons = list(item.get("candidate_reason") or [])
    score = float(item.get("merge_score") or 0)
    if score < min_score:
        reasons.append(f"综合相似度低于当前建议阈值 {min_score}，仍保留为低优先级待审候选。")
        item["review_priority"] = "low"
    elif score >= 0.9 or float(item.get("alias_similarity") or 0) >= 0.98:
        item["review_priority"] = "high"
    else:
        item["review_priority"] = "normal"
    item["review_reason"] = "；".join(reasons) if reasons else "疑似同义或重复知识点，需 Step 7 判断是否合并。"
    item["allowed_decisions"] = ["accept_merge", "reject_merge", "defer"]
    item["merge_execution_step"] = "Step 7B only"
    return item


def write_checklist(path: Path, rows: list[dict[str, Any]]) -> None:
    counts = Counter(str(row.get("node_type") or "") for row in rows)
    priority_counts = Counter(str(row.get("review_priority") or "") for row in rows)
    lines = [
        "# v4.4 Step 5B Merge Review Checklist",
        "",
        "本清单只列出疑似同义/重复知识点，Step 5B 不自动合并。",
        "",
        "## 审核口径",
        "",
        "- `accept_merge`：两个节点确实是同一知识点、别名或等价表述，保留 primary，secondary 并入 aliases/source trace，并迁移关系。",
        "- `reject_merge`：两个节点只是相关、上下位、组成、应用、推导或并列关系，不合并。",
        "- `defer`：证据不足，继续保留在待审队列。",
        "",
        "## 统计",
        f"- review_merge_candidates: {len(rows)}",
    ]
    for key, count in sorted(counts.items()):
        lines.append(f"- node_type={key}: {count}")
    for key, count in sorted(priority_counts.items()):
        lines.append(f"- priority={key}: {count}")

    lines.extend(["", "## 明细"])
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"{index}. [{row.get('review_priority')}] {row.get('node_type')} | "
            f"{row.get('primary_name')} <- {row.get('secondary_name')} | score={row.get('merge_score')}"
        )
        lines.append(f"   - reason: {row.get('review_reason', '')}")
        node_a = row.get("node_a") or {}
        node_b = row.get("node_b") or {}
        lines.append(f"   - A: {node_a.get('name', '')} | {node_a.get('section_node_id', '')}")
        lines.append(f"   - B: {node_b.get('name', '')} | {node_b.get('section_node_id', '')}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    candidates = read_jsonl(args.merge_candidates, required=False)
    review_items = [prepare_review_item(candidate, args.min_score) for candidate in candidates]
    write_jsonl(args.out, review_items)
    write_checklist(args.checklist, review_items)
    print(f"[OK] Step 5B merge review items -> {args.out}")
    print(f"[OK] checklist -> {args.checklist}")
    print(f"[INFO] review_merge_candidates={len(review_items)}")


if __name__ == "__main__":
    main()
