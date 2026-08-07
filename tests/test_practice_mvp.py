from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from app.config import config
from app.db.connection import init_db
from app.services.practice import repository as repo
from app.services.practice.agents import build_draft
from app.services.practice.seeds import seed_demo_items
from app.services.practice.service import practice_service


ROOT = Path(__file__).resolve().parents[1]
ITEMS_PATH = ROOT / "data" / "practice" / "mvp_items.json"


def _case_context(case: str) -> dict:
    fixtures = {
        "rank": {
            "textbook_id": "gaodai_shang",
            "sequence_id": "V1-C03-S05",
            "concept_ids": ["gaodai_shang:node:ab85433bd4db"],
            "question": "我不会证明子矩阵的秩为什么不超过原矩阵。",
        },
        "independence": {
            "textbook_id": "gaodai_shang",
            "sequence_id": "V1-C03-S02",
            "concept_ids": ["gaodai_shang:node:60a83e5e6d8c"],
            "question": "我对线性无关的定义不理解。",
        },
        "limit": {
            "textbook_id": "gaoshu_shang",
            "sequence_id": "V1-C01-S05",
            "concept_ids": ["gaoshu_shang:node:d5552c5914f9"],
            "question": "我是不是误用了极限运算法则？请用反例说明。",
        },
    }
    context = dict(fixtures[case])
    context.update({
        "turn_id": f"turn-{case}",
        "tree_id": "tree-mvp",
        "node_id": f"node-{case}",
        "concept_names": [],
        "evidence_quote": context["question"],
        "intervention_goal": "根据学生卡点选择可信教材题",
    })
    return context


def test_mvp_asset_pool_is_small_reviewed_and_uses_minimal_contract() -> None:
    items = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))
    exercises = [item for item in items if item["item_kind"] == "exercise_item"]
    examples = [item for item in items if item["item_kind"] == "worked_example"]
    assert len(exercises) == 12
    assert len(examples) == 3
    counts = {}
    for item in items:
        if item["item_kind"] == "exercise_item":
            counts[item["sequence_id"]] = counts.get(item["sequence_id"], 0) + 1
        assert item["kg_mapping_status"] == "verified"
        assert item["review_status"] == "approved"
        assert item["solution_review_status"] in {"reviewed", "teacher_approved"}
        expected_trust = "teacher_approved" if item["item_kind"] == "exercise_item" else "machine_verified"
        assert item["trust_status"] == expected_trust
        assert item["source_locator"].startswith("page:")
        assert len(item["hints"]) == 3
        assert item["rubric"]
        assert "target_stage" not in item
        assert "literacy_tags" not in item
    assert counts == {"V1-C03-S05": 4, "V1-C03-S02": 4, "V1-C01-S05": 4}


def test_three_demo_cases_recall_four_items_and_start_without_a_model() -> None:
    with tempfile.TemporaryDirectory() as directory:
        original = config.DB_PATH
        config.DB_PATH = f"{directory}/mvp.db"
        try:
            init_db()
            assert seed_demo_items() == 15
            expected_goals = {"rank": "proof", "independence": "definition", "limit": "counterexample"}
            for case, expected_goal in expected_goals.items():
                context = _case_context(case)
                draft = repo.create_draft(
                    user_id="student", context=context, trigger_kind="explicit_request",
                    intervention_goal=context["intervention_goal"],
                    evidence_quote=context["evidence_quote"], auto_prepared=False,
                )
                asyncio.run(build_draft(draft))
                stored = repo.get_draft(draft["id"], "student")
                assert stored["status"] == "ready"
                draft_items = repo.list_draft_items(draft["id"], "student")
                assert sum(item["item_kind"] == "exercise_item" for item in draft_items) == 4
                assert sum(item["item_kind"] == "worked_example" for item in draft_items) == 1
                with patch("app.services.practice.service.llm_service.qa_async", None):
                    started = practice_service.start_session(draft["id"], "student")
                assert started["session"]["status"] == "active"
                assert started["item"]["diagnostic_goal"] == expected_goal
                assert started["selection_decision"]["fallback"] is True
                assert "answer_spec" not in started["item"]
                hints = [practice_service.request_hint(started["session"]["id"], "student") for _ in range(3)]
                assert hints[0]["worked_example"] is None
                assert hints[2]["worked_example"]["id"].endswith("worked-example")
                assert hints[2]["worked_example"]["explanation"]
                assert "answer_spec" not in hints[2]["worked_example"]
        finally:
            config.DB_PATH = original


def test_local_demo_grader_supports_correct_partial_and_incorrect() -> None:
    item = json.loads(ITEMS_PATH.read_text(encoding="utf-8"))[4]
    correct = practice_service._fallback_grade(
        item, "不对，因为任意向量组都能取全零系数；线性无关要求只能全为零。"
    )
    partial = practice_service._fallback_grade(item, "这个说法不对。")
    incorrect = practice_service._fallback_grade(item, "这个说法正确。")
    assert correct["verdict"] == "correct"
    assert partial["verdict"] == "partial"
    assert incorrect["verdict"] == "incorrect"
