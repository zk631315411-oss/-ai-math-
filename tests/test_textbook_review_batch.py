from __future__ import annotations

import json
from pathlib import Path
import unittest

from scripts.build_textbook_review_batch import build_batch


ROOT = Path(__file__).resolve().parents[1]


class TextbookReviewBatchTests(unittest.TestCase):
    def test_default_review_input_is_separate_from_generated_batch(self) -> None:
        import inspect

        source = inspect.getsource(__import__("scripts.build_textbook_review_batch", fromlist=["main"]).main)
        self.assertIn("textbook_review_overrides.json", source)

    def test_deferred_full_bank_remains_blocked_by_mvp_annotation_and_human_gates(self) -> None:
        rows, report = build_batch(
            ROOT / "data/practice/textbook_candidates.json",
            ROOT / "data/practice/textbook_review_overrides.json",
        )
        self.assertEqual(len(rows), 119)
        self.assertEqual(report["exercise_count"], 67)
        self.assertEqual(report["worked_example_count"], 52)
        self.assertEqual(report["edited_count"], 3)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["missing_source_locators"], [])
        edited_locators = {
            row["source_locator"]
            for row in json.loads(
                (ROOT / "data/practice/textbook_review_overrides.json").read_text(encoding="utf-8")
            )
        }
        for item in report["items"]:
            if item["source_locator"] not in edited_locators:
                continue
            self.assertEqual(
                set(item["errors"]),
                {
                    "invalid_diagnostic_goal",
                    "kg_mapping_not_verified",
                    "solution_not_reviewed",
                    "subject_review_not_approved",
                },
            )


if __name__ == "__main__":
    unittest.main()
