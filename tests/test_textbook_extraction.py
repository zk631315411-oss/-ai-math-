from __future__ import annotations

import unittest

from scripts.extract_textbook_practice import extract_case
from scripts.import_textbook_items import validate_item


class TextbookExtractionTests(unittest.TestCase):
    def test_three_demo_cases_extract_exercises_and_examples(self) -> None:
        matrix = extract_case("matrix_rank_and_system")
        proof = extract_case("linear_independence_proof")
        limits = extract_case("limit_calculation_concept_misuse")
        self.assertGreater(matrix["counts"]["exercise_item"], 0)
        self.assertGreater(matrix["counts"]["worked_example"], 0)
        self.assertGreater(proof["counts"]["exercise_item"], 0)
        self.assertGreater(proof["counts"]["worked_example"], 0)
        self.assertGreater(limits["counts"]["exercise_item"], 0)

    def test_extracted_item_has_page_locator_and_source_hash(self) -> None:
        item = extract_case("linear_independence_proof")["items"][0]
        self.assertEqual(item["textbook_id"], "gaodai_shang")
        self.assertTrue(item["source_asset_id"].startswith("gaodai-qiuweisheng-upper:"))
        self.assertEqual(item["original_textbook_name"], "高等代数（上册）丘维声")
        self.assertIn("page:", item["source_locator"])
        self.assertIsInstance(item["source_page"], int)
        self.assertTrue(item["source_problem_no"])
        self.assertEqual(len(item["source_hash"]), 64)
        self.assertTrue(item["primary_concept_id"])

    def test_structural_markers_are_removed_from_stems(self) -> None:
        items = extract_case("matrix_rank_and_system")["items"]
        self.assertTrue(items)
        self.assertTrue(all("##### 题" not in item["question"] for item in items))

    def test_independent_subquestions_keep_shared_parent_trace(self) -> None:
        exercises = [
            item for item in extract_case("linear_independence_proof")["items"]
            if item["item_kind"] == "exercise_item"
        ]
        first_problem = [
            item for item in exercises
            if "; item:1;" in item["source_locator"]
        ]
        self.assertEqual(len(first_problem), 3)
        self.assertEqual(len({item["parent_item_id"] for item in first_problem}), 1)
        self.assertEqual(
            {item["extraction"]["subitem_number"] for item in first_problem},
            {"1", "2", "3"},
        )
        self.assertTrue(all("; subitem:" in item["source_locator"] for item in first_problem))

    def test_question_type_distinguishes_calculation_concept_and_proof(self) -> None:
        matrix = extract_case("matrix_rank_and_system")["items"]
        calculation = next(item for item in matrix if "; item:1;" in item["source_locator"])
        proof = next(item for item in matrix if "; item:6;" in item["source_locator"])
        concept = extract_case("linear_independence_proof")["items"][0]
        self.assertEqual(calculation["question_type"], "calculation")
        self.assertEqual(proof["question_type"], "proof")
        self.assertEqual(concept["question_type"], "concept")

    def test_unreviewed_candidates_are_blocked_from_import(self) -> None:
        item = extract_case("matrix_rank_and_system")["items"][0]
        errors = validate_item(item)
        self.assertIn("missing_reviewed_reference_answer", errors)
        self.assertIn("kg_mapping_not_verified", errors)
        self.assertIn("solution_not_reviewed", errors)
        self.assertNotIn("stem_not_reviewed", errors)


if __name__ == "__main__":
    unittest.main()
