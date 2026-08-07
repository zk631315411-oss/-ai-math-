"""Seed the small, reviewed textbook pool used by the competition demo."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from app.db.connection import init_db
from app.services.practice.repository import add_item
from app.textbooks import CANONICAL_TEXTBOOK_IDS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/practice/mvp_items.json"


def _validate(item: dict) -> list[str]:
    errors: list[str] = []
    if not item.get("id"):
        errors.append("missing_id")
    if item.get("textbook_id") not in CANONICAL_TEXTBOOK_IDS:
        errors.append("invalid_textbook_id")
    for field in ("source_asset_id", "source_locator", "original_textbook_name", "question"):
        if not str(item.get(field) or "").strip():
            errors.append(f"missing_{field}")
    item_kind = item.get("item_kind")
    if item_kind not in {"exercise_item", "worked_example"}:
        errors.append("invalid_mvp_item_kind")
    if item.get("kg_mapping_status") != "verified":
        errors.append("kg_mapping_not_verified")
    if item.get("review_status") != "approved":
        errors.append("review_not_approved")
    if item.get("solution_review_status") not in {"reviewed", "teacher_approved"}:
        errors.append("solution_not_reviewed")
    if item.get("stem_review_status") not in {"source_verified", "reviewed", "teacher_approved"}:
        errors.append("stem_not_reviewed")
    expected_trust = {"teacher_approved"} if item_kind == "exercise_item" else {
        "machine_verified", "teacher_approved",
    }
    if item.get("trust_status") not in expected_trust:
        errors.append("item_not_trusted")
    if item.get("diagnostic_goal") not in {"definition", "application", "proof", "counterexample", "transfer"}:
        errors.append("invalid_diagnostic_goal")
    if not item.get("concept_ids") or not item.get("primary_concept_id"):
        errors.append("missing_kg_mapping")
    if not isinstance(item.get("answer_spec"), dict) or not item["answer_spec"].get("reference"):
        errors.append("missing_reference_answer")
    if not isinstance(item.get("hints"), list) or len(item["hints"]) != 3:
        errors.append("requires_three_hints")
    if not isinstance(item.get("rubric"), list) or not item["rubric"]:
        errors.append("missing_rubric")
    return errors


def seed(input_path: Path = DEFAULT_INPUT) -> dict:
    init_db()
    rows = json.loads(input_path.read_text(encoding="utf-8"))
    imported: list[str] = []
    isolated: list[dict] = []
    for raw in rows:
        item = dict(raw)
        errors = _validate(item)
        if errors:
            isolated.append({"id": item.get("id"), "errors": errors})
            continue
        item["source_hash"] = hashlib.sha256(item["question"].encode("utf-8")).hexdigest()
        add_item(item)
        imported.append(item["id"])
    report = {
        "mode": "competition_mvp",
        "input": str(input_path),
        "expected_count": len(rows),
        "exercise_count": sum(row.get("item_kind") == "exercise_item" for row in rows),
        "worked_example_count": sum(row.get("item_kind") == "worked_example" for row in rows),
        "imported": imported,
        "isolated": isolated,
        "status": "ready" if len(imported) == len(rows) else "blocked",
    }
    report_path = ROOT / "data/practice/mvp-seed-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()
    report = seed(args.input)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
