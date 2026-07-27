from __future__ import annotations

import asyncio
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import BackgroundTasks, HTTPException

from app.auth.jwt_handler import create_access_token
from app.config import config
from app.db.connection import get_conn, init_db
from app.db.exercise_bank_db import (
    attach_user_states,
    get_exercise,
    get_user_exercise_state,
    list_by_sequence_id,
    save_exercise,
)
from app.models.schemas import ExerciseSubmitRequest
from app.routers.exercise import request_hint, submit_exercise_answer


class ExerciseUserIsolationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = f"{self.temp_dir.name}/exercise-isolation.db"
        init_db()

        self.user_a = "student-a"
        self.user_b = "student-b"
        self.auth_a = f"Bearer {create_access_token({'user_id': self.user_a})}"
        self.auth_b = f"Bearer {create_access_token({'user_id': self.user_b})}"
        self.exercise_id = save_exercise(
            user_id="__system__",
            topic="线性方程组",
            difficulty="basic",
            target_stage=2,
            question="求方程组的通解。",
            answer="x_1=t+2, x_2=t, x_3=-1",
            hints=["先消元", "确定自由变量", "写出通解"],
            sequence_id="V1-C01-S01",
        )
        conn = get_conn()
        conn.execute(
            "UPDATE exercise_bank SET source='textbook' WHERE id=?",
            (self.exercise_id,),
        )
        conn.commit()
        conn.close()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_hint_and_answer_state_are_isolated_from_other_students(self) -> None:
        hint = asyncio.run(request_hint(self.exercise_id, authorization=self.auth_a))
        self.assertEqual(hint.hint_level, 1)
        self.assertEqual(hint.hint, "先消元")

        state_a = get_user_exercise_state(self.user_a, self.exercise_id)
        state_b = get_user_exercise_state(self.user_b, self.exercise_id)
        self.assertEqual(state_a["hint_level"], 1)
        self.assertIsNone(state_b)

        with patch(
            "app.services.llm_service.llm_service.chat_async",
            new=AsyncMock(return_value='{"is_correct": true, "grading_feedback": "通解正确"}'),
        ):
            result = asyncio.run(
                submit_exercise_answer(
                    self.exercise_id,
                    ExerciseSubmitRequest(student_answer="x_1=t+2, x_2=t, x_3=-1"),
                    BackgroundTasks(),
                    authorization=self.auth_a,
                )
            )

        self.assertTrue(result.is_correct)
        self.assertEqual(result.grading_status, "completed")

        template = get_exercise(self.exercise_id)
        self.assertEqual(template["user_id"], "__system__")
        self.assertEqual(template["hint_level"], 0)
        self.assertEqual(template["is_answered"], 0)
        self.assertIsNone(template["student_answer"])

        view_a = attach_user_states([template], self.user_a)[0]
        view_b = attach_user_states([template], self.user_b)[0]
        self.assertTrue(view_a["is_answered"])
        self.assertEqual(view_a["student_answer"], "x_1=t+2, x_2=t, x_3=-1")
        self.assertEqual(view_a["hint_level"], 1)
        self.assertFalse(view_b["is_answered"])
        self.assertIsNone(view_b["student_answer"])
        self.assertEqual(view_b["hint_level"], 0)

        conn = get_conn()
        attempt = conn.execute(
            "SELECT user_id, grading_status FROM exercise_attempts WHERE exercise_id=?",
            (self.exercise_id,),
        ).fetchone()
        conn.close()
        self.assertEqual(attempt["user_id"], self.user_a)
        self.assertEqual(attempt["grading_status"], "valid")

    def test_grading_failure_is_retryable_and_not_a_wrong_answer(self) -> None:
        with patch(
            "app.services.llm_service.llm_service.chat_async",
            new=AsyncMock(side_effect=RuntimeError("model unavailable")),
        ):
            result = asyncio.run(
                submit_exercise_answer(
                    self.exercise_id,
                    ExerciseSubmitRequest(student_answer="尝试答案"),
                    BackgroundTasks(),
                    authorization=self.auth_b,
                )
            )

        self.assertFalse(result.is_correct)
        self.assertEqual(result.grading_status, "failed")
        state = get_user_exercise_state(self.user_b, self.exercise_id)
        self.assertEqual(state["grading_status"], "failed")
        self.assertIsNone(state["is_correct"])

        conn = get_conn()
        attempt = conn.execute(
            "SELECT grading_status, analysis_status FROM exercise_attempts WHERE user_id=?",
            (self.user_b,),
        ).fetchone()
        conn.close()
        self.assertEqual(attempt["grading_status"], "invalid")
        self.assertEqual(attempt["analysis_status"], "ready")

    def test_low_quality_textbook_question_is_filtered(self) -> None:
        conn = get_conn()
        conn.execute(
            "UPDATE exercise_bank SET quality_score=-1 WHERE id=?",
            (self.exercise_id,),
        )
        conn.commit()
        conn.close()
        self.assertEqual(list_by_sequence_id("V1-C01-S01"), [])

    def test_token_user_mismatch_is_rejected(self) -> None:
        from app.routers.exercise import _validated_user_id

        with self.assertRaises(HTTPException) as context:
            _validated_user_id(self.auth_a, self.user_b)
        self.assertEqual(context.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
