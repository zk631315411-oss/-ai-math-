"""Offline tests for the conversation probability shadow state."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from app.config import config


class DialogueStateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db = config.DB_PATH
        self.old_mode = config.DIALOGUE_STATE_MODE
        self.old_version = config.DIALOGUE_STATE_MODEL_VERSION
        config.DB_PATH = os.path.join(self.temp_dir.name, "dialogue-state.db")
        config.DIALOGUE_STATE_MODE = "shadow"
        config.DIALOGUE_STATE_MODEL_VERSION = "test-ordinal-v1"
        from app.db.connection import init_db

        init_db()

    def tearDown(self):
        config.DB_PATH = self.old_db
        config.DIALOGUE_STATE_MODE = self.old_mode
        config.DIALOGUE_STATE_MODEL_VERSION = self.old_version
        self.temp_dir.cleanup()

    def _insert_evidence(
        self,
        *,
        evidence_id: str,
        concept_id: str,
        concept_name: str,
        stage: int = 4,
        behavior: str = "explanation",
        strength: str = "certain",
        support: str = "fading",
        overlap: float = 0.0,
        direction: str = "positive",
        action: str = "accepted",
        reason: str = "independent_evidence",
        rationale: str = "学生独立展示了能力",
        include_decision: bool = True,
        projection_role: str = "primary",
        created_at: str = "2026-07-28T10:00:00",
    ) -> dict:
        from app.db.connection import get_conn

        row = {
            "id": evidence_id,
            "user_id": "u1",
            "concept_name": concept_name,
            "source_type": "qa_turn",
            "observation_type": "stage",
            "observed_stage": stage,
            "direction": direction,
            "strength": strength,
            "behavior": behavior,
            "support_level": support,
            "payload": {
                "concept_id": concept_id,
                "projection_role": projection_role,
                "assistant_overlap": overlap,
            },
        }
        if include_decision:
            row["payload"].update({
                "dialogue_state_action": action,
                "dialogue_state_reason": reason,
                "dialogue_state_rationale": rationale,
            })
        row["payload"] = json.dumps(row["payload"], ensure_ascii=False)
        conn = get_conn()
        conn.execute(
            """
            INSERT INTO diagnostic_evidence (
                id, run_id, source_type, source_id, user_id, sequence_id,
                observation_type, concept_name, observed_stage, direction,
                strength, student_quote, behavior, support_level, scorer_version,
                payload, created_at
            ) VALUES (?, ?, 'qa_turn', ?, ?, '', 'stage', ?, ?, ?, ?, ?, ?, ?, 'v2', ?, ?)
            """,
            (
                evidence_id,
                f"run-{evidence_id}",
                f"turn-{evidence_id}",
                row["user_id"],
                concept_name,
                stage,
                direction,
                strength,
                "学生原话",
                behavior,
                support,
                row["payload"],
                created_at,
            ),
        )
        conn.commit()
        conn.close()
        row["concept_id"] = concept_id
        return row

    def test_accepted_evidence_updates_once_and_stays_shadow_only(self):
        from app.db.connection import get_conn
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence, get_dialogue_state

        evidence = self._insert_evidence(
            evidence_id="accepted-1", concept_id="kg-a", concept_name="概念A"
        )
        self.assertTrue(project_dialogue_evidence(evidence))
        self.assertFalse(project_dialogue_evidence(evidence))

        state = get_dialogue_state("u1", "kg-a")
        self.assertIsNotNone(state)
        self.assertEqual(state["evidence_count"], 1)
        self.assertAlmostEqual(sum(state["probabilities"]), 1.0, places=8)

        conn = get_conn()
        self.assertIsNone(conn.execute(
            "SELECT 1 FROM knowledge_stages WHERE user_id='u1' AND concept_name='概念A'"
        ).fetchone())
        conn.close()

    def test_model_semantic_abstention_wins_even_with_low_overlap(self):
        from app.db.connection import get_conn
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence

        evidence = self._insert_evidence(
            evidence_id="question-1", concept_id="kg-b", concept_name="概念B",
            behavior="explanation", strength="probable", overlap=0.01,
            action="abstained", reason="ai_dependent",
            rationale="虽然措辞不同，但复述了上一轮 AI 的关键解释",
        )
        self.assertTrue(project_dialogue_evidence(evidence))

        conn = get_conn()
        self.assertIsNone(conn.execute(
            "SELECT 1 FROM dialogue_knowledge_states WHERE user_id='u1' AND concept_id='kg-b'"
        ).fetchone())
        action = conn.execute(
            "SELECT action FROM dialogue_state_projection_log WHERE evidence_id='question-1'"
        ).fetchone()[0]
        self.assertEqual(action, "abstained:ai_dependent")
        conn.close()

    def test_model_acceptance_wins_even_with_high_overlap(self):
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence, get_dialogue_state

        evidence = self._insert_evidence(
            evidence_id="copy-1", concept_id="kg-c", concept_name="概念C", overlap=0.95
        )
        self.assertTrue(project_dialogue_evidence(evidence))
        self.assertEqual(get_dialogue_state("u1", "kg-c")["evidence_count"], 1)

    def test_legacy_missing_decision_is_audit_only(self):
        from app.db.connection import get_conn
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence

        evidence = self._insert_evidence(
            evidence_id="legacy-1", concept_id="kg-legacy", concept_name="旧证据",
            include_decision=False,
        )
        self.assertTrue(project_dialogue_evidence(evidence))
        conn = get_conn()
        action = conn.execute(
            "SELECT action FROM dialogue_state_projection_log WHERE evidence_id='legacy-1'"
        ).fetchone()[0]
        self.assertEqual(action, "abstained:legacy_missing_decision")
        self.assertIsNone(conn.execute(
            "SELECT 1 FROM dialogue_knowledge_states WHERE concept_id='kg-legacy'"
        ).fetchone())
        conn.close()

    def test_supporting_evidence_is_forced_to_abstain(self):
        from app.db.connection import get_conn
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence

        evidence = self._insert_evidence(
            evidence_id="supporting-1", concept_id="kg-support", concept_name="父概念",
            projection_role="supporting",
        )
        self.assertTrue(project_dialogue_evidence(evidence))
        conn = get_conn()
        action = conn.execute(
            "SELECT action FROM dialogue_state_projection_log WHERE evidence_id='supporting-1'"
        ).fetchone()[0]
        self.assertEqual(action, "abstained:supporting_evidence")
        conn.close()

    def test_replay_is_deterministic(self):
        from app.services.diagnosis.dialogue_state import replay_dialogue_states, get_dialogue_state

        self._insert_evidence(
            evidence_id="replay-1", concept_id="kg-d", concept_name="概念D",
            created_at="2026-07-28T10:00:00",
        )
        self._insert_evidence(
            evidence_id="replay-2", concept_id="kg-d", concept_name="概念D",
            stage=5, created_at="2026-07-28T10:01:00",
        )
        self.assertEqual(replay_dialogue_states("u1"), 2)
        first = get_dialogue_state("u1", "kg-d")
        self.assertEqual(replay_dialogue_states("u1"), 2)
        second = get_dialogue_state("u1", "kg-d")
        self.assertEqual(first["probabilities"], second["probabilities"])
        self.assertEqual(first["evidence_count"], second["evidence_count"])

    def test_stronger_assistance_produces_smaller_update(self):
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence, get_dialogue_state

        independent = self._insert_evidence(
            evidence_id="independent-1", concept_id="kg-e", concept_name="概念E",
            strength="probable", support="fading",
        )
        assisted = self._insert_evidence(
            evidence_id="assisted-1", concept_id="kg-f", concept_name="概念F",
            strength="probable", support="modeling",
        )
        project_dialogue_evidence(independent)
        project_dialogue_evidence(assisted)
        independent_state = get_dialogue_state("u1", "kg-e")
        assisted_state = get_dialogue_state("u1", "kg-f")
        self.assertGreater(
            independent_state["expected_stage"] - 2.5,
            assisted_state["expected_stage"] - 2.5,
        )

    def test_unknown_assistance_uses_reduced_weight_but_still_updates(self):
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence, get_dialogue_state

        fading = self._insert_evidence(
            evidence_id="fading-1", concept_id="kg-known", concept_name="已知帮助",
            strength="certain", support="fading",
        )
        unknown = self._insert_evidence(
            evidence_id="unknown-1", concept_id="kg-unknown", concept_name="未知帮助",
            strength="certain", support="unknown",
        )
        project_dialogue_evidence(fading)
        project_dialogue_evidence(unknown)
        fading_state = get_dialogue_state("u1", "kg-known")
        unknown_state = get_dialogue_state("u1", "kg-unknown")
        self.assertIsNotNone(unknown_state)
        self.assertGreater(
            fading_state["expected_stage"] - 2.5,
            unknown_state["expected_stage"] - 2.5,
        )

    def test_negative_evidence_reduces_expected_stage(self):
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence, get_dialogue_state

        positive = self._insert_evidence(
            evidence_id="positive-1", concept_id="kg-g", concept_name="概念G", stage=4
        )
        negative = self._insert_evidence(
            evidence_id="negative-1", concept_id="kg-g", concept_name="概念G",
            stage=2, direction="negative", created_at="2026-07-28T10:01:00",
        )
        project_dialogue_evidence(positive)
        before = get_dialogue_state("u1", "kg-g")["expected_stage"]
        project_dialogue_evidence(negative)
        after = get_dialogue_state("u1", "kg-g")["expected_stage"]
        self.assertLess(after, before)

    def test_off_mode_performs_no_writes(self):
        from app.db.connection import get_conn
        from app.services.diagnosis.dialogue_state import project_dialogue_evidence

        evidence = self._insert_evidence(
            evidence_id="off-1", concept_id="kg-h", concept_name="概念H"
        )
        config.DIALOGUE_STATE_MODE = "off"
        self.assertFalse(project_dialogue_evidence(evidence))
        conn = get_conn()
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM dialogue_state_projection_log"
        ).fetchone()[0], 0)
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM dialogue_knowledge_states"
        ).fetchone()[0], 0)
        conn.close()

    def test_worker_drains_dialogue_backlog_without_pending_scorers(self):
        import asyncio
        from app.services.diagnostic_worker import run_diagnostic_batch
        from app.services.diagnosis.dialogue_state import get_dialogue_state

        self._insert_evidence(
            evidence_id="worker-1", concept_id="kg-worker", concept_name="积压概念"
        )
        self.assertTrue(asyncio.run(run_diagnostic_batch("u1")))
        self.assertEqual(get_dialogue_state("u1", "kg-worker")["evidence_count"], 1)
        self.assertFalse(asyncio.run(run_diagnostic_batch("u1")))

    def test_worker_limits_each_cycle_to_ten_batches_of_one_hundred(self):
        from app.services import diagnostic_worker

        with patch.object(
            diagnostic_worker, "project_pending_dialogue_states", return_value=100
        ) as project:
            self.assertEqual(diagnostic_worker._drain_dialogue_state_backlog(), 1000)

        self.assertEqual(project.call_count, 10)
        project.assert_called_with(100, user_id=None)

    def test_pending_projection_uses_created_at_then_id_order(self):
        from app.services.diagnosis.dialogue_state import (
            get_dialogue_state,
            project_pending_dialogue_states,
        )

        self._insert_evidence(
            evidence_id="order-b", concept_id="kg-order", concept_name="顺序概念",
            stage=5,
        )
        self._insert_evidence(
            evidence_id="order-a", concept_id="kg-order", concept_name="顺序概念",
            stage=3,
        )
        self.assertEqual(project_pending_dialogue_states(), 2)
        self.assertEqual(get_dialogue_state("u1", "kg-order")["last_evidence_id"], "order-b")

    def test_replay_failure_rolls_back_original_user_state(self):
        from app.db.connection import get_conn
        from app.services.diagnosis import dialogue_state

        first = self._insert_evidence(
            evidence_id="rollback-1", concept_id="kg-rollback", concept_name="回滚概念"
        )
        dialogue_state.project_dialogue_evidence(first)
        before = dialogue_state.get_dialogue_state("u1", "kg-rollback")
        self._insert_evidence(
            evidence_id="rollback-2", concept_id="kg-rollback", concept_name="回滚概念",
            stage=5, created_at="2026-07-28T10:01:00",
        )

        original = dialogue_state._project_dialogue_evidence
        calls = 0

        def fail_second(conn, evidence, version):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("injected replay failure")
            return original(conn, evidence, version)

        with patch.object(dialogue_state, "_project_dialogue_evidence", side_effect=fail_second):
            with self.assertRaises(RuntimeError):
                dialogue_state.replay_dialogue_states("u1")

        after = dialogue_state.get_dialogue_state("u1", "kg-rollback")
        self.assertEqual(after["probabilities"], before["probabilities"])
        self.assertEqual(after["evidence_count"], before["evidence_count"])
        conn = get_conn()
        self.assertEqual(conn.execute(
            "SELECT COUNT(*) FROM dialogue_state_projection_log WHERE user_id='u1'"
        ).fetchone()[0], 1)
        conn.close()


class LLMAsyncRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_diagnosis_scorer_uses_profile_model(self):
        from app.services.diagnosis.scorers import _call_and_validate
        from app.services.llm_service import llm_service

        with patch.object(
            llm_service, "chat_async", new=AsyncMock(return_value='{"observations": []}')
        ) as mocked:
            result, _ = await _call_and_validate("test", lambda value: value)

        self.assertEqual(result, {"observations": []})
        self.assertEqual(mocked.await_args.kwargs["model"], config.PROFILE_LLM_MODEL)
        self.assertNotIn("use_profile", mocked.await_args.kwargs)


if __name__ == "__main__":
    unittest.main()
