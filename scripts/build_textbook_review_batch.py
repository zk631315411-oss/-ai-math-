"""Apply review drafts without mutating the immutable extraction inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.import_textbook_items import validate_item


REVIEWABLE_FIELDS = {
    "annotation_status", "review_status", "kg_mapping_status",
    "concept_ids", "concept_names", "primary_concept_id", "primary_concept_name",
    "secondary_concept_ids", "prerequisite_concept_ids", "prerequisite_concept_names",
    "question_type", "target_stage", "stage_rationale", "literacy_tags", "difficulty",
    "answer_spec", "hints", "rubric", "stem_review_status", "solution_source",
    "solution_review_status", "trust_status",
}


def build_batch(candidates_path: Path, reviews_path: Path) -> tuple[list[dict], dict]:
    candidates = json.loads(candidates_path.read_text(encoding="utf-8"))
    reviews = json.loads(reviews_path.read_text(encoding="utf-8")) if reviews_path.exists() else []
    candidates_by_locator = {row["source_locator"]: row for row in candidates}
    reviews_by_locator = {row["source_locator"]: row for row in reviews}
    reviewed: list[dict] = []
    missing = sorted(set(reviews_by_locator) - set(candidates_by_locator))
    for source in candidates:
        locator = source["source_locator"]
        override = reviews_by_locator.get(locator, {})
        item = dict(source)
        item.update({key: value for key, value in override.items() if key in REVIEWABLE_FIELDS})
        item["source_locator"] = locator
        item["review_status"] = item.get("review_status") or item.get(
            "annotation_status", "draft_subject_review"
        )
        item["annotation_status"] = item["review_status"]
        reviewed.append(item)
    report = {
        "status": "blocked" if missing or any(validate_item(item) for item in reviewed) else "ready",
        "candidate_count": len(reviewed),
        "exercise_count": sum(item.get("item_kind") == "exercise_item" for item in reviewed),
        "worked_example_count": sum(item.get("item_kind") == "worked_example" for item in reviewed),
        "edited_count": sum(item["source_locator"] in reviews_by_locator for item in reviewed),
        "missing_source_locators": missing,
        "items": [
            {
                "id": item["id"],
                "source_locator": item["source_locator"],
                "annotation_status": item.get("annotation_status", "draft"),
                "errors": validate_item(item),
            }
            for item in reviewed
        ],
    }
    return reviewed, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--candidates",
        type=Path,
        default=ROOT / "data/practice/textbook_candidates.json",
    )
    parser.add_argument(
        "--reviews", "--overrides",
        dest="reviews",
        type=Path,
        # Keep reviewer edits separate from the generated batch.  This makes
        # the batch reproducible and prevents a rerun from treating generated
        # fields as new human annotations.
        default=ROOT / "data/practice/textbook_review_overrides.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data/practice/textbook_review_batch.json",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=ROOT / "data/practice/textbook-review-report.json",
    )
    args = parser.parse_args()
    rows, report = build_batch(args.candidates, args.reviews)
    args.output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 2 if report["status"] == "blocked" else 0


if __name__ == "__main__":
    raise SystemExit(main())
