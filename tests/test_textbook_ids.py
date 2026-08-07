from __future__ import annotations

import unittest

from pydantic import ValidationError
from fastapi.testclient import TestClient

from app.models.schemas import ExerciseGenerateRequest, QARequest
from app.routers.profile import TextbookPreferenceRequest
from app.textbooks import (
    CANONICAL_TEXTBOOK_IDS,
    TextbookId,
    canonical_textbook_id,
    cumulative_textbook_ids,
    section_node_id,
    textbook_spec,
)


class TextbookRegistryTests(unittest.TestCase):
    def test_registry_contains_exactly_four_canonical_ids(self) -> None:
        self.assertEqual(
            CANONICAL_TEXTBOOK_IDS,
            {"gaodai_shang", "gaodai_xia", "gaoshu_shang", "gaoshu_xia"},
        )
        for textbook_id in TextbookId:
            spec = textbook_spec(textbook_id)
            self.assertEqual(spec.neo4j_prefix, textbook_id.value)
            self.assertTrue(spec.pdf_path)

    def test_unknown_and_legacy_ids_are_rejected(self) -> None:
        for value in ("高代上-丘维声", "gaodai-qiuweisheng-upper", "unknown"):
            with self.assertRaises(ValueError):
                canonical_textbook_id(value)
            with self.assertRaises(ValidationError):
                QARequest(question="test", textbook_id=value)
            with self.assertRaises(ValidationError):
                ExerciseGenerateRequest(user_id="u", page_number=1, textbook_id=value)
            with self.assertRaises(ValidationError):
                TextbookPreferenceRequest(textbook_id=value, page_number=1)

    def test_section_and_cumulative_scope_use_canonical_identity(self) -> None:
        self.assertEqual(
            section_node_id("gaodai_shang", "V1-C03-S02"),
            "gaodai_shang:C03:S02",
        )
        self.assertEqual(
            cumulative_textbook_ids("gaoshu_xia"),
            ["gaoshu_shang", "gaoshu_xia"],
        )

    def test_public_api_returns_422_for_legacy_ids(self) -> None:
        from app.main import app

        client = TestClient(app)
        qa = client.post(
            "/api/qa/solve-stream",
            json={"question": "test", "textbook_id": "高代上-丘维声"},
        )
        exercise = client.get(
            "/api/exercise/by-page",
            params={"page_number": 1, "user_id": "u", "textbook_id": "高代上-丘维声"},
        )
        preference = client.post(
            "/api/profile/textbook-preference",
            json={"textbook_id": "高代上-丘维声", "page_number": 1},
        )
        self.assertEqual(qa.status_code, 422)
        self.assertEqual(exercise.status_code, 422)
        self.assertEqual(preference.status_code, 422)


if __name__ == "__main__":
    unittest.main()
