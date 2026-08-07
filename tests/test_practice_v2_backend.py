from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from app.config import config
from app.db.connection import get_conn, init_db
from app.services.practice import repository as repo
from app.services.practice.agents import build_draft
from app.services.practice.service import practice_service
from app.services.sympy_sandbox import verify_computable


def _context(turn_id: str = "turn-1") -> dict:
    return {
        "turn_id": turn_id,
        "tree_id": "tree-1",
        "node_id": "node-1",
        "textbook_id": "gaodai_shang",
        "sequence_id": "V1-C01-S01",
        "concept_ids": ["rank"],
        "concept_names": ["matrix rank"],
        "prerequisite_concept_ids": ["row-operations"],
        "prerequisite_concept_names": ["row operations"],
        "kg_neighbor_ids": ["rank-system"],
        "question": "I do not understand matrix rank. Give me practice.",
        "student_stage": 2,
        "evidence_quote": "do not understand matrix rank",
        "intervention_goal": "remediate the current gap and verify independent work",
    }


def _add_item(item_id: str, concept_id: str, stage: int = 2, *, question_type: str = "concept") -> str:
    repo.add_item({
        "id": item_id,
        "textbook_id": "gaodai_shang",
        "source_locator": f"p.10 {item_id}",
        "sequence_id": "V1-C01-S01",
        "concept_ids": [concept_id],
        "concept_names": [concept_id],
        "primary_concept_id": concept_id,
        "primary_concept_name": concept_id,
        "prerequisite_concept_ids": ["row-operations"] if concept_id == "rank" else [],
        "question_type": question_type,
        "diagnostic_goal": "definition" if stage <= 2 else "application",
        "difficulty": "basic",
        "question": f"Question for {concept_id}: {item_id}",
        "answer_spec": {"reference": f"answer for {item_id}"},
        "hints": ["hint 1", "hint 2", "hint 3"],
        "source": "textbook",
        "trust_status": "teacher_approved",
        "solution_review_status": "reviewed",
        "kg_mapping_status": "verified",
        "review_status": "approved",
    })
    return item_id


def _decision(item_id: str, concept_id: str, *, use: str = "diagnostic",
              action: str = "continue", reason: str = "bounded selection") -> str:
    return json.dumps({
        "item_id": item_id,
        "purpose": use,
        "target_concept": concept_id,
        "evidence_refs": ["do not understand matrix rank"],
        "reason": reason,
        "recommend_end": action == "end",
        "action": action,
    })


def _grade(verdict: str) -> dict:
    return {
        "verdict": verdict,
        "evidence_quotes": ["student answer"],
        "rubric_findings": [],
        "feedback": verdict,
        "error_analysis": {},
    }


class SympyQualityGateTests(unittest.TestCase):
    def test_inverse_and_system_answers_are_compared(self) -> None:
        inverse = verify_computable(
            "matrix_inverse", {"matrix": [[1, 0], [0, 2]]}, [[1, 0], [0, 0.5]],
        )
        self.assertTrue(inverse["success"], inverse)
        wrong = verify_computable(
            "matrix_inverse", {"matrix": [[1, 0], [0, 2]]}, [[1, 0], [0, 2]],
        )
        self.assertFalse(wrong["success"], wrong)
        system = verify_computable(
            "system_solve", {"matrix": [[2, 0], [0, 4]], "vector": [[2], [8]]}, [[1], [2]],
        )
        self.assertTrue(system["success"], system)


class PracticeV2BackendTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = f"{self.temp_dir.name}/practice-v2.db"
        init_db()

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def _create_draft(self, user_id: str = "student-a", turn_id: str = "turn-1") -> dict:
        context = _context(turn_id)
        return repo.create_draft(
            user_id=user_id, context=context, trigger_kind="explicit_request",
            intervention_goal=context["intervention_goal"],
            evidence_quote=context["evidence_quote"], auto_prepared=False,
        )

    def _ready_draft(self, user_id: str = "student-a") -> dict:
        draft = self._create_draft(user_id=user_id)
        fixtures = [
            (f"{user_id}-rank-1", "rank", 2),
            (f"{user_id}-rank-2", "rank", 3),
            (f"{user_id}-prereq", "row-operations", 2),
            (f"{user_id}-successor", "rank-system", 3),
        ]
        for rank, (item_id, concept_id, stage) in enumerate(fixtures):
            _add_item(item_id, concept_id, stage)
            repo.attach_draft_item(draft["id"], item_id, "diagnostic", rank, "candidate")
        repo.update_draft(draft["id"], status="ready", selection_reason="fixture")
        return repo.get_draft(draft["id"], user_id)

    def _start(self, draft: dict, *, item_suffix: str = "rank-1", use: str = "diagnostic") -> dict:
        item_id = f"{draft['user_id']}-{item_suffix}"
        concept = "rank" if "rank-" in item_suffix else "row-operations"
        with (
            patch("app.services.practice.service.llm_service.qa_async", object()),
            patch("app.services.practice.service.llm_service.chat_qa_async",
                  new=AsyncMock(return_value=_decision(item_id, concept, use=use))),
        ):
            return practice_service.start_session(draft["id"], draft["user_id"])

    def test_draft_creation_is_idempotent_and_regeneration_versions_once(self) -> None:
        original = self._create_draft()
        duplicate = self._create_draft()
        self.assertEqual(duplicate["id"], original["id"])
        with patch("app.services.practice.service.practice_worker.enqueue") as enqueue:
            replacement = practice_service.regenerate(original["id"], "student-a")
            repeated = practice_service.regenerate(original["id"], "student-a")
        self.assertNotEqual(replacement["id"], original["id"])
        self.assertEqual(repeated["id"], replacement["id"])
        self.assertEqual(replacement["version"], 2)
        enqueue.assert_called()

    def test_first_item_requires_valid_structured_model_decision(self) -> None:
        draft = self._ready_draft()
        invalid_id = _decision("outside-candidate-set", "rank")
        invalid_target = _decision("student-a-rank-1", "outside-concept")
        valid = _decision("student-a-rank-1", "rank")
        selector = AsyncMock(side_effect=[invalid_id, invalid_target, valid])
        with (
            patch("app.services.practice.service.llm_service.qa_async", object()),
            patch("app.services.practice.service.llm_service.chat_qa_async", new=selector),
        ):
            started = practice_service.start_session(draft["id"], "student-a")
        self.assertEqual(selector.await_count, 3)
        self.assertEqual(started["item"]["id"], "student-a-rank-1")
        self.assertEqual(started["selection_decision"]["purpose"], "diagnostic")
        self.assertEqual(started["session"]["status"], "active")

    def test_three_selection_failures_use_bounded_fallback(self) -> None:
        draft = self._ready_draft()
        selector = AsyncMock(return_value=_decision("student-a-successor", "rank-system"))
        with (
            patch("app.services.practice.service.llm_service.qa_async", object()),
            patch("app.services.practice.service.llm_service.chat_qa_async", new=selector),
        ):
            started = practice_service.start_session(draft["id"], "student-a")
        self.assertEqual(selector.await_count, 3)
        self.assertEqual(started["item"]["id"], "student-a-rank-2")
        self.assertEqual(started["item"]["diagnostic_goal"], "application")
        self.assertEqual(started["session"]["status"], "active")
        self.assertTrue(started["selection_decision"]["fallback"])

    def test_model_unavailable_uses_deterministic_item_fallback(self) -> None:
        draft = self._ready_draft()
        with patch("app.services.practice.service.llm_service.qa_async", None):
            started = practice_service.start_session(draft["id"], "student-a")
        self.assertEqual(started["item"]["id"], "student-a-rank-2")
        self.assertEqual(started["item"]["diagnostic_goal"], "application")
        self.assertTrue(started["selection_decision"]["fallback"])

    def test_prerequisite_is_open_but_successor_requires_independent_correct(self) -> None:
        draft = self._ready_draft()
        before = practice_service._candidate_items(draft, None, allow_successors=False)
        after = practice_service._candidate_items(draft, None, allow_successors=True)
        self.assertEqual({item["primary_concept_id"] for item in before}, {"rank", "row-operations"})
        self.assertEqual(
            {item["primary_concept_id"] for item in after},
            {"rank", "row-operations", "rank-system"},
        )

    def test_drafts_sessions_and_hints_are_user_isolated(self) -> None:
        draft = self._ready_draft()
        self.assertIsNone(practice_service.get_draft(draft["id"], "student-b"))
        with self.assertRaisesRegex(ValueError, "not ready"):
            practice_service.start_session(draft["id"], "student-b")
        started = self._start(draft)
        session_id = started["session"]["id"]
        self.assertIsNone(repo.get_session(session_id, "student-b"))
        with self.assertRaisesRegex(ValueError, "no active"):
            practice_service.request_hint(session_id, "student-b")
        owner_hint = practice_service.request_hint(session_id, "student-a")
        self.assertEqual(owner_hint["hint_level"], 1)
        self.assertEqual(repo.get_hint_level(session_id, started["item"]["id"], "student-b"), 0)

    def test_rolling_selector_failure_uses_rule_fallback(self) -> None:
        draft = self._ready_draft()
        started = self._start(draft)
        selector = AsyncMock(return_value="{}")
        with (
            patch.object(practice_service, "_grade", new=AsyncMock(return_value=_grade("incorrect"))),
            patch("app.services.practice.service.llm_service.qa_async", object()),
            patch("app.services.practice.service.llm_service.chat_qa_async", new=selector),
        ):
            result = asyncio.run(practice_service.submit_attempt(
                started["session"]["id"], "student-a", started["item"]["id"], "student answer",
            ))
        self.assertEqual(selector.await_count, 3)
        self.assertEqual(result["session_status"], "active")
        self.assertIsNotNone(result["next_item"])
        self.assertTrue(result["selection_decision"]["fallback"])

    def test_only_independent_correct_on_planned_validation_verifies_mastery(self) -> None:
        draft = self._ready_draft()
        started = self._start(draft, use="validation")
        with patch.object(practice_service, "_grade", new=AsyncMock(return_value=_grade("correct"))):
            result = asyncio.run(practice_service.submit_attempt(
                started["session"]["id"], "student-a", started["item"]["id"], "student answer",
            ))
        self.assertEqual(result["session_status"], "completed")
        self.assertTrue(result["summary"]["mastery_verified"])
        self.assertEqual(result["summary"]["outcome_status"], "mastery_verified")

        draft2 = self._ready_draft("student-b")
        started2 = self._start(draft2, use="validation")
        practice_service.request_hint(started2["session"]["id"], "student-b")
        end_choice = json.dumps({"action": "end", "reason": "enough evidence", "evidence_refs": ["student answer"]})
        with (
            patch.object(practice_service, "_grade", new=AsyncMock(return_value=_grade("correct"))),
            patch("app.services.practice.service.llm_service.qa_async", object()),
            patch("app.services.practice.service.llm_service.chat_qa_async", new=AsyncMock(return_value=end_choice)),
        ):
            hinted = asyncio.run(practice_service.submit_attempt(
                started2["session"]["id"], "student-b", started2["item"]["id"], "student answer",
            ))
        self.assertFalse(hinted["summary"]["mastery_verified"])

    def test_ungradable_retries_do_not_consume_question_limit(self) -> None:
        draft = self._ready_draft()
        started = self._start(draft)
        grader = AsyncMock(side_effect=[_grade("ungradable"), _grade("ungradable"), _grade("ungradable")])
        with patch.object(practice_service, "_grade", new=grader):
            first = asyncio.run(practice_service.submit_attempt(
                started["session"]["id"], "student-a", started["item"]["id"], "first",
            ))
            second = asyncio.run(practice_service.submit_attempt(
                started["session"]["id"], "student-a", started["item"]["id"], "second",
            ))
            third = asyncio.run(practice_service.submit_attempt(
                started["session"]["id"], "student-a", started["item"]["id"], "third",
            ))
        self.assertEqual(first["completed_count"], 0)
        self.assertEqual(second["completed_count"], 0)
        self.assertEqual(third["completed_count"], 0)
        self.assertEqual(third["session_status"], "inconclusive")

    def test_zero_usable_items_marks_draft_failed(self) -> None:
        draft = self._create_draft()
        with patch("app.services.practice.agents.list_items", return_value=[]):
            asyncio.run(build_draft(draft))
        stored = repo.get_draft(draft["id"], "student-a")
        self.assertEqual(stored["status"], "failed")
        self.assertEqual(stored["error"], "no_qualified_items")


if __name__ == "__main__":
    unittest.main()
