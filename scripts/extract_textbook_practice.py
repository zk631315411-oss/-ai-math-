"""Extract textbook exercises and worked examples into reviewable assets.

This is intentionally a conservative parser.  It never marks an extracted
row as publishable: answers, KG IDs, stage rationale and review status still
need to be completed by the import review step.  The output is therefore a
useful inventory and an auditable quarantine list, rather than an automatic
question bank.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from app.textbooks import textbook_spec


ROOT = Path(__file__).resolve().parents[1]
ASSETS = {
    "matrix_rank_and_system": {
        "textbook_id": "gaodai_shang",
        "legacy_textbook_id": "gaodai-qiuweisheng-upper",
        "path": ROOT / "比赛相关文件与文件夹/揭榜挂帅/教材库/高等代数/高等代数上册_structured.md",
        "exercise_sections": {"习题3.5": 117, "习题3.6": 122},
        "example_sections": {"3.5.2 典型例题": 113, "3.6.2 典型例题": 120},
        "concept_ids": ["kg:matrix-rank", "kg:linear-system"],
        "concept_names": ["matrix rank", "linear system"],
    },
    "linear_independence_proof": {
        "textbook_id": "gaodai_shang",
        "legacy_textbook_id": "gaodai-qiuweisheng-upper",
        "path": ROOT / "比赛相关文件与文件夹/揭榜挂帅/教材库/高等代数/高等代数上册_structured.md",
        "exercise_sections": {"习题3.2": 96},
        "example_sections": {"3.2.2 典型例题": 90},
        "concept_ids": ["kg:linear-independence"],
        "concept_names": ["linear independence"],
    },
    "limit_calculation_concept_misuse": {
        "textbook_id": "gaoshu_shang",
        "legacy_textbook_id": "gaoshu-huang-upper-v2",
        "path": ROOT / "比赛相关文件与文件夹/揭榜挂帅/教材库/高等数学/上册/高等数学上册_structured.md",
        "exercise_sections": {"习题1-3": 33, "习题1-4": 38, "习题1-5": 43},
        "example_sections": {"函数的极限": 26, "极限的运算法则": 39},
        "concept_ids": ["kg:function-limit", "kg:limit-laws"],
        "concept_names": ["function limit", "limit laws"],
    },
}


def _heading_key(line: str) -> str:
    value = re.sub(r"^#+\s*", "", line.strip())
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _kind_from_text(text: str) -> str:
    if "证明" in text:
        return "proof"
    calculation_tokens = (
        "计算", "求下列", "求上述", "求下述", "求解", "解下列", "求极限", "求值",
    )
    return "calculation" if any(token in text for token in calculation_tokens) else "concept"


def _candidate_errors(item: dict) -> list[str]:
    errors = ["kg_mapping_not_verified", "missing_stage_rationale", "solution_not_reviewed"]
    if item.get("item_kind") == "exercise_item":
        errors.extend(["missing_reviewed_reference_answer", "missing_three_level_hints"])
        if item.get("question_type") == "proof":
            errors.append("missing_proof_rubric")
    return errors


def _sequence_id(textbook_id: str, title: str) -> str:
    numbers = [int(value) for value in re.findall(r"\d+", title)[:2]]
    if len(numbers) < 2:
        return ""
    volume = "V1" if textbook_id.endswith("_shang") else "V2"
    return f"{volume}-C{numbers[0]:02d}-S{numbers[1]:02d}"


def _split_numbered_blocks(lines: list[tuple[int, str]]) -> list[tuple[str, int, str]]:
    starts = [(index, line_no, text.strip()) for index, (line_no, text) in enumerate(lines)
              if re.match(r"^\s*\d+[.．、)]\s*", text)]
    result: list[tuple[str, int, str]] = []
    for position, (index, line_no, title) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        body = "\n".join(text for _, text in lines[index:end]).strip()
        result.append((re.match(r"^\s*(\d+)", title).group(1), line_no, body))
    return result


def _clean_structural_markers(text: str) -> str:
    """Remove pipeline headings that delimit, but are not part of, a stem."""

    lines = [
        line for line in text.splitlines()
        if not re.match(r"^\s*#{4,6}\s*题\s*\d+\s*$", line)
    ]
    return "\n".join(lines).strip()


def _split_subquestions(text: str) -> list[tuple[str, str, str]]:
    """Split independently answerable line-delimited numbered subquestions."""

    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = re.match(r"^\s*[（(](\d+)[）)]", line)
        if match:
            starts.append((index, match.group(1)))
    if len(starts) < 2:
        return []

    shared_stem = "\n".join(lines[:starts[0][0]]).strip()
    result: list[tuple[str, str, str]] = []
    for position, (start, number) in enumerate(starts):
        stop = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        subquestion = "\n".join(lines[start:stop]).strip()
        combined = "\n".join(part for part in (shared_stem, subquestion) if part).strip()
        if combined:
            result.append((number, combined, shared_stem))
    return result


def _extract_section(lines: list[str], title: str, page: int, *, item_kind: str,
                     textbook_id: str, legacy_textbook_id: str,
                     original_textbook_name: str,
                     concept_ids: list[str], concept_names: list[str]) -> list[dict]:
    heading_index = next((i for i, line in enumerate(lines) if _heading_key(line) == title), None)
    if heading_index is None:
        return []
    end = next((i for i in range(heading_index + 1, len(lines)) if re.match(r"^#{1,3}\s+", lines[i])), len(lines))
    section_lines = [(i + 1, lines[i]) for i in range(heading_index + 1, end) if lines[i].strip()]
    if item_kind == "exercise_item":
        blocks = _split_numbered_blocks(section_lines)
    else:
        starts = [(i, line_no, text.strip()) for i, (line_no, text) in enumerate(section_lines)
                  if re.match(r"^(?:例\s*\d+|例\d+|#####\s*例\s*\d+)", text)]
        blocks = []
        for position, (index, line_no, label) in enumerate(starts):
            stop = starts[position + 1][0] if position + 1 < len(starts) else len(section_lines)
            body = "\n".join(text for _, text in section_lines[index:stop]).strip()
            number = re.search(r"\d+", label)
            blocks.append((number.group(0) if number else str(position + 1), line_no, body))
    rows: list[dict] = []
    for number, line_no, raw_question in blocks:
        question = _clean_structural_markers(raw_question)
        if len(question) < 8:
            continue
        parent_digest = hashlib.sha256(question.encode("utf-8")).hexdigest()
        parent_item_id = f"{textbook_id}:{title}:{number}:{parent_digest[:10]}"
        legacy_parent_item_id = f"{legacy_textbook_id}:{title}:{number}:{parent_digest[:10]}"
        subquestions = _split_subquestions(question) if item_kind == "exercise_item" else []
        assets = subquestions or [("", question, "")]
        for subitem, asset_question, shared_stem in assets:
            digest = hashlib.sha256(asset_question.encode("utf-8")).hexdigest()
            item_id = f"{parent_item_id}:sub{subitem}" if subitem else parent_item_id
            source_asset_id = (
                f"{legacy_parent_item_id}:sub{subitem}" if subitem else legacy_parent_item_id
            )
            source_locator = f"page:{page}; section:{title}; item:{number}; markdown_line:{line_no}"
            if subitem:
                source_locator += f"; subitem:{subitem}"
            rows.append({
                "id": item_id,
                "source_asset_id": source_asset_id,
                "textbook_id": textbook_id,
                "original_textbook_name": original_textbook_name,
                "source_locator": source_locator,
                "source_page": page,
                "source_problem_no": number,
                "source_subitem_no": subitem or None,
                "sequence_id": _sequence_id(textbook_id, title),
                "concept_ids": concept_ids,
                "concept_names": concept_names,
                "kg_mapping_status": "pending_production_kg",
                "primary_concept_id": concept_ids[0] if concept_ids else "",
                "primary_concept_name": concept_names[0] if concept_names else "",
                "question_type": _kind_from_text(asset_question),
                "target_stage": 4 if "证明" in asset_question else 3,
                "stage_rationale": "pending subject-matter review",
                "literacy_tags": [],
                "item_kind": item_kind,
                "question": asset_question,
                "answer_spec": {},
                "hints": [],
                "rubric": [],
                "source": "textbook",
                "trust_status": "machine_reviewed",
                "stem_source": "textbook",
                "stem_review_status": "source_verified",
                "solution_source": "textbook_pending_review",
                "solution_review_status": "unreviewed",
                "review_status": "draft_subject_review",
                "source_hash": digest,
                "parent_item_id": parent_item_id if subitem else None,
                "extraction": {
                    "section": title,
                    "page": page,
                    "markdown_line": line_no,
                    "item_number": number,
                    "subitem_number": subitem or None,
                    "shared_stem": shared_stem,
                },
            })
    return rows


def extract_case(case_name: str) -> dict:
    spec = ASSETS[case_name]
    lines = spec["path"].read_text(encoding="utf-8").splitlines()
    rows: list[dict] = []
    for title, page in spec["exercise_sections"].items():
        rows.extend(_extract_section(lines, title, page, item_kind="exercise_item",
                                     textbook_id=spec["textbook_id"],
                                     legacy_textbook_id=spec["legacy_textbook_id"],
                                     original_textbook_name=textbook_spec(spec["textbook_id"]).display_name,
                                     concept_ids=spec["concept_ids"], concept_names=spec["concept_names"]))
    for title, page in spec["example_sections"].items():
        rows.extend(_extract_section(lines, title, page, item_kind="worked_example",
                                     textbook_id=spec["textbook_id"],
                                     legacy_textbook_id=spec["legacy_textbook_id"],
                                     original_textbook_name=textbook_spec(spec["textbook_id"]).display_name,
                                     concept_ids=spec["concept_ids"], concept_names=spec["concept_names"]))
    return {"case": case_name, "source": str(spec["path"]), "items": rows,
            "counts": {"exercise_item": sum(row["item_kind"] == "exercise_item" for row in rows),
                       "worked_example": sum(row["item_kind"] == "worked_example" for row in rows)}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=[*ASSETS, "all"], default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "data/practice/textbook_candidates.json")
    parser.add_argument("--report", type=Path, default=ROOT / "data/practice/textbook-extraction-report.json")
    args = parser.parse_args()
    cases = list(ASSETS) if args.case == "all" else [args.case]
    extracted = [extract_case(case) for case in cases]
    payload = [dict(item, case=case["case"]) for case in extracted for item in case["items"]]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    isolated = [
        {"id": row["id"], "case": row["case"], "source_locator": row["source_locator"],
         "question_excerpt": row["question"][:180],
         "errors": _candidate_errors(row)}
        for row in payload
    ]
    report = {
        "status": "blocked" if isolated else "ready",
        "candidate_count": len(payload),
        "exercise_count": sum(row["item_kind"] == "exercise_item" for row in payload),
        "worked_example_count": sum(row["item_kind"] == "worked_example" for row in payload),
        "isolated": isolated,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({case["case"]: case["counts"] for case in extracted}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
