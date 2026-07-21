# -*- coding: utf-8 -*-
"""
Generate conservative implicit semantic edges for an existing v4.4 final graph.

This is an enhancement layer inspired by Tree-KG HiddenKG/Pred:
- build candidate node pairs from local graph context, textbook groups, names,
  and descriptions;
- ask an LLM to decide whether one strong relation should be added;
- keep accepted edges as `kg_layer=implicit` without mutating the original graph.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
DEFAULT_ENV_PATHS = [
    SCRIPT_DIR / ".env",
    SCRIPT_DIR / "v4.4_xia" / ".env",
    SCRIPT_DIR / "v4.4" / ".env",
    REPO_ROOT / ".env",
]

CORE_NODE_TYPES = {"Concept", "Theorem", "Formula", "Method", "ProblemClass"}
ALLOWED_IMPLICIT_EDGE_TYPES = {
    "SUPERIOR",
    "PART_OF",
    "HAS_PROPERTY",
    "USES",
    "GETS",
    "DERIVES",
    "EQUATIVE",
    "APPLIES_TO",
    "PREREQUISITE_OF",
}
SEMANTIC_EDGE_TYPES = ALLOWED_IMPLICIT_EDGE_TYPES | {
    "HAS_RULE_CASE",
    "REFERS_TO",
}
TRIVIAL_NAMES = {
    "解",
    "根",
    "点",
    "线",
    "面",
    "项",
    "和",
    "差",
    "积",
    "商",
    "式",
    "值",
    "数",
    "函数",
    "公式",
    "定理",
    "方法",
    "问题",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate v4.4 implicit KG edges.")
    parser.add_argument("--final-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--env-file", type=Path, action="append", default=[])
    parser.add_argument("--model", default="")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--max-candidates", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=1800)
    parser.add_argument("--min-confidence", type=float, default=0.72)
    parser.add_argument("--chapter-regex", default="")
    parser.add_argument("--include-cross-textbook", action="store_true")
    parser.add_argument("--cross-textbook-only", action="store_true")
    parser.add_argument("--dry-run-candidates", action="store_true")
    parser.add_argument("--timeout", type=float, default=None)
    return parser.parse_args()


def read_jsonl(path: Path, required: bool = True) -> list[dict[str, Any]]:
    if not path.exists():
        if required:
            raise FileNotFoundError(f"JSONL not found: {path}")
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_json(path: Path) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def load_env_value(key: str, env_files: list[Path]) -> str:
    if os.environ.get(key):
        return str(os.environ[key]).strip()
    for env_path in env_files + DEFAULT_ENV_PATHS:
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


def env_bool(value: str, default: bool = True) -> bool:
    if value == "":
        return default
    return value.strip().lower() not in {"0", "false", "no", "off"}


def resolve_llm(args: argparse.Namespace, config: dict[str, Any]) -> tuple[str, str, str, float, bool]:
    llm = config.get("llm", {}) if isinstance(config, dict) else {}
    model = (
        args.model
        or load_env_value("OPENAI_EDGE_MODEL", args.env_file)
        or load_env_value("OPENAI_DEFAULT_MODEL", args.env_file)
        or llm.get("edge_model")
        or llm.get("relation_audit_model")
        or llm.get("high_risk_model")
        or "gpt-5.5"
    )
    base_url = (
        args.base_url
        or load_env_value("OPENAI_BASE_URL", args.env_file)
        or load_env_value("LLM_BASE_URL", args.env_file)
        or load_env_value("DEEPSEEK_API_BASE", args.env_file)
        or llm.get("base_url")
        or "http://120.224.38.132:7361/v1"
    )
    api_key = (
        args.api_key
        or load_env_value("OPENAI_API_KEY", args.env_file)
        or load_env_value("LLM_API_KEY", args.env_file)
        or load_env_value("DEEPSEEK_API_KEY", args.env_file)
    )
    timeout = float(args.timeout if args.timeout is not None else llm.get("timeout_seconds", 180))
    verify_ssl = env_bool(load_env_value("LLM_VERIFY_SSL", args.env_file), True)
    return str(model), str(base_url).rstrip("/"), str(api_key), timeout, verify_ssl


def stable_id(prefix: str, parts: list[str], n: int = 14) -> str:
    digest = hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:n]
    return f"{prefix}:{digest}"


def normalize_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[\$\\{}_\^（）()\[\]【】,，.。:：;；、|/]", "", text)
    return text.lower()


def char_bigrams(text: str) -> set[str]:
    text = normalize_text(text)
    if len(text) <= 1:
        return {text} if text else set()
    return {text[i : i + 2] for i in range(len(text) - 1)}


def jaccard(a: str, b: str) -> float:
    aa = char_bigrams(a)
    bb = char_bigrams(b)
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / len(aa | bb)


def compact_text(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def node_text(node: dict[str, Any], limit: int = 260) -> str:
    parts = [
        node.get("definition", ""),
        node.get("description", ""),
        node.get("evidence_span", ""),
    ]
    attrs = node.get("attributes", [])
    if isinstance(attrs, list):
        parts.extend(f"{a.get('name', '')}:{a.get('value', '')}" for a in attrs if isinstance(a, dict))
    return compact_text(" ".join(str(p or "") for p in parts), limit)


def valid_core_node(node: dict[str, Any]) -> bool:
    if node.get("type") not in CORE_NODE_TYPES:
        return False
    if node.get("final_import_ready") is False:
        return False
    name = str(node.get("name") or "").strip()
    if len(name) < 2 or name in TRIVIAL_NAMES:
        return False
    return bool(node.get("node_id"))


def chapter_order(chapter: str) -> int:
    match = re.search(r"第\s*(\d+)\s*章", str(chapter or ""))
    return int(match.group(1)) if match else 0


def pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def load_graph(final_dir: Path, chapter_regex: str = "") -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes = read_jsonl(final_dir / "final_core_nodes.jsonl")
    edges = read_jsonl(final_dir / "final_core_edges.jsonl")
    group_edges = read_jsonl(final_dir / "final_knowledge_group_edges.jsonl", required=False)
    valid_nodes = [node for node in nodes if valid_core_node(node)]
    if chapter_regex:
        pattern = re.compile(chapter_regex)
        valid_nodes = [node for node in valid_nodes if pattern.search(str(node.get("chapter", "")))]
    return valid_nodes, edges, group_edges


def semantic_degrees(edges: list[dict[str, Any]]) -> Counter[str]:
    deg: Counter[str] = Counter()
    for edge in edges:
        if edge.get("type") not in SEMANTIC_EDGE_TYPES:
            continue
        s = str(edge.get("source_node_id") or "")
        t = str(edge.get("target_node_id") or "")
        if s:
            deg[s] += 1
        if t:
            deg[t] += 1
    return deg


def existing_semantic_pairs(edges: list[dict[str, Any]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for edge in edges:
        if edge.get("type") not in SEMANTIC_EDGE_TYPES:
            continue
        s = str(edge.get("source_node_id") or "")
        t = str(edge.get("target_node_id") or "")
        if s and t and s != t:
            pairs.add(pair_key(s, t))
    return pairs


def neighbor_names(edges: list[dict[str, Any]]) -> dict[str, list[str]]:
    names: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        if edge.get("type") not in SEMANTIC_EDGE_TYPES:
            continue
        s = str(edge.get("source_node_id") or "")
        t = str(edge.get("target_node_id") or "")
        st = str(edge.get("source_name") or "")
        tt = str(edge.get("target_name") or "")
        typ = str(edge.get("type") or "")
        if s and tt:
            names[s].append(f"{typ}->{tt}")
        if t and st:
            names[t].append(f"{typ}<-{st}")
    return {k: v[:8] for k, v in names.items()}


def group_memberships(group_edges: list[dict[str, Any]], node_ids: set[str]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    group_to_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
    node_to_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in group_edges:
        if edge.get("type") != "HAS_MEMBER":
            continue
        target_id = str(edge.get("target_node_id") or "")
        source_group_id = str(edge.get("source_group_id") or edge.get("source_node_id") or "")
        if not target_id or not source_group_id or target_id not in node_ids:
            continue
        info = {
            "group_id": source_group_id,
            "group_name": edge.get("source_name", ""),
            "section_group_key": edge.get("section_group_key", ""),
            "section_node_id": edge.get("section_node_id", ""),
            "chapter": edge.get("chapter", ""),
            "section": edge.get("section", ""),
            "subsection": edge.get("subsection", ""),
        }
        group_to_members[source_group_id].append({"node_id": target_id, **info})
        node_to_groups[target_id].append(info)
    return group_to_members, node_to_groups


def candidate_score(
    a: dict[str, Any],
    b: dict[str, Any],
    node_to_groups: dict[str, list[dict[str, Any]]],
    deg: Counter[str],
    cross_textbook: bool,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    a_id = str(a["node_id"])
    b_id = str(b["node_id"])
    a_name = str(a.get("name") or "")
    b_name = str(b.get("name") or "")
    na = normalize_text(a_name)
    nb = normalize_text(b_name)

    if a.get("textbook_id") != b.get("textbook_id"):
        if not cross_textbook:
            return -999.0, []
        score += 0.4
        reasons.append("跨上下册候选")

    same_subsection = bool(a.get("section_node_id") and a.get("section_node_id") == b.get("section_node_id"))
    same_section = bool(a.get("section") and a.get("section") == b.get("section") and a.get("chapter") == b.get("chapter"))
    same_chapter = bool(a.get("chapter") and a.get("chapter") == b.get("chapter"))
    if same_subsection:
        score += 2.2
        reasons.append("同叶子小节")
    elif same_section:
        score += 1.5
        reasons.append("同教材节")
    elif same_chapter:
        score += 0.6
        reasons.append("同章")

    group_ids_a = {g["group_id"] for g in node_to_groups.get(a_id, [])}
    group_ids_b = {g["group_id"] for g in node_to_groups.get(b_id, [])}
    group_inter = group_ids_a & group_ids_b
    if group_inter:
        score += min(1.4, 0.7 * len(group_inter))
        reasons.append("同知识组")

    if na and nb and (na in nb or nb in na) and na != nb:
        longer = max(len(na), len(nb))
        if longer >= 4:
            score += 3.0
            reasons.append("名称包含")
    sim = jaccard(a_name, b_name)
    if sim >= 0.45:
        score += 2.0 * sim
        reasons.append(f"名称相似({sim:.2f})")

    a_text = normalize_text(node_text(a, 500))
    b_text = normalize_text(node_text(b, 500))
    if na and len(na) >= 3 and na in b_text:
        score += 1.8
        reasons.append("A名称出现在B描述")
    if nb and len(nb) >= 3 and nb in a_text:
        score += 1.8
        reasons.append("B名称出现在A描述")

    type_pair = (str(a.get("type")), str(b.get("type")))
    if "Method" in type_pair and ("ProblemClass" in type_pair or "Formula" in type_pair or "Concept" in type_pair):
        score += 0.8
        reasons.append("方法相关类型组合")
    if "Theorem" in type_pair and ("Formula" in type_pair or "Concept" in type_pair):
        score += 0.7
        reasons.append("定理相关类型组合")
    if "Formula" in type_pair and "Concept" in type_pair:
        score += 0.6
        reasons.append("公式-概念组合")

    if deg[a_id] == 0 or deg[b_id] == 0:
        score += 0.8
        reasons.append("至少一端语义边稀疏")

    ca = chapter_order(str(a.get("chapter", "")))
    cb = chapter_order(str(b.get("chapter", "")))
    if a.get("textbook_id") != b.get("textbook_id") and ca and cb and 0 < cb - ca <= 6:
        score += 0.5
        reasons.append("章节顺序支持前后衔接")

    return round(score, 4), reasons


def build_candidates(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    group_edges: list[dict[str, Any]],
    max_candidates: int,
    include_cross_textbook: bool,
    cross_textbook_only: bool,
) -> list[dict[str, Any]]:
    node_by_id = {str(node["node_id"]): node for node in nodes}
    node_ids = set(node_by_id)
    _, node_to_groups = group_memberships(group_edges, node_ids)
    deg = semantic_degrees(edges)
    existing_pairs = existing_semantic_pairs(edges)
    candidates_by_pair: dict[tuple[str, str], dict[str, Any]] = {}

    for i, a in enumerate(nodes):
        for b in nodes[i + 1 :]:
            a_id = str(a["node_id"])
            b_id = str(b["node_id"])
            if a_id == b_id:
                continue
            is_cross = a.get("textbook_id") != b.get("textbook_id")
            if cross_textbook_only and not is_cross:
                continue
            if is_cross and not include_cross_textbook and not cross_textbook_only:
                continue
            key = pair_key(a_id, b_id)
            if key in existing_pairs:
                continue
            score, reasons = candidate_score(a, b, node_to_groups, deg, include_cross_textbook or cross_textbook_only)
            if score < 3.35:
                continue
            item = {
                "candidate_id": stable_id("implicit:candidate", [a_id, b_id]),
                "a_node_id": a_id,
                "a_name": a.get("name", ""),
                "a_type": a.get("type", ""),
                "a_textbook_id": a.get("textbook_id", ""),
                "a_chapter": a.get("chapter", ""),
                "a_section": a.get("section", ""),
                "b_node_id": b_id,
                "b_name": b.get("name", ""),
                "b_type": b.get("type", ""),
                "b_textbook_id": b.get("textbook_id", ""),
                "b_chapter": b.get("chapter", ""),
                "b_section": b.get("section", ""),
                "score": score,
                "candidate_reasons": reasons,
                "a_semantic_degree": deg[a_id],
                "b_semantic_degree": deg[b_id],
                "a_group_names": sorted({g["group_name"] for g in node_to_groups.get(a_id, []) if g.get("group_name")})[:5],
                "b_group_names": sorted({g["group_name"] for g in node_to_groups.get(b_id, []) if g.get("group_name")})[:5],
            }
            candidates_by_pair[key] = item

    candidates = sorted(
        candidates_by_pair.values(),
        key=lambda row: (
            -float(row["score"]),
            min(int(row["a_semantic_degree"]), int(row["b_semantic_degree"])),
            row["a_name"],
            row["b_name"],
        ),
    )
    return candidates[:max_candidates] if max_candidates > 0 else candidates


def prompt_for_batch(batch: list[dict[str, Any]], node_by_id: dict[str, dict[str, Any]], neighbors: dict[str, list[str]]) -> str:
    compact_candidates: list[dict[str, Any]] = []
    for cand in batch:
        a = node_by_id[cand["a_node_id"]]
        b = node_by_id[cand["b_node_id"]]
        compact_candidates.append(
            {
                "candidate_id": cand["candidate_id"],
                "score": cand["score"],
                "candidate_reasons": cand["candidate_reasons"],
                "A": {
                    "node_id": cand["a_node_id"],
                    "name": cand["a_name"],
                    "type": cand["a_type"],
                    "chapter": cand["a_chapter"],
                    "section": cand["a_section"],
                    "description": node_text(a),
                    "neighbors": neighbors.get(cand["a_node_id"], [])[:6],
                },
                "B": {
                    "node_id": cand["b_node_id"],
                    "name": cand["b_name"],
                    "type": cand["b_type"],
                    "chapter": cand["b_chapter"],
                    "section": cand["b_section"],
                    "description": node_text(b),
                    "neighbors": neighbors.get(cand["b_node_id"], [])[:6],
                },
            }
        )

    system = """你是数学教材知识图谱的隐式边审核员。你的任务是判断候选知识点对之间是否应新增一条强语义边。

只能使用以下关系，并且必须注意方向：
- SUPERIOR：A 是 B 的特例/子类/更具体概念，方向 A -> B。
- PART_OF：A 是 B 的组成部分、表达式部分、步骤部分，方向 A -> B。
- HAS_PROPERTY：A 具有性质/定理/特征 B，方向 A -> B。
- USES：A 在定义、计算、证明或方法中使用 B，方向 A -> B。
- GETS：A 可得到/计算出/产生 B，方向 A -> B。
- DERIVES：A 可推出或推导出 B，方向 A -> B。
- EQUATIVE：A 与 B 等价或实质同义，任选更规范名称为 source。
- APPLIES_TO：A 适用于 B，通常 A 是方法/公式/定理，B 是对象/题型/场景。
- PREREQUISITE_OF：学习 A 是理解 B 的明显前置，方向 A -> B。

硬规则：
1. 只因同章、同节、同知识组、名称相似而相关，不足以加边，必须输出 no_edge。
2. 不要为了减少孤立节点强行加边。
3. 不新增“泛泛相关”边；没有强关系就 no_edge。
4. 若已有描述证据只能支持条件判断本身，不要把条件判断压成普通边。
5. 输出必须是 JSON，不要写解释性正文。
6. basis 必须直接写具体节点名称，不要用“A”“B”“实体A”“实体B”代称。"""

    user = {
        "task": "逐条判断是否新增隐式边。action 只能是 A_TO_B、B_TO_A、no_edge。",
        "output_schema": [
            {
                "candidate_id": "原 candidate_id",
                "action": "A_TO_B|B_TO_A|no_edge",
                "type": "关系类型；no_edge时为空字符串",
                "confidence": "0到1之间的小数",
                "basis": "一句中文依据，必须使用具体节点名称，不要使用A/B代称",
            }
        ],
        "candidates": compact_candidates,
    }
    return system + "\n\n" + json.dumps(user, ensure_ascii=False, indent=2)


def parse_json_array(text: str) -> list[dict[str, Any]]:
    if not text:
        return []
    stripped = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    try:
        data = json.loads(stripped)
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            return [row for row in data["items"] if isinstance(row, dict)]
    except Exception:
        pass
    match = re.search(r"\[.*\]", stripped, flags=re.S)
    if not match:
        return []
    try:
        data = json.loads(match.group(0))
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
    except Exception:
        return []
    return []


def call_llm_batch(
    batch: list[dict[str, Any]],
    node_by_id: dict[str, dict[str, Any]],
    neighbors: dict[str, list[str]],
    api_key: str,
    base_url: str,
    model: str,
    timeout: float,
    max_tokens: int,
    verify_ssl: bool,
) -> tuple[list[dict[str, Any]], str]:
    prompt = prompt_for_batch(batch, node_by_id, neighbors)
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = f"{base_url}/chat/completions"
    last_error = ""
    for attempt in range(1, 4):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout, verify=verify_ssl)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return parse_json_array(content), content[:1000]
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:240]}"
            time.sleep(min(12, 2**attempt))
    return [], last_error


def normalize_decision(raw: dict[str, Any]) -> dict[str, Any]:
    action = str(raw.get("action") or raw.get("decision") or "").strip()
    action = action.upper().replace("-", "_")
    rel_type = str(raw.get("type") or raw.get("relation_type") or "").strip().upper()
    try:
        confidence = float(raw.get("confidence", 0))
    except Exception:
        confidence = 0.0
    return {
        "candidate_id": str(raw.get("candidate_id") or "").strip(),
        "action": action,
        "type": rel_type,
        "confidence": max(0.0, min(1.0, confidence)),
        "basis": compact_text(raw.get("basis", ""), 260),
        "raw_decision": raw,
    }


def concrete_basis(basis: str, candidate: dict[str, Any]) -> str:
    text = compact_text(basis, 260)
    a_name = str(candidate.get("a_name") or "")
    b_name = str(candidate.get("b_name") or "")
    replacements = [
        ("实体A", a_name),
        ("实体B", b_name),
        ("节点A", a_name),
        ("节点B", b_name),
        ("概念A", a_name),
        ("概念B", b_name),
    ]
    for old, new in replacements:
        if new:
            text = text.replace(old, new)
    if a_name:
        text = re.sub(r"(?<![A-Za-z])A(?![A-Za-z])", a_name, text)
    if b_name:
        text = re.sub(r"(?<![A-Za-z])B(?![A-Za-z])", b_name, text)
    return compact_text(text, 260)


def decision_to_edge(
    decision: dict[str, Any],
    candidate: dict[str, Any],
    node_by_id: dict[str, dict[str, Any]],
    model: str,
    min_confidence: float,
) -> tuple[dict[str, Any] | None, str]:
    if decision["action"] == "NO_EDGE":
        return None, "no_edge"
    if decision["action"] not in {"A_TO_B", "B_TO_A"}:
        return None, "invalid_action"
    if decision["type"] not in ALLOWED_IMPLICIT_EDGE_TYPES:
        return None, "invalid_type"
    if decision["confidence"] < min_confidence:
        return None, "low_confidence"
    a = node_by_id.get(candidate["a_node_id"])
    b = node_by_id.get(candidate["b_node_id"])
    if not a or not b:
        return None, "missing_endpoint"
    source = a if decision["action"] == "A_TO_B" else b
    target = b if decision["action"] == "A_TO_B" else a
    if source["node_id"] == target["node_id"]:
        return None, "self_loop"

    basis = concrete_basis(decision["basis"], candidate)
    textbook_id = source.get("textbook_id") if source.get("textbook_id") == target.get("textbook_id") else "gaoshu"
    edge_id = stable_id(
        f"{textbook_id}:implicitedge",
        [source["node_id"], target["node_id"], decision["type"], candidate["candidate_id"]],
    )
    now = datetime.now().isoformat(timespec="seconds")
    edge = {
        "edge_id": edge_id,
        "type": decision["type"],
        "kg_layer": "implicit",
        "source_node_id": source.get("node_id", ""),
        "source_name": source.get("name", ""),
        "source_type": source.get("type", ""),
        "target_node_id": target.get("node_id", ""),
        "target_name": target.get("name", ""),
        "target_type": target.get("type", ""),
        "textbook_id": textbook_id,
        "textbook_name": source.get("textbook_name", "") if textbook_id != "gaoshu" else "高等数学",
        "chapter": source.get("chapter", ""),
        "section": source.get("section", ""),
        "subsection": source.get("subsection", ""),
        "section_node_id": source.get("section_node_id", ""),
        "source_scope": source.get("source_scope", ""),
        "source_code": f"implicit:{candidate['candidate_id']}",
        "evidence_span": "隐式边；依据节点描述、已有邻域结构与教材知识组推断，非连续原文证据。",
        "evidence_spans": [
            {"role": "candidate_reasons", "text": "；".join(candidate.get("candidate_reasons", []))},
            {"role": "llm_basis", "text": basis},
        ],
        "description": basis,
        "confidence": decision["confidence"],
        "review_status": "auto_accept_implicit",
        "final_import_ready": True,
        "validation_warnings": ["implicit_edge_no_contiguous_evidence"],
        "implicit_candidate_id": candidate["candidate_id"],
        "implicit_candidate_score": candidate.get("score", 0),
        "implicit_candidate_reasons": candidate.get("candidate_reasons", []),
        "implicit_model": model,
        "implicit_generated_at": now,
    }
    return edge, "accepted"


def build_report(
    args: argparse.Namespace,
    model: str,
    candidates: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
) -> str:
    decision_counts = Counter(row.get("decision_status", "") for row in decisions)
    edge_counts = Counter(row.get("type", "") for row in edges)
    lines = [
        "# v4.4 隐式边生成报告",
        "",
        f"- generated_at: `{datetime.now().isoformat(timespec='seconds')}`",
        f"- final_dir: `{args.final_dir}`",
        f"- model: `{model}`",
        f"- candidates: {len(candidates)}",
        f"- decisions: {len(decisions)}",
        f"- accepted_edges: {len(edges)}",
        f"- rejected_or_no_edge: {len(rejected)}",
        "",
        "## 决策统计",
    ]
    for key, value in sorted(decision_counts.items()):
        lines.append(f"- {key or '(empty)'}: {value}")
    lines.extend(["", "## 隐式边类型"])
    for key, value in sorted(edge_counts.items()):
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## 样例边"])
    for edge in edges[:20]:
        lines.append(
            f"- {edge['source_name']} --{edge['type']}--> {edge['target_name']} "
            f"(confidence={edge['confidence']}, basis={edge['description']})"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    config = read_json(args.config) if args.config else {}
    model, base_url, api_key, timeout, verify_ssl = resolve_llm(args, config)

    nodes, edges, group_edges = load_graph(args.final_dir, args.chapter_regex)
    node_by_id = {str(node["node_id"]): node for node in nodes}
    candidates = build_candidates(
        nodes,
        edges,
        group_edges,
        args.max_candidates,
        include_cross_textbook=args.include_cross_textbook,
        cross_textbook_only=args.cross_textbook_only,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.out_dir / "implicit_candidates.jsonl", candidates)

    print(
        json.dumps(
            {
                "nodes": len(nodes),
                "existing_edges": len(edges),
                "group_edges": len(group_edges),
                "candidates": len(candidates),
                "model": model,
                "verify_ssl": verify_ssl,
                "dry_run_candidates": args.dry_run_candidates,
            },
            ensure_ascii=False,
        )
    )

    if args.dry_run_candidates or not candidates:
        (args.out_dir / "implicit_report.md").write_text(
            build_report(args, model, candidates, [], [], []),
            encoding="utf-8",
        )
        return
    if not api_key:
        raise RuntimeError("API key not found. Pass --api-key or configure OPENAI_API_KEY/LLM_API_KEY.")

    neigh = neighbor_names(edges)
    batches = [candidates[i : i + args.batch_size] for i in range(0, len(candidates), args.batch_size)]
    raw_decisions_by_id: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, Any]] = []
    checkpoint_path = args.out_dir / "implicit_decisions_checkpoint.jsonl"
    warning_checkpoint_path = args.out_dir / "implicit_warnings_checkpoint.jsonl"
    if checkpoint_path.exists():
        for row in read_jsonl(checkpoint_path, required=False):
            dec = normalize_decision(row)
            if dec["candidate_id"]:
                raw_decisions_by_id[dec["candidate_id"]] = dec
    completed_at_start = len(raw_decisions_by_id)
    if not verify_ssl:
        requests.packages.urllib3.disable_warnings()

    def run_batch(batch_index: int, batch: list[dict[str, Any]]) -> tuple[int, list[dict[str, Any]], str]:
        rows, raw = call_llm_batch(batch, node_by_id, neigh, api_key, base_url, model, timeout, args.max_tokens, verify_ssl)
        return batch_index, rows, raw

    def run_batches(batch_items: list[list[dict[str, Any]]], offset: str) -> None:
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            future_map = {
                executor.submit(run_batch, batch_index, batch): (batch_index, batch)
                for batch_index, batch in enumerate(batch_items)
            }
            for future in as_completed(future_map):
                batch_index, batch = future_map[future]
                try:
                    _, rows, raw = future.result()
                    if not rows:
                        warning = {"batch_index": f"{offset}:{batch_index}", "warning": "empty_or_unparsed_response", "raw": raw}
                        warnings.append(warning)
                        append_jsonl(warning_checkpoint_path, [warning])
                    normalized_rows: list[dict[str, Any]] = []
                    for row in rows:
                        dec = normalize_decision(row)
                        if dec["candidate_id"]:
                            raw_decisions_by_id[dec["candidate_id"]] = dec
                            normalized_rows.append(dec)
                    append_jsonl(checkpoint_path, normalized_rows)
                except Exception as exc:
                    warning = {"batch_index": f"{offset}:{batch_index}", "warning": f"{type(exc).__name__}: {str(exc)[:240]}"}
                    warnings.append(warning)
                    append_jsonl(warning_checkpoint_path, [warning])

    pending_batches = [
        [cand for cand in batch if cand["candidate_id"] not in raw_decisions_by_id]
        for batch in batches
    ]
    pending_batches = [batch for batch in pending_batches if batch]
    run_batches(pending_batches, "initial")

    # If a gateway drops a whole batch, retry unresolved candidates as singletons.
    # This keeps network flakiness from silently turning into missing decisions.
    for retry_round in range(1, 3):
        missing = [cand for cand in candidates if cand["candidate_id"] not in raw_decisions_by_id]
        if not missing:
            break
        singleton_batches = [[cand] for cand in missing]
        run_batches(singleton_batches, f"retry{retry_round}")

    decisions: list[dict[str, Any]] = []
    accepted_edges: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for cand in candidates:
        dec = raw_decisions_by_id.get(cand["candidate_id"])
        if not dec:
            row = {"candidate": cand, "decision_status": "missing_decision"}
            decisions.append(row)
            rejected.append(row)
            continue
        edge, status = decision_to_edge(dec, cand, node_by_id, model, args.min_confidence)
        row = {**dec, "candidate": cand, "decision_status": status}
        decisions.append(row)
        if edge:
            accepted_edges.append(edge)
        else:
            rejected.append(row)

    write_jsonl(args.out_dir / "implicit_decisions.jsonl", decisions)
    write_jsonl(args.out_dir / "implicit_edges.jsonl", accepted_edges)
    write_jsonl(args.out_dir / "implicit_rejected.jsonl", rejected)
    all_warnings = read_jsonl(warning_checkpoint_path, required=False) if warning_checkpoint_path.exists() else warnings
    write_jsonl(args.out_dir / "implicit_warnings.jsonl", all_warnings)
    (args.out_dir / "implicit_report.md").write_text(
        build_report(args, model, candidates, decisions, accepted_edges, rejected),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidates": len(candidates),
                "decisions": len(decisions),
                "accepted_edges": len(accepted_edges),
                "rejected": len(rejected),
                "warnings": len(warnings),
                "checkpoint_loaded": completed_at_start,
                "out_dir": str(args.out_dir),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
