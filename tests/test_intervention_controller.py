from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from app.config import config
from app.db.connection import get_conn, init_db
from app.db.diagnosis_v2_db import save_signals
from app.services.diagnosis.contracts import DiagnosticSignal
from app.services.intervention import repository as repo
from app.services.intervention.service import intervention_service
from app.services.intervention.state import load_student_state, publish_snapshot


class InterventionControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db = config.DB_PATH
        self.original_mode = config.TEACHING_CONTROLLER_MODE
        config.DB_PATH = f"{self.temp_dir.name}/controller.db"
        config.TEACHING_CONTROLLER_MODE = "active"
        init_db()
        self._insert_turn("turn-1", "I confuse rank with the number of rows.")

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db
        config.TEACHING_CONTROLLER_MODE = self.original_mode
        self.temp_dir.cleanup()

    def _insert_turn(self, turn_id: str, question: str, node_id: str = "node-1") -> None:
        context = {
            "input_context": {"tree_id": "tree-1", "node_id": node_id},
            "grounding": {
                "related_concepts": [{"node_id": "rank", "name": "matrix rank"}],
                "prerequisite_concepts": [{"node_id": "row-operation", "name": "row operation"}],
            },
            "history": [],
        }
        conn = get_conn()
        try:
            conn.execute(
                """INSERT INTO qa_turn_records
                   (id,user_id,input_type,question,answer,textbook_id,sequence_id,context_snapshot,error)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (turn_id, "student-1", "text", question, "answer", "gaodai_shang", "V1-C01-S01",
                 __import__("json").dumps(context), ""),
            )
            conn.commit()
        finally:
            conn.close()

    def _signal(self, *, signal_type: str = "concept_confusion", confidence: float = 0.9,
                strength: str = "certain") -> DiagnosticSignal:
        return DiagnosticSignal(
            source_type="qa_turn", source_id="turn-1", user_id="student-1",
            sequence_id="V1-C01-S01", signal_type=signal_type,
            concept_ids=["rank"], student_quote="confuse rank",
            confidence=confidence, strength=strength,
            rationale="Distinguish invariant rank from a matrix representation.",
        )

    def test_high_confidence_signal_can_prepare_practice(self) -> None:
        save_signals([self._signal()])
        snapshot = publish_snapshot("qa_turn", "turn-1")
        with (
            patch("app.services.intervention.service.llm_service", create=True),
            patch(
                "app.services.practice.service.practice_service.create_from_intervention",
                return_value={"id": "draft-1", "status": "queued"},
            ),
        ):
            # The planner's deterministic branch is used because no QA client is configured.
            result = intervention_service.plan_snapshot(snapshot)
        self.assertEqual(result["directive"]["action"], "prepare_practice")
        actions = repo.list_actions_for_turn("student-1", "turn-1")
        self.assertEqual(actions[-1]["trigger_kind"], "agent_recommended")
        self.assertEqual(actions[-1]["draft_id"], "draft-1")

    def test_auto_preference_blocks_automatic_practice(self) -> None:
        repo.update_preferences("student-1", {"auto_prepare_practice": False})
        save_signals([self._signal()])
        snapshot = publish_snapshot("qa_turn", "turn-1")
        result = intervention_service.plan_snapshot(snapshot)
        self.assertEqual(result["directive"]["action"], "adjust_qa")
        self.assertEqual(repo.list_actions_for_turn("student-1", "turn-1"), [])

    def test_text_practice_request_only_offers_entry(self) -> None:
        save_signals([self._signal(signal_type="practice_request", confidence=0.7, strength="probable")])
        snapshot = publish_snapshot("qa_turn", "turn-1")
        result = intervention_service.plan_snapshot(snapshot)
        self.assertEqual(result["directive"]["action"], "offer_practice_entry")
        action = repo.list_actions_for_turn("student-1", "turn-1")[-1]
        self.assertEqual(action["status"], "ready")
        self.assertIsNone(action["draft_id"])

    def test_directive_is_single_use_and_branch_scoped(self) -> None:
        save_signals([self._signal(confidence=0.7, strength="probable")])
        snapshot = publish_snapshot("qa_turn", "turn-1")
        directive = intervention_service.plan_snapshot(snapshot)["directive"]
        active = repo.get_active_directive(
            "student-1", tree_id="tree-1", node_id="node-1",
            sequence_id="V1-C01-S01", concept_ids=["rank"],
        )
        self.assertEqual(active["id"], directive["id"])
        intervention_service.mark_applied(directive["id"], "turn-2")
        self.assertIsNone(repo.get_active_directive(
            "student-1", tree_id="tree-1", node_id="node-1",
            sequence_id="V1-C01-S01", concept_ids=["rank"],
        ))

        second = repo.create_directive(
            snapshot=snapshot, action="adjust_qa", teaching_goal="test", qa_policy={},
            evidence_refs=[], confidence=0.7, model_name="test", prompt_version="test",
            status="active",
        )
        self.assertIsNone(repo.get_active_directive(
            "student-1", tree_id="tree-1", node_id="node-2",
            sequence_id="V1-C01-S01", concept_ids=["rank"],
        ))
        self.assertEqual(repo.get_directive(second["id"])["status"], "stale")

    def test_no_action_turn_becomes_terminal_when_planning_finishes(self) -> None:
        snapshot = publish_snapshot("qa_turn", "turn-1")
        job_id = repo.get_job_id_for_snapshot(snapshot["id"])
        claimed = repo.claim_job(job_id, "worker-1")
        self.assertIsNotNone(claimed)
        repo.finish_job(job_id, "worker-1", status="ready", result={"action": "no_action"})

        result = intervention_service.get_turn_result(user_id="student-1", turn_id="turn-1")

        self.assertTrue(result["terminal"])
        self.assertEqual(result["actions"], [])

    def test_explicit_button_creates_audited_linked_draft(self) -> None:
        with patch("app.services.practice.service.practice_worker.enqueue"):
            draft = intervention_service.request_explicit_practice(
                user_id="student-1", turn_id="turn-1", node_id="node-1",
            )
        actions = repo.list_actions_for_turn("student-1", "turn-1")
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["trigger_kind"], "explicit_button")
        self.assertEqual(actions[0]["draft_id"], draft["id"])
        conn = get_conn()
        try:
            row = conn.execute(
                "SELECT intervention_action_id FROM practice_drafts WHERE id=?", (draft["id"],)
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["intervention_action_id"], actions[0]["id"])

    def test_preferences_are_isolated_by_user(self) -> None:
        intervention_service.update_preferences(
            "student-1", auto_prepare_practice=False,
        )
        self.assertFalse(intervention_service.get_preferences("student-1")["auto_prepare_practice"])
        self.assertTrue(intervention_service.get_preferences("student-2")["auto_prepare_practice"])

    def test_expired_worker_lease_is_recoverable(self) -> None:
        snapshot = publish_snapshot("qa_turn", "turn-1")
        job_id = repo.get_job_id_for_snapshot(snapshot["id"])
        self.assertIsNotNone(repo.claim_job(job_id, "worker-a"))
        conn = get_conn()
        try:
            conn.execute(
                "UPDATE intervention_agent_jobs SET lease_until=datetime('now','-1 minute') WHERE id=?",
                (job_id,),
            )
            conn.commit()
        finally:
            conn.close()

        self.assertIn(job_id, repo.list_recoverable_job_ids())
        recovered = repo.claim_job(job_id, "worker-b")
        self.assertEqual(recovered["worker_id"], "worker-b")

    def test_student_state_reads_projected_stage(self) -> None:
        conn = get_conn()
        try:
            conn.execute(
                "INSERT INTO knowledge_stages(id,user_id,concept_name,stage,confidence) VALUES (?,?,?,?,?)",
                ("stage-1", "student-1", "rank", 2, 0.8),
            )
            conn.commit()
        finally:
            conn.close()
        state = load_student_state(
            "student-1", tree_id="tree-1", node_id="node-1",
            sequence_id="V1-C01-S01", concept_ids=["rank"],
        )
        self.assertEqual(state.current_section_stage, 2)
        self.assertEqual(state.related_concept_stages["rank"], 2)


if __name__ == "__main__":
    unittest.main()
