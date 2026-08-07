"""Import reviewed textbook practice assets into the v2 item bank."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.db.connection import init_db
from app.services.practice.repository import add_item
from app.services.practice.kg_validation import verify_item_kg_mapping
from app.textbooks import CANONICAL_TEXTBOOK_IDS


def _source_hash(item: dict) -> str:
    return hashlib.sha256(str(item.get("question") or "").encode("utf-8")).hexdigest()


def validate_item(item: dict) -> list[str]:
    errors: list[str] = []
    if not item.get("id"): errors.append("missing_id")
    if item.get("textbook_id") not in CANONICAL_TEXTBOOK_IDS:
        errors.append("invalid_textbook_id")
    if not item.get("source_asset_id"): errors.append("missing_source_asset_id")
    if not item.get("original_textbook_name"): errors.append("missing_original_textbook_name")
    locator = str(item.get("source_locator") or "")
    if not locator or not any(token in locator for token in ("page", "p.", "页", "题")):
        errors.append("missing_page_or_problem_locator")
    if not item.get("question"): errors.append("missing_question")
    if not item.get("concept_ids") or not item.get("primary_concept_id"):
        errors.append("missing_kg_mapping")
    if not item.get("concept_names") or not item.get("primary_concept_name"):
        errors.append("missing_kg_name")
    if item.get("kg_mapping_status") != "verified":
        errors.append("kg_mapping_not_verified")
    if item.get("item_kind", "exercise_item") not in {"exercise_item", "worked_example"}:
        errors.append("invalid_item_kind")
    if item.get("stem_review_status") not in {"source_verified", "reviewed", "teacher_approved"}:
        errors.append("stem_not_reviewed")
    if item.get("diagnostic_goal") not in {"definition", "application", "proof", "counterexample", "transfer"}:
        errors.append("invalid_diagnostic_goal")
    answer_spec = item.get("answer_spec") or {}
    if item.get("item_kind", "exercise_item") == "exercise_item":
        if not isinstance(answer_spec, dict) or not str(answer_spec.get("reference") or "").strip():
            errors.append("missing_reviewed_reference_answer")
        if not isinstance(item.get("hints"), list) or not 1 <= len(item["hints"]) <= 3:
            errors.append("missing_three_level_hints")
        if item.get("question_type") == "proof" and not isinstance(item.get("rubric"), list):
            errors.append("missing_proof_rubric")
    if item.get("solution_review_status") not in {"reviewed", "teacher_approved"}:
        errors.append("solution_not_reviewed")
    if item.get("review_status") != "approved":
        errors.append("subject_review_not_approved")
    return errors


def import_items(input_path: Path, report_path: Path) -> dict:
    rows = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list): raise ValueError("input must be a JSON array")
    imported: list[str] = []
    isolated: list[dict] = []
    for raw in rows:
        item = dict(raw)
        errors = validate_item(item)
        if not errors:
            try:
                errors.extend(verify_item_kg_mapping(item))
            except Exception as exc:
                errors.append(f"kg_preflight_failed:{type(exc).__name__}")
        if errors:
            isolated.append({"id": item.get("id"), "source_locator": item.get("source_locator", ""),
                             "question_excerpt": str(item.get("question", ""))[:160], "errors": errors})
            continue
        item["source"] = "textbook"
        item["trust_status"] = "teacher_approved"
        item.setdefault("stem_source", "textbook")
        item.setdefault("solution_source", "textbook")
        item.setdefault("solution_review_status", "reviewed")
        item.setdefault("source_hash", _source_hash(item))
        add_item(item)
        imported.append(item["id"])
    report = {"input": str(input_path), "imported": imported, "isolated": isolated,
              "status": "blocked" if isolated else "ready"}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--report", type=Path, default=Path("data/practice/import-report.json"))
    args = parser.parse_args()
    init_db()
    report = import_items(args.input, args.report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
