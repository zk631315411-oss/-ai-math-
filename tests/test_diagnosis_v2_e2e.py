"""Synthetic diagnosis V2 E2E: source records -> scorers -> ledger -> profiles."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app.config import config
from app.services.diagnosis.contracts import KGStageNode


class DiagnosisV2SyntheticE2E(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = config.DB_PATH
        self.old_mode = config.DIAGNOSIS_V2_MODE
        self.old_dialogue_mode = config.DIALOGUE_STATE_MODE
        self.old_dialogue_version = config.DIALOGUE_STATE_MODEL_VERSION
        config.DB_PATH = os.path.join(self.temp_dir.name, "diagnosis-v2-e2e.db")
        config.DIAGNOSIS_V2_MODE = "full"
        config.DIALOGUE_STATE_MODE = "shadow"
        config.DIALOGUE_STATE_MODEL_VERSION = "ordinal-bayes-v1"
        from app.db.connection import init_db

        init_db()

    def tearDown(self):
        config.DB_PATH = self.old_db
        config.DIAGNOSIS_V2_MODE = self.old_mode
        config.DIALOGUE_STATE_MODE = self.old_dialogue_mode
        config.DIALOGUE_STATE_MODEL_VERSION = self.old_dialogue_version
        self.temp_dir.cleanup()

    def test_mixed_qa_and_exercise_events_update_long_term_profiles(self):
        self._seed_qa_turns()
        self._seed_exercise_attempts()

        from app.services.llm_service import llm_service
        from app.services.diagnostic_worker import run_diagnostic_batch

        with patch(
            "app.services.diagnosis.adapters.get_stage_candidates_by_sequence_id",
            return_value=([KGStageNode("kg-linear-independent", "线性无关", "Concept")], []),
        ), patch.object(llm_service, "chat_async", side_effect=_fake_profile_llm):
            first_run = asyncio.run(run_diagnostic_batch("synthetic-user"))
            second_run = asyncio.run(run_diagnostic_batch("synthetic-user"))

        self.assertTrue(first_run)
        self.assertFalse(second_run, "terminal sources must not be scored twice")

        from app.db.connection import get_conn

        conn = get_conn()
        try:
            stage = conn.execute(
                """
                SELECT stage, confidence, projection_version
                FROM knowledge_stages
                WHERE user_id='synthetic-user' AND concept_name='线性无关'
                """
            ).fetchone()
            dialogue_state = conn.execute(
                """
                SELECT map_stage, evidence_count, probabilities_json
                FROM dialogue_knowledge_states
                WHERE user_id='synthetic-user' AND concept_id='kg-linear-independent'
                  AND model_version='ordinal-bayes-v1'
                """
            ).fetchone()
            profile = conn.execute(
                "SELECT lr_technical, projection_version FROM math_profiles WHERE user_id='synthetic-user'"
            ).fetchone()
            runs = conn.execute(
                "SELECT source_type, scorer_type, status, model_name FROM diagnosis_runs ORDER BY source_type, source_id, scorer_type"
            ).fetchall()
            evidence_count = conn.execute("SELECT COUNT(*) FROM diagnostic_evidence").fetchone()[0]
            source_count = conn.execute(
                "SELECT COUNT(DISTINCT source_type || ':' || source_id) FROM diagnostic_evidence"
            ).fetchone()[0]
            window = conn.execute(
                "SELECT event_count, status FROM dimension_windows WHERE user_id='synthetic-user'"
            ).fetchone()
            assessment_count = conn.execute(
                "SELECT COUNT(*) FROM question_assessments WHERE user_id='synthetic-user'"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertIsNotNone(stage)
        self.assertEqual(stage["stage"], 4)
        self.assertGreaterEqual(stage["confidence"], 0.8)
        self.assertEqual(stage["projection_version"], "v2")
        self.assertIsNotNone(dialogue_state)
        self.assertEqual(dialogue_state["evidence_count"], 3)
        self.assertAlmostEqual(sum(json.loads(dialogue_state["probabilities_json"])), 1.0, places=8)
        self.assertEqual(profile["lr_technical"], 1)
        self.assertEqual(profile["projection_version"], "v2")
        self.assertEqual(len(runs), 10)  # 5 events x independent Stage/dimension scorers
        self.assertTrue(all(row["status"] == "success" for row in runs))
        self.assertTrue(all(row["model_name"] == config.PROFILE_LLM_MODEL for row in runs))
        self.assertEqual(evidence_count, 10)
        self.assertEqual(source_count, 5)
        self.assertEqual(window["event_count"], 5)
        self.assertEqual(window["status"], "closed")
        self.assertEqual(assessment_count, 1)

        print(
            "E2E_SUMMARY",
            json.dumps(
                {
                    "sources": source_count,
                    "runs": len(runs),
                    "evidence": evidence_count,
                    "stage": stage["stage"],
                    "stage_confidence": stage["confidence"],
                    "lr_technical": profile["lr_technical"],
                    "dimension_window": window["status"],
                },
                ensure_ascii=False,
            ),
        )

    def _seed_qa_turns(self):
        from app.services.qa.contracts import QATurnRecord
        from app.services.qa.turn_store import save_turn_record

        for index in range(3):
            student_text = (
                f"因为线性组合等于零，所以第{index + 1}次推导中所有系数都为零，"
                "故这个向量组线性无关。"
            )
            record = QATurnRecord(
                turn_id=f"qa-turn-{index}",
                user_id="synthetic-user",
                chat_id=f"chat-row-{index}",
                marker_id="synthetic-thread",
                input_type="text",
                question=student_text,
                answer=f"AI对第{index + 1}次学生推导的反馈",
                apprenticeship_level="fading",
                textbook_id="高代上-丘维声",
                sequence_id="V1-C01-S01",
                context_snapshot={"history": []},
                created_at=f"2026-07-14T10:00:0{index}",
            )
            self.assertTrue(
                save_turn_record(record, write_chat_log=False, update_chat_history=False)
            )

    def _seed_exercise_attempts(self):
        from app.db.diagnosis_v2_db import save_exercise_attempt

        for index in range(2):
            exercise = {
                "id": f"exercise-{index}",
                "user_id": "synthetic-user",
                "sequence_id": "V1-C01-S01",
                "topic": "线性无关",
                "target_stage": 4,
                "difficulty": "normal",
                "question": "证明给定向量组线性无关。",
                "answer": "设线性组合为零并证明所有系数为零。",
                "hint_level": 0,
            }
            answer = (
                f"设第{index + 1}组向量的线性组合等于零，因为比较各分量可得"
                "每个系数均为零，所以该向量组线性无关。"
            )
            save_exercise_attempt(
                exercise=exercise,
                student_answer=answer,
                is_correct=True,
                grading_feedback="证明过程正确且条件完整",
                grader_version="synthetic-grader-v1",
            )


async def _fake_profile_llm(messages, **_):
    prompt = messages[-1]["content"]
    if "评分 QA 中学生自己展示" in prompt:
        student_text = _line_value(prompt, "学生当前原文：")
        strength = "probable" if "上一轮脚手架：unknown" in prompt else "certain"
        return json.dumps({
            "observations": [{
                "concept_id": "kg-linear-independent",
                "concept_name": "线性无关",
                "observed_stage": 4,
                "direction": "positive",
                "strength": strength,
                "behavior": "proof",
                "student_quote": student_text,
                "dialogue_state_action": "accepted",
                "dialogue_state_reason": "independent_evidence",
                "dialogue_state_rationale": "学生独立完成了证明",
            }]
        }, ensure_ascii=False)
    if "只评价 QA 中学生原文" in prompt:
        student_text = _line_value(prompt, "学生原文：")
        strength = "probable" if "上一轮脚手架：unknown" in prompt else "certain"
        return _dimension_result(student_text, strength=strength)
    if "只评价这次练习中学生答案展示的概念" in prompt:
        student_text = _line_value(prompt, "学生答案：")
        return json.dumps({
            "observations": [{
                "concept_id": "kg-linear-independent",
                "concept_name": "线性无关",
                "observed_stage": 4,
                "direction": "positive",
                "strength": "certain",
                "behavior": "proof",
                "student_quote": student_text,
            }]
        }, ensure_ascii=False)
    if "只评价这次练习中学生答案实际展示" in prompt:
        student_text = _line_value(prompt, "学生答案：")
        return _dimension_result(student_text)
    raise AssertionError(f"unexpected scorer prompt: {prompt[:80]}")


def _dimension_result(student_text: str, *, strength: str = "certain") -> str:
    return json.dumps({
        "observations": [{
            "dimension": "lr",
            "facet": "technical",
            "status": "observed",
            "direction": "positive",
            "strength": strength,
            "student_quote": student_text,
        }]
    }, ensure_ascii=False)


def _line_value(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    raise AssertionError(f"missing prompt field: {prefix}")


if __name__ == "__main__":
    unittest.main()
