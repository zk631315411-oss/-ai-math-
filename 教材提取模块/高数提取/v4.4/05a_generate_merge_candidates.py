"""
v4.4 Step 5A: generate semantic merge candidates.

This script does not merge nodes. It only finds pairs that may refer to the
same knowledge point and writes auditable candidate records for Step 5B/Step 7.

Design notes:
- hard rule: only compare nodes with the same type.
- hard rule: do not propose merging two nodes that already have a meaningful
  semantic relation between them. A relation usually means the nodes are related
  but not the same.
- evidence is heuristic: normalized name similarity, alias overlap, text
  similarity, and local role similarity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_DIR = SCRIPT_DIR / "中间产物"

DEFAULT_MAIN_NODES = DEFAULT_DIR / "kg_main_nodes.jsonl"
DEFAULT_REVIEW_NODES = DEFAULT_DIR / "step5_review_nodes.jsonl"
DEFAULT_MAIN_EDGES = DEFAULT_DIR / "kg_main_edges.jsonl"
DEFAULT_REVIEW_EDGES = DEFAULT_DIR / "step5_review_edges.jsonl"
DEFAULT_OUT = DEFAULT_DIR / "merge_candidates.jsonl"
DEFAULT_REPORT = DEFAULT_DIR / "merge_candidate_report.md"

BLOCKING_EDGE_TYPES = {"SUPERIOR", "PART_OF", "HAS_PROPERTY", "USES", "GETS", "DERIVES"}
NODE_TYPES = {"Concept", "Method", "Formula", "Theorem", "ProblemClass"}
STOP_TOKENS = {
    "的",
    "和",
    "与",
    "及",
    "性质",
    "定理",
    "公式",
    "方法",
    "问题",
    "概念",
    "定义",
    "判定",
    "准则",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate v4.4 Step 5A semantic merge candidates.")
    parser.add_argument("--main-nodes", type=Path, default=DEFAULT_MAIN_NODES)
    parser.add_argument("--review-nodes", type=Path, default=DEFAULT_REVIEW_NODES)
    parser.add_argument("--main-edges", type=Path, default=DEFAULT_MAIN_EDGES)
    parser.add_argument("--review-edges", type=Path, default=DEFAULT_REVIEW_EDGES)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--max-pairs-per-type", type=int, default=5000)
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


def stable_id(prefix: str, parts: list[str]) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:14]
    return f"{prefix}:{digest}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value).strip()]


def normalize_text(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\$+|\\[a-zA-Z]+|[\s`*_{}()\[\]（）【】,，.。:：;；、!！?？\-—=<>]+", "", text)
    text = re.sub(r"(第?[一二三四五六七八九十百千万0-9]+[章节条])", "", text)
    return text.strip()


def char_ngrams(text: str, n: int = 2) -> set[str]:
    text = normalize_text(text)
    if not text:
        return set()
    if len(text) <= n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def name_similarity(left: str, right: str) -> float:
    left_n = normalize_text(left)
    right_n = normalize_text(right)
    if not left_n or not right_n:
        return 0.0
    if left_n == right_n:
        return 1.0
    seq = SequenceMatcher(None, left_n, right_n).ratio()
    ng = jaccard(char_ngrams(left_n), char_ngrams(right_n))
    contains = 0.0
    if left_n in right_n or right_n in left_n:
        shorter = min(len(left_n), len(right_n))
        longer = max(len(left_n), len(right_n))
        contains = shorter / longer
    return max(seq, ng, contains)


def token_set(node: dict[str, Any]) -> set[str]:
    parts = [
        node.get("name", ""),
        node.get("definition", ""),
        node.get("description", ""),
        node.get("evidence_span", ""),
    ]
    parts.extend(as_list(node.get("aliases")))
    text = normalize_text(" ".join(str(part) for part in parts if part))
    tokens = set(re.findall(r"[\u4e00-\u9fff]{1,}|[a-zA-Z0-9]+", text))
    tokens = {token for token in tokens if token and token not in STOP_TOKENS}
    tokens.update(char_ngrams(text, 2))
    return tokens


def alias_overlap(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_aliases = {normalize_text(item) for item in [left.get("name", ""), *as_list(left.get("aliases"))] if normalize_text(item)}
    right_aliases = {normalize_text(item) for item in [right.get("name", ""), *as_list(right.get("aliases"))] if normalize_text(item)}
    if not left_aliases or not right_aliases:
        return 0.0
    if left_aliases & right_aliases:
        return 1.0
    best = 0.0
    for left_alias in left_aliases:
        for right_alias in right_aliases:
            best = max(best, name_similarity(left_alias, right_alias))
    return best


def edge_endpoint_ids(edge: dict[str, Any]) -> tuple[str, str]:
    return str(edge.get("source_node_id") or ""), str(edge.get("target_node_id") or "")


def related_pairs(edges: list[dict[str, Any]]) -> set[frozenset[str]]:
    pairs: set[frozenset[str]] = set()
    for edge in edges:
        if str(edge.get("type") or "") not in BLOCKING_EDGE_TYPES:
            continue
        source_id, target_id = edge_endpoint_ids(edge)
        if source_id and target_id and source_id != target_id:
            pairs.add(frozenset((source_id, target_id)))
    return pairs


def role_vectors(edges: list[dict[str, Any]]) -> dict[str, Counter[str]]:
    vectors: dict[str, Counter[str]] = defaultdict(Counter)
    for edge in edges:
        edge_type = str(edge.get("type") or "")
        source_id, target_id = edge_endpoint_ids(edge)
        if source_id:
            vectors[source_id][f"out:{edge_type}"] += 1
        if target_id:
            vectors[target_id][f"in:{edge_type}"] += 1
    return vectors


def cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    keys = set(left) | set(right)
    dot = sum(left[key] * right[key] for key in keys)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def node_quality(node: dict[str, Any]) -> float:
    score = 0.0
    if node.get("definition"):
        score += 2.0
    if node.get("description"):
        score += 1.0
    if node.get("evidence_span"):
        score += 1.0
    score += min(len(as_list(node.get("aliases"))) * 0.3, 1.2)
    try:
        score += float(node.get("confidence") or 0) * 0.5
    except (TypeError, ValueError):
        pass
    if node.get("review_status") == "auto_accept":
        score += 0.8
    return score


def preferred_primary(left: dict[str, Any], right: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    if left.get("review_status") == "auto_accept" and right.get("review_status") != "auto_accept":
        return left, right, "左侧节点已通过 Step 3E 自动复核。"
    if right.get("review_status") == "auto_accept" and left.get("review_status") != "auto_accept":
        return right, left, "右侧节点已通过 Step 3E 自动复核。"
    if node_quality(left) >= node_quality(right):
        return left, right, "左侧节点描述更完整或置信度更高。"
    return right, left, "右侧节点描述更完整或置信度更高。"


def source_brief(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "node_id": node.get("node_id", ""),
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "aliases": as_list(node.get("aliases")),
        "definition": node.get("definition", ""),
        "description": node.get("description", ""),
        "evidence_span": node.get("evidence_span", ""),
        "review_status": node.get("review_status", ""),
        "kg_layer": node.get("kg_layer", ""),
        "chapter": node.get("chapter", ""),
        "section": node.get("section", ""),
        "subsection": node.get("subsection", ""),
        "section_node_id": node.get("section_node_id", ""),
        "source_code": node.get("source_code", ""),
    }


def candidate_reason(name_score: float, alias_score: float, text_score: float, role_score: float) -> list[str]:
    reasons: list[str] = []
    if alias_score >= 0.98:
        reasons.append("名称或别名完全重合。")
    elif alias_score >= 0.86:
        reasons.append("名称或别名高度相似。")
    if name_score >= 0.86:
        reasons.append("语义名称高度相似。")
    if text_score >= 0.58:
        reasons.append("定义、描述或证据文本有明显重叠。")
    if role_score >= 0.75:
        reasons.append("局部入边/出边角色相似。")
    if not reasons:
        reasons.append("综合相似度达到候选阈值。")
    return reasons


def merge_score(name_score: float, alias_score: float, text_score: float, role_score: float) -> float:
    return round(max(alias_score, 0.42 * name_score + 0.30 * text_score + 0.18 * role_score + 0.10 * alias_score), 4)


def should_emit(score: float, name_score: float, alias_score: float, text_score: float, role_score: float, min_score: float) -> bool:
    if alias_score >= 0.98:
        return True
    if name_score >= 0.92:
        return True
    if score >= min_score and (name_score >= 0.70 or text_score >= 0.50 or role_score >= 0.75):
        return True
    return False


def generate_candidates(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    min_score: float,
    max_pairs_per_type: int,
) -> list[dict[str, Any]]:
    by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        if str(node.get("type") or "") not in NODE_TYPES:
            continue
        if not node.get("node_id") or not node.get("name"):
            continue
        by_type[str(node.get("type"))].append(node)

    blocked = related_pairs(edges)
    roles = role_vectors(edges)
    token_cache = {str(node.get("node_id")): token_set(node) for node in nodes if node.get("node_id")}
    candidates: list[dict[str, Any]] = []

    for node_type, typed_nodes in sorted(by_type.items()):
        typed_nodes = sorted(typed_nodes, key=lambda item: str(item.get("node_id") or ""))
        compared = 0
        for index, left in enumerate(typed_nodes):
            left_id = str(left.get("node_id") or "")
            for right in typed_nodes[index + 1 :]:
                right_id = str(right.get("node_id") or "")
                if not left_id or not right_id or left_id == right_id:
                    continue
                compared += 1
                if compared > max_pairs_per_type:
                    break
                if frozenset((left_id, right_id)) in blocked:
                    continue
                n_score = name_similarity(str(left.get("name") or ""), str(right.get("name") or ""))
                a_score = alias_overlap(left, right)
                t_score = jaccard(token_cache.get(left_id, set()), token_cache.get(right_id, set()))
                r_score = cosine(roles.get(left_id, Counter()), roles.get(right_id, Counter()))
                score = merge_score(n_score, a_score, t_score, r_score)
                if not should_emit(score, n_score, a_score, t_score, r_score, min_score):
                    continue

                primary, secondary, primary_reason = preferred_primary(left, right)
                candidate_id = stable_id("merge-candidate", [left_id, right_id, node_type])
                candidates.append(
                    {
                        "candidate_id": candidate_id,
                        "item_kind": "merge_candidate",
                        "item_type": "MergeCandidate",
                        "node_type": node_type,
                        "primary_node_id": primary.get("node_id", ""),
                        "primary_name": primary.get("name", ""),
                        "secondary_node_id": secondary.get("node_id", ""),
                        "secondary_name": secondary.get("name", ""),
                        "node_a": source_brief(left),
                        "node_b": source_brief(right),
                        "name_similarity": round(n_score, 4),
                        "alias_similarity": round(a_score, 4),
                        "text_similarity": round(t_score, 4),
                        "role_similarity": round(r_score, 4),
                        "merge_score": score,
                        "candidate_reason": candidate_reason(n_score, a_score, t_score, r_score),
                        "primary_selection_reason": primary_reason,
                        "step5a_policy": "candidate_only_no_auto_merge",
                        "review_status": "review",
                        "generated_at": now_iso(),
                    }
                )
            if compared > max_pairs_per_type:
                break

    return sorted(candidates, key=lambda item: (-float(item.get("merge_score") or 0), str(item.get("candidate_id") or "")))


def write_report(path: Path, candidates: list[dict[str, Any]]) -> None:
    counts = Counter(str(row.get("node_type") or "") for row in candidates)
    lines = [
        "# v4.4 Step 5A Merge Candidate Report",
        "",
        "Step 5A 只生成“疑似同义/重复知识点”候选，不执行合并。",
        "",
        "## Counts",
        f"- merge_candidates: {len(candidates)}",
    ]
    for node_type, count in sorted(counts.items()):
        lines.append(f"- {node_type}: {count}")
    lines.extend(["", "## Top Candidates"])
    for index, row in enumerate(candidates[:50], start=1):
        lines.append(
            f"{index}. {row.get('node_type')} | {row.get('primary_name')} <- {row.get('secondary_name')} "
            f"| score={row.get('merge_score')} name={row.get('name_similarity')} text={row.get('text_similarity')} role={row.get('role_similarity')}"
        )
        lines.append(f"   - reason: {'；'.join(row.get('candidate_reason') or [])}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    args = parse_args()
    main_nodes = read_jsonl(args.main_nodes, required=False)
    review_nodes = read_jsonl(args.review_nodes, required=False)
    main_edges = read_jsonl(args.main_edges, required=False)
    review_edges = read_jsonl(args.review_edges, required=False)

    candidates = generate_candidates(
        [*main_nodes, *review_nodes],
        [*main_edges, *review_edges],
        min_score=args.min_score,
        max_pairs_per_type=args.max_pairs_per_type,
    )
    write_jsonl(args.out, candidates)
    write_report(args.report, candidates)
    print(f"[OK] Step 5A merge candidates -> {args.out}")
    print(f"[OK] report -> {args.report}")
    print(f"[INFO] candidates={len(candidates)}")


if __name__ == "__main__":
    main()
