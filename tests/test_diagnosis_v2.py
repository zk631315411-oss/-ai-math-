"""Deterministic tests for diagnosis V2; no LLM or Neo4j required."""

from __future__ import annotations

import os
import json
import tempfile
import unittest
import uuid
from unittest.mock import patch

from app.config import config
from app.services.diagnosis.adapters import detect_qa_behavior_hints
from app.services.diagnosis.contracts import (
    ExerciseEvidenceInput,
    KGStageNode,
    KGStageRelation,
    QAEvidenceInput,
)
from app.services.diagnosis.scorers import (
    ObservationValidationError,
    _validate_exercise_stage,
    _validate_qa_stage,
    validate_exercise_dimensions,
    validate_qa_dimensions,
)


ACCEPTED_DIALOGUE_DECISION = {
    "dialogue_state_action": "accepted",
    "dialogue_state_reason": "independent_evidence",
    "dialogue_state_rationale": "学生当前回答独立展示了该能力",
}


class ScorerRuleTests(unittest.TestCase):
    def test_branch_history_uses_snapshot_last_three_and_excludes_references(self):
        from app.services.diagnosis.adapters import adapt_qa_turn
        from app.services.diagnosis.scorers import _qa_stage_prompt

        history = [
            {"user": "分支问题一", "assistant": "分支回答一"},
            {"user": "分支问题二", "assistant": "分支回答二"},
            {"user": "失败消息", "assistant": "不应出现", "status": "failed"},
            {"user": "分支问题三", "assistant": "分支回答三"},
            {"user": "分支问题四", "assistant": "分支回答四"},
            {"user": "[用户显式引用的其他分支回答]", "assistant": "兄弟分支答案"},
            {"role": "tool", "content": "工具消息"},
        ]
        row = {
            "id": "branch-turn", "user_id": "u", "question": "当前回答",
            "sequence_id": "", "textbook_id": "", "chat_id": "chat",
            "context_snapshot": json.dumps({"history": history}, ensure_ascii=False),
        }
        with patch(
            "app.services.diagnosis.adapters.get_previous_qa_turn"
        ) as previous:
            event = adapt_qa_turn(row)

        previous.assert_not_called()
        self.assertEqual(
            [item["user"] for item in event.recent_history],
            ["分支问题二", "分支问题三", "分支问题四"],
        )
        self.assertEqual(event.previous_ai_answer, "分支回答四")
        prompt = _qa_stage_prompt(event)
        self.assertNotIn("兄弟分支答案", prompt)
        self.assertNotIn("分支问题一", prompt)

    def test_empty_tree_history_does_not_fall_back_to_marker_lookup(self):
        from app.services.diagnosis.adapters import adapt_qa_turn

        row = {
            "id": "first-tree-turn", "user_id": "u", "question": "当前回答",
            "sequence_id": "", "textbook_id": "", "chat_id": "chat",
            "context_snapshot": json.dumps({
                "input_context": {"tree_id": "tree", "node_id": "node"},
                "history": [],
            }),
        }
        with patch(
            "app.services.diagnosis.adapters.get_previous_qa_turn"
        ) as previous:
            event = adapt_qa_turn(row)

        previous.assert_not_called()
        self.assertEqual(event.recent_history, [])
        self.assertEqual(event.previous_ai_answer, "")

    def test_kg_section_id_keeps_existing_v44_convention(self):
        from app.services.diagnosis.diagnosis_service import _v44_section_id

        self.assertEqual(
            _v44_section_id("高代上-丘维声", "V1-C03-S02"),
            "gaodai_shang:C03:S02",
        )
        self.assertEqual(
            _v44_section_id("高数下", "V2-C01-S04-U02"),
            "gaoshu_xia:C01:S04:U02",
        )

    def test_ai_answer_cannot_upgrade_question_only_qa(self):
        event = QAEvidenceInput(
            turn_id="turn-1",
            user_id="user-1",
            student_text="为什么线性无关要这样证明？",
            previous_ai_answer="完整证明：因为……所以……",
            previous_apprenticeship_level="fading",
            kg_candidates=["线性无关"],
            behavior_hints=detect_qa_behavior_hints("为什么线性无关要这样证明？"),
        )
        value = {
            "observations": [{
                "concept_name": "线性无关",
                "observed_stage": 4,
                "direction": "positive",
                "strength": "certain",
                "behavior": "proof",
                "student_quote": "线性无关",
                **ACCEPTED_DIALOGUE_DECISION,
            }]
        }
        with self.assertRaises(ObservationValidationError):
            _validate_qa_stage(value, event)

        dimensions = {
            "observations": [{
                "dimension": "lr", "facet": "technical", "status": "observed",
                "direction": "positive", "strength": "certain", "student_quote": "线性无关",
            }]
        }
        with self.assertRaises(ObservationValidationError):
            validate_qa_dimensions(dimensions, event)

    def test_qa_scaffolding_caps_stage(self):
        event = QAEvidenceInput(
            turn_id="turn-2", user_id="user-1",
            student_text="设系数后由等式可得所有系数为零。",
            previous_apprenticeship_level="coaching",
            kg_candidates=["线性无关"], behavior_hints=["proof"],
        )
        value = {"observations": [{
            "concept_name": "线性无关", "observed_stage": 4,
            "direction": "positive", "strength": "certain", "behavior": "proof",
            "student_quote": "由等式可得所有系数为零",
            **ACCEPTED_DIALOGUE_DECISION,
        }]}
        with self.assertRaises(ObservationValidationError):
            _validate_qa_stage(value, event)

    def test_stage_behavior_caps_do_not_use_keyword_markers(self):
        event = QAEvidenceInput(
            turn_id="turn-stage-boundary", user_id="u",
            student_text="由消元可得 x=2。因为初等行变换保持同解，所以解集不变。",
            previous_apprenticeship_level="fading",
            kg_candidates=["同解方程组"], behavior_hints=["solution_attempt", "proof"],
        )
        solution_only = {"observations": [{
            "concept_name": "同解方程组", "observed_stage": 4,
            "direction": "positive", "strength": "certain",
            "behavior": "solution_attempt", "student_quote": "由消元可得 x=2",
            **ACCEPTED_DIALOGUE_DECISION,
        }]}
        with self.assertRaises(ObservationValidationError):
            _validate_qa_stage(solution_only, event)

        marker_free_explanation = {"observations": [{
            **solution_only["observations"][0],
            "behavior": "explanation",
        }]}
        result = _validate_qa_stage(marker_free_explanation, event)
        self.assertEqual(result["observations"][0]["observed_stage"], 4)

        explanation = {"observations": [{
            "concept_name": "同解方程组", "observed_stage": 4,
            "direction": "positive", "strength": "certain",
            "behavior": "explanation",
            "student_quote": "因为初等行变换保持同解，所以解集不变",
            **ACCEPTED_DIALOGUE_DECISION,
        }]}
        result = _validate_qa_stage(explanation, event)
        self.assertEqual(result["observations"][0]["observed_stage"], 4)

        concise_stage_five = {"observations": [{
            "concept_name": "同解方程组", "observed_stage": 5,
            "direction": "positive", "strength": "certain",
            "behavior": "explanation", "student_quote": "解集不变",
            **ACCEPTED_DIALOGUE_DECISION,
        }]}
        result = _validate_qa_stage(concise_stage_five, event)
        self.assertEqual(result["observations"][0]["observed_stage"], 5)

        proof_stage_five = {"observations": [{
            **concise_stage_five["observations"][0],
            "behavior": "proof",
        }]}
        with self.assertRaises(ObservationValidationError):
            _validate_qa_stage(proof_stage_five, event)

        accepted_hypothesis = {"observations": [{
            **explanation["observations"][0],
            "strength": "hypothesis",
        }]}
        with self.assertRaises(ObservationValidationError):
            _validate_qa_stage(accepted_hypothesis, event)

    def test_part_of_suppresses_only_overlapping_evidence(self):
        child = KGStageNode("solution", "线性方程组的解", "Concept")
        parent = KGStageNode("solution-set", "解集", "Concept")
        relation = KGStageRelation(
            "solution", "线性方程组的解", "PART_OF", "solution-set", "解集"
        )
        shared_quote = "因为线性方程组的解组成解集，所以这里得到同一个解集"
        event = QAEvidenceInput(
            turn_id="part-of-shared", user_id="u", student_text=shared_quote,
            previous_apprenticeship_level="fading",
            kg_candidates=[child.name, parent.name],
            kg_candidate_nodes=[child, parent], kg_candidate_relations=[relation],
            behavior_hints=["proof"],
        )
        shared = {"observations": [
            {
                "concept_id": child.node_id, "concept_name": child.name,
                "observed_stage": 4, "direction": "positive", "strength": "certain",
                "behavior": "explanation", "student_quote": shared_quote,
                **ACCEPTED_DIALOGUE_DECISION,
            },
            {
                "concept_id": parent.node_id, "concept_name": parent.name,
                "observed_stage": 4, "direction": "positive", "strength": "certain",
                "behavior": "explanation", "student_quote": shared_quote,
                **ACCEPTED_DIALOGUE_DECISION,
            },
        ]}
        result = _validate_qa_stage(shared, event)["observations"]
        roles = {item["concept_name"]: item["projection_role"] for item in result}
        self.assertEqual(roles, {child.name: "primary", parent.name: "supporting"})

        child_quote = "由消元可得线性方程组的解为 x=2"
        parent_quote = "因为初等行变换保持同解，所以解集不变"
        distinct_event = QAEvidenceInput(
            turn_id="part-of-distinct", user_id="u",
            student_text=f"{child_quote}。{parent_quote}。",
            previous_apprenticeship_level="fading",
            kg_candidates=[child.name, parent.name],
            kg_candidate_nodes=[child, parent], kg_candidate_relations=[relation],
            behavior_hints=["proof"],
        )
        distinct = {"observations": [
            {
                "concept_id": child.node_id, "concept_name": child.name,
                "observed_stage": 3, "direction": "positive", "strength": "certain",
                "behavior": "solution_attempt", "student_quote": child_quote,
                **ACCEPTED_DIALOGUE_DECISION,
            },
            {
                "concept_id": parent.node_id, "concept_name": parent.name,
                "observed_stage": 4, "direction": "positive", "strength": "certain",
                "behavior": "explanation", "student_quote": parent_quote,
                **ACCEPTED_DIALOGUE_DECISION,
            },
        ]}
        distinct_result = _validate_qa_stage(distinct, distinct_event)["observations"]
        self.assertTrue(all(item["projection_role"] == "primary" for item in distinct_result))

    def test_structured_kg_requires_matching_concept_id_and_name(self):
        node = KGStageNode("kg-same-solution", "同解方程组", "Concept")
        quote = "因为初等行变换保持同解，所以解集不变"
        event = QAEvidenceInput(
            turn_id="kg-id", user_id="u", student_text=quote,
            previous_apprenticeship_level="fading",
            kg_candidates=[node.name], kg_candidate_nodes=[node],
            behavior_hints=["proof"],
        )
        value = {"observations": [{
            "concept_id": "wrong-id", "concept_name": node.name,
            "observed_stage": 4, "direction": "positive", "strength": "certain",
            "behavior": "explanation", "student_quote": quote,
            **ACCEPTED_DIALOGUE_DECISION,
        }]}
        with self.assertRaises(ObservationValidationError):
            _validate_qa_stage(value, event)

    def test_uses_relation_does_not_suppress_stage_evidence(self):
        matrix = KGStageNode("matrix", "增广矩阵", "Concept")
        method = KGStageNode("method", "矩阵消元法", "Method")
        quote = "因为把方程组写成增广矩阵，所以可以用矩阵消元法求解"
        event = QAEvidenceInput(
            turn_id="uses", user_id="u", student_text=quote,
            previous_apprenticeship_level="fading",
            kg_candidates=[matrix.name, method.name],
            kg_candidate_nodes=[matrix, method],
            kg_candidate_relations=[KGStageRelation(
                matrix.node_id, matrix.name, "USES", method.node_id, method.name
            )],
            behavior_hints=["proof"],
        )
        value = {"observations": [
            {
                "concept_id": matrix.node_id, "concept_name": matrix.name,
                "observed_stage": 4, "direction": "positive", "strength": "certain",
                "behavior": "explanation", "student_quote": quote,
                **ACCEPTED_DIALOGUE_DECISION,
            },
            {
                "concept_id": method.node_id, "concept_name": method.name,
                "observed_stage": 4, "direction": "positive", "strength": "certain",
                "behavior": "explanation", "student_quote": quote,
                **ACCEPTED_DIALOGUE_DECISION,
            },
        ]}
        result = _validate_qa_stage(value, event)["observations"]
        self.assertTrue(all(item["projection_role"] == "primary" for item in result))

    def test_exercise_has_separate_stage_caps(self):
        hinted = ExerciseEvidenceInput(
            attempt_id="a1", exercise_id="e1", user_id="u1", question="证明",
            student_answer="设系数后，因为等式成立，所以所有系数为零。",
            correct_answer="略", is_correct=True, target_concept="线性无关",
            target_stage=4, hint_level=1,
        )
        value = {"observations": [{
            "concept_name": "线性无关", "observed_stage": 4,
            "direction": "positive", "strength": "certain", "behavior": "proof",
            "student_quote": "因为等式成立，所以所有系数为零",
        }]}
        with self.assertRaises(ObservationValidationError):
            _validate_exercise_stage(value, hinted, ["线性无关"])

        final_only = ExerciseEvidenceInput(
            attempt_id="a2", exercise_id="e1", user_id="u1", question="计算",
            student_answer="42", correct_answer="42", is_correct=True,
            target_concept="计算", target_stage=3, hint_level=0,
        )
        final_value = {"observations": [{
            "concept_name": "计算", "observed_stage": 3,
            "direction": "positive", "strength": "certain", "behavior": "solution_attempt",
            "student_quote": "42",
        }]}
        with self.assertRaises(ObservationValidationError):
            _validate_exercise_stage(final_value, final_only, ["计算"])

    def test_dimension_semantic_gates_reject_over_attribution(self):
        qa = QAEvidenceInput(
            turn_id="q-dim", user_id="u", student_text="因为条件成立，所以结论成立。",
            previous_ai_answer="请完成这道标准证明题。",
            previous_apprenticeship_level="fading", behavior_hints=["proof"],
        )
        standard_radius = {"observations": [{
            "dimension": "lr", "facet": "radius", "status": "observed",
            "direction": "positive", "strength": "certain",
            "student_quote": "因为条件成立，所以结论成立",
        }]}
        with self.assertRaises(ObservationValidationError):
            validate_qa_dimensions(standard_radius, qa)

        fake_abstraction = {"observations": [{
            "dimension": "mt", "facet": "technical", "status": "observed",
            "direction": "positive", "strength": "certain",
            "student_quote": "因为条件成立，所以结论成立",
        }]}
        with self.assertRaises(ObservationValidationError):
            validate_qa_dimensions(fake_abstraction, qa)

        exercise = ExerciseEvidenceInput(
            attempt_id="a-dim", exercise_id="e", user_id="u", question="求解方程。",
            student_answer="所以 x=2。", correct_answer="x=2", is_correct=True,
            target_stage=3, hint_level=0, difficulty="normal",
        )
        final_answer_ps = {"observations": [{
            "dimension": "ps", "facet": "coverage", "status": "observed",
            "direction": "positive", "strength": "certain", "student_quote": "所以 x=2",
        }]}
        with self.assertRaises(ObservationValidationError):
            validate_exercise_dimensions(final_answer_ps, exercise)

    def test_support_caps_dimension_strength(self):
        qa = QAEvidenceInput(
            turn_id="q-support", user_id="u", student_text="因为条件成立，所以结论成立。",
            previous_ai_answer="使用这个定理。", previous_apprenticeship_level="coaching",
            behavior_hints=["proof"],
        )
        value = {"observations": [{
            "dimension": "lr", "facet": "coverage", "status": "observed",
            "direction": "positive", "strength": "certain",
            "student_quote": "因为条件成立，所以结论成立",
        }]}
        with self.assertRaises(ObservationValidationError):
            validate_qa_dimensions(value, qa)

        exercise = ExerciseEvidenceInput(
            attempt_id="a-support", exercise_id="e", user_id="u", question="计算。",
            student_answer="设 x=1，所以 x+1=2。", correct_answer="2", is_correct=True,
            target_stage=3, hint_level=1, difficulty="normal",
        )
        exercise_value = {"observations": [{
            "dimension": "so", "facet": "technical", "status": "observed",
            "direction": "positive", "strength": "certain", "student_quote": "x+1=2",
        }]}
        with self.assertRaises(ObservationValidationError):
            validate_exercise_dimensions(exercise_value, exercise)

    def test_real_transfer_evidence_can_support_radius(self):
        text = "一般地，对于任意n维向量组，同样可以把线性组合写成矩阵方程。"
        event = QAEvidenceInput(
            turn_id="q-transfer", user_id="u", student_text=text,
            previous_ai_answer="请把结论推广到任意维数。",
            previous_apprenticeship_level="fading", behavior_hints=["transfer"],
        )
        value = {"observations": [{
            "dimension": "mt", "facet": "radius", "status": "observed",
            "direction": "positive", "strength": "certain", "student_quote": text,
        }]}
        result = validate_qa_dimensions(value, event)
        self.assertEqual(len(result["observations"]), 1)

    def test_probable_votes_have_half_weight(self):
        from app.services.diagnosis.projectors import _aggregate_dimensions

        three_probable = [
            {"dimension": "lr", "facet": "technical", "direction": "positive", "strength": "probable"}
            for _ in range(3)
        ]
        self.assertEqual(
            _aggregate_dimensions(three_probable)["changes"]["lr"]["technical"], 0
        )
        four_probable = three_probable + [three_probable[0].copy()]
        self.assertEqual(
            _aggregate_dimensions(four_probable)["changes"]["lr"]["technical"], 1
        )


class ProjectionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = config.DB_PATH
        self.old_mode = config.DIAGNOSIS_V2_MODE
        config.DB_PATH = os.path.join(self.temp_dir.name, "diagnosis-v2.db")
        from app.db.connection import init_db

        init_db()

    def tearDown(self):
        config.DB_PATH = self.old_db
        config.DIAGNOSIS_V2_MODE = self.old_mode
        self.temp_dir.cleanup()

    def _insert_stage_evidence(
        self,
        source_id: str,
        direction: str,
        stage: int = 2,
        projection_role: str = "primary",
    ) -> dict:
        from app.db.connection import get_conn

        evidence_id = str(uuid.uuid4())
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO diagnostic_evidence (
                id, run_id, source_type, source_id, user_id, sequence_id,
                observation_type, concept_name, observed_stage, direction, strength,
                student_quote, behavior, scorer_version, payload
            ) VALUES (?, ?, 'qa_turn', ?, 'u1', 'S1', 'stage', '概念A', ?, ?,
                      'certain', '学生原话', 'proof', 'v2', ?)
            """,
            (
                evidence_id, "run-" + source_id, source_id, stage, direction,
                json.dumps({"projection_role": projection_role}),
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM diagnostic_evidence WHERE id=?", (evidence_id,)).fetchone()
        conn.close()
        return dict(row)

    def test_stage_projection_is_idempotent_and_demotion_requires_two_events(self):
        from app.db.connection import get_conn
        from app.services.diagnosis.projectors import project_stage_evidence

        config.DIAGNOSIS_V2_MODE = "stage_only"
        positive = self._insert_stage_evidence("p1", "positive", 4)
        self.assertTrue(project_stage_evidence(positive))
        self.assertFalse(project_stage_evidence(positive))

        first_negative = self._insert_stage_evidence("n1", "negative", 2)
        self.assertTrue(project_stage_evidence(first_negative))
        conn = get_conn()
        row = conn.execute(
            "SELECT stage, confidence FROM knowledge_stages WHERE user_id='u1' AND concept_name='概念A'"
        ).fetchone()
        self.assertEqual(row["stage"], 4)
        self.assertAlmostEqual(row["confidence"], 0.45)
        conn.close()

        second_negative = self._insert_stage_evidence("n2", "negative", 2)
        self.assertTrue(project_stage_evidence(second_negative))
        conn = get_conn()
        row = conn.execute(
            "SELECT stage, confidence FROM knowledge_stages WHERE user_id='u1' AND concept_name='概念A'"
        ).fetchone()
        self.assertEqual(row["stage"], 3)
        self.assertAlmostEqual(row["confidence"], 0.5)
        conn.close()

        third_negative = self._insert_stage_evidence("n3", "negative", 1)
        fourth_negative = self._insert_stage_evidence("n4", "negative", 1)
        self.assertTrue(project_stage_evidence(third_negative))
        conn = get_conn()
        self.assertEqual(conn.execute(
            "SELECT stage FROM knowledge_stages WHERE user_id='u1' AND concept_name='概念A'"
        ).fetchone()["stage"], 3)
        conn.close()
        self.assertTrue(project_stage_evidence(fourth_negative))
        conn = get_conn()
        self.assertEqual(conn.execute(
            "SELECT stage FROM knowledge_stages WHERE user_id='u1' AND concept_name='概念A'"
        ).fetchone()["stage"], 2)
        conn.close()

    def test_supporting_stage_evidence_is_logged_but_not_projected_or_counted(self):
        from app.db.connection import get_conn
        from app.services.diagnosis.projectors import project_stage_evidence

        config.DIAGNOSIS_V2_MODE = "stage_only"
        positive = self._insert_stage_evidence("support-base", "positive", 4)
        self.assertTrue(project_stage_evidence(positive))

        supporting = self._insert_stage_evidence(
            "supporting-negative", "negative", 2, projection_role="supporting"
        )
        self.assertTrue(project_stage_evidence(supporting))
        self.assertFalse(project_stage_evidence(supporting))
        conn = get_conn()
        stage = conn.execute(
            "SELECT stage, confidence FROM knowledge_stages WHERE user_id='u1' AND concept_name='概念A'"
        ).fetchone()
        action = conn.execute(
            "SELECT json_extract(after_value, '$.action') FROM state_projection_log WHERE evidence_id=?",
            (supporting["id"],),
        ).fetchone()[0]
        self.assertEqual((stage["stage"], stage["confidence"]), (4, 0.6))
        self.assertEqual(action, "suppressed")
        conn.close()

        first_primary = self._insert_stage_evidence("primary-negative-1", "negative", 2)
        self.assertTrue(project_stage_evidence(first_primary))
        conn = get_conn()
        stage = conn.execute(
            "SELECT stage, confidence FROM knowledge_stages WHERE user_id='u1' AND concept_name='概念A'"
        ).fetchone()
        self.assertEqual(stage["stage"], 4)
        self.assertAlmostEqual(stage["confidence"], 0.45)
        conn.close()

        second_primary = self._insert_stage_evidence("primary-negative-2", "negative", 2)
        self.assertTrue(project_stage_evidence(second_primary))
        conn = get_conn()
        stage = conn.execute(
            "SELECT stage, confidence FROM knowledge_stages WHERE user_id='u1' AND concept_name='概念A'"
        ).fetchone()
        self.assertEqual(stage["stage"], 3)
        conn.close()

    def test_dimension_window_requires_five_distinct_events_and_closes_once(self):
        from app.db.connection import get_conn
        from app.services.diagnosis.projectors import close_ready_dimension_windows

        config.DIAGNOSIS_V2_MODE = "full"
        conn = get_conn()
        for index in range(4):
            conn.execute(
                """
                INSERT INTO diagnostic_evidence (
                    id, run_id, source_type, source_id, user_id, sequence_id,
                    observation_type, dimension, facet, direction, strength,
                    student_quote, scorer_version
                ) VALUES (?, ?, 'qa_turn', ?, 'u2', 'S2', 'dimension', 'lr',
                          'technical', 'positive', 'certain', ?, 'v2')
                """,
                (str(uuid.uuid4()), f"run-{index}", f"event-{index}", f"原话-{index}"),
            )
        conn.commit()
        conn.close()
        self.assertEqual(close_ready_dimension_windows(), 0)

        conn = get_conn()
        conn.execute(
            """
            INSERT INTO diagnostic_evidence (
                id, run_id, source_type, source_id, user_id, sequence_id,
                observation_type, dimension, facet, direction, strength,
                student_quote, scorer_version
            ) VALUES (?, 'run-4', 'exercise_attempt', 'event-4', 'u2', 'S2',
                      'dimension', 'lr', 'technical', 'positive', 'certain', '原话-4', 'v2')
            """,
            (str(uuid.uuid4()),),
        )
        conn.commit()
        conn.close()

        self.assertEqual(close_ready_dimension_windows(), 1)
        self.assertEqual(close_ready_dimension_windows(), 0)
        conn = get_conn()
        profile = conn.execute("SELECT lr_technical FROM math_profiles WHERE user_id='u2'").fetchone()
        windows = conn.execute("SELECT COUNT(*) FROM dimension_windows WHERE user_id='u2'").fetchone()[0]
        self.assertEqual(profile["lr_technical"], 1)
        self.assertEqual(windows, 1)
        conn.close()

    def test_incorrect_attempt_waits_for_error_analysis(self):
        from app.db.diagnosis_v2_db import (
            list_pending_sources,
            save_exercise_attempt,
            update_exercise_attempt_error,
        )

        attempt_id = save_exercise_attempt(
            exercise={
                "id": "exercise-1", "user_id": "u3", "sequence_id": "S3",
                "topic": "概念B", "target_stage": 3, "difficulty": "normal",
                "question": "题目", "answer": "答案", "hint_level": 0,
            },
            student_answer="错误步骤", is_correct=False,
            grading_feedback="错误", grader_version="test",
        )
        self.assertEqual(list_pending_sources(
            "exercise_attempt", "exercise_stage", "v2", user_id="u3"
        ), [])
        update_exercise_attempt_error(attempt_id, {"error_category": "logic_gap"})
        rows = list_pending_sources(
            "exercise_attempt", "exercise_stage", "v2", user_id="u3"
        )
        self.assertEqual([row["id"] for row in rows], [attempt_id])


if __name__ == "__main__":
    unittest.main()
