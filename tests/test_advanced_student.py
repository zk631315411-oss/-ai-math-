"""Deterministic advanced-student diagnosis test with an isolated database."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from app.config import config
from app.services.diagnosis.contracts import KGStageNode


ADVANCED_RESPONSES = [
    (
        "因为特征多项式在代数闭域上分解为一次因子，所以 Jordan 标准形可以按特征值分块；"
        "若底域不是代数闭域，则应改用有理标准形和不可约因子描述同一个模结构。"
    ),
    (
        "由 Cayley-Hamilton 定理，若有限维矩阵的全部特征值为零，则特征多项式为 x^n，"
        "代入矩阵可得 A^n=0，因此它必为幂零矩阵。"
    ),
    (
        "正规矩阵可酉对角化，因此不存在不可对角化的正规复矩阵；Schur 分解适用于任意复方阵，"
        "而正规性恰好保证 Schur 上三角阵进一步退化为对角阵。"
    ),
]


class AdvancedStudentDiagnosisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = config.DB_PATH
        self.old_mode = config.DIAGNOSIS_V2_MODE
        self.old_dialogue_mode = config.DIALOGUE_STATE_MODE
        config.DB_PATH = os.path.join(self.temp_dir.name, "advanced-student.db")
        config.DIAGNOSIS_V2_MODE = "full"
        config.DIALOGUE_STATE_MODE = "shadow"
        from app.db.connection import init_db

        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.old_db
        config.DIAGNOSIS_V2_MODE = self.old_mode
        config.DIALOGUE_STATE_MODE = self.old_dialogue_mode
        self.temp_dir.cleanup()

    def test_advanced_reasoning_projects_stage_four_once(self) -> None:
        self._seed_advanced_turns()
        from app.services.diagnostic_worker import run_diagnostic_batch
        from app.services.llm_service import llm_service

        kg_node = KGStageNode("kg-eigen-structure", "特征值与特征向量", "Concept")
        with patch(
            "app.services.diagnosis.adapters.get_stage_candidates_by_sequence_id",
            return_value=([kg_node], []),
        ), patch.object(llm_service, "chat_async", side_effect=_fake_advanced_scorer):
            first_run = asyncio.run(run_diagnostic_batch("advanced-student"))
            second_run = asyncio.run(run_diagnostic_batch("advanced-student"))

        self.assertTrue(first_run)
        self.assertFalse(second_run, "terminal diagnosis runs must not be scored twice")

        from app.db.connection import get_conn

        conn = get_conn()
        try:
            stage = conn.execute(
                """SELECT stage, confidence, evidence FROM knowledge_stages
                   WHERE user_id=? AND concept_name=?""",
                ("advanced-student", "特征值与特征向量"),
            ).fetchone()
            runs = conn.execute(
                "SELECT source_id,scorer_type,status,error_reason FROM diagnosis_runs WHERE source_type='qa_turn'"
            ).fetchall()
        finally:
            conn.close()

        self.assertIsNotNone(stage)
        self.assertEqual(stage["stage"], 4)
        self.assertGreaterEqual(stage["confidence"], 0.7)
        self.assertGreaterEqual(len(json.loads(stage["evidence"])), 2)
        self.assertEqual(len(runs), 6)
        failures = [dict(row) for row in runs if row["status"] != "success"]
        self.assertEqual(failures, [])

    def _seed_advanced_turns(self) -> None:
        from app.services.qa.contracts import QATurnRecord
        from app.services.qa.turn_store import save_turn_record

        for index, student_text in enumerate(ADVANCED_RESPONSES):
            record = QATurnRecord(
                turn_id=f"advanced-turn-{index}",
                user_id="advanced-student",
                chat_id=f"advanced-chat-{index}",
                marker_id="advanced-thread",
                input_type="text",
                question=student_text,
                answer=f"AI 对第 {index + 1} 条高阶推理的反馈",
                apprenticeship_level="fading",
                textbook_id="高代上-丘维声",
                sequence_id="V1-C02-S05",
                context_snapshot={"history": []},
                created_at=f"2026-08-05T10:00:0{index}",
            )
            self.assertTrue(
                save_turn_record(record, write_chat_log=False, update_chat_history=False)
            )


async def _fake_advanced_scorer(messages, **_) -> str:
    prompt = messages[-1]["content"]
    if "评分 QA 中学生自己展示" in prompt:
        student_text = _line_value(prompt, "学生当前原文：")
        strength = "probable" if "上一轮脚手架：unknown" in prompt else "certain"
        return json.dumps({
            "observations": [{
                "concept_id": "kg-eigen-structure",
                "concept_name": "特征值与特征向量",
                "observed_stage": 4,
                "direction": "positive",
                "strength": strength,
                "behavior": "proof",
                "student_quote": student_text,
                "dialogue_state_action": "accepted",
                "dialogue_state_reason": "independent_evidence",
                "dialogue_state_rationale": "学生独立展示了结构化推理",
            }],
        }, ensure_ascii=False)
    if "只评价 QA 中学生原文" in prompt:
        student_text = _line_value(prompt, "学生原文：")
        strength = "probable" if "上一轮脚手架：unknown" in prompt else "certain"
        return json.dumps({
            "observations": [{
                "dimension": "lr",
                "facet": "technical",
                "status": "observed",
                "direction": "positive",
                "strength": strength,
                "student_quote": student_text,
            }],
        }, ensure_ascii=False)
    raise AssertionError(f"unexpected scorer prompt: {prompt[:100]}")


def _line_value(prompt: str, prefix: str) -> str:
    for line in prompt.splitlines():
        if line.startswith(prefix):
            return line[len(prefix):]
    raise AssertionError(f"missing prompt field: {prefix}")


if __name__ == "__main__":
    unittest.main()
