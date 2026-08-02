from __future__ import annotations

import json
import tempfile
import unittest

from app.config import config
from app.db.chat_history_db import save_chat_history
from app.db.chat_tree_db import (
    InvalidFork,
    RevisionConflict,
    append_message,
    archive_node,
    begin_turn,
    create_fork,
    create_tree,
    create_summary_tree,
    ensure_tree_from_history,
    finish_turn,
    get_authorized_context,
    get_tree,
    migrate_legacy_followups,
    restore_node,
    update_summary_node,
)
from app.db.connection import init_db


class ChatTreeDbTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_db_path = config.DB_PATH
        config.DB_PATH = f"{self.temp_dir.name}/tree.db"
        init_db()
        self.user = "student-tree"

    def tearDown(self) -> None:
        config.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def test_create_and_append_stay_in_one_node(self) -> None:
        tree = create_tree(self.user, "marker-1", "基础问题", "第一轮回答")
        root = tree["nodes"][0]
        self.assertEqual(len(root["messages"]), 2)
        appended = append_message(root["id"], self.user, "user", "继续问一个细节", expected_revision=root["revision"])
        self.assertEqual(appended["sequence_no"], 2)
        updated = get_tree(tree["id"], self.user)
        self.assertEqual(len(updated["nodes"]), 1)
        self.assertEqual(len(updated["nodes"][0]["messages"]), 3)

    def test_fork_requires_completed_ai_anchor_and_freezes_anchor(self) -> None:
        tree = create_tree(self.user, "marker-2", "基础问题", "回答一")
        root = tree["nodes"][0]
        answer_id = root["messages"][1]["id"]
        child = create_fork(root["id"], self.user, answer_id, "为什么？", expected_revision=root["revision"])
        self.assertEqual(child["parent_node_id"], root["id"])
        self.assertEqual(child["fork_message_id"], answer_id)
        append_message(root["id"], self.user, "user", "父节点后续消息")
        context = get_authorized_context(child["id"], self.user)
        self.assertEqual([m["content"] for m in context], ["基础问题", "回答一", "为什么？"])
        self.assertNotIn("父节点后续消息", [m["content"] for m in context])
        with self.assertRaises(InvalidFork):
            create_fork(child["id"], self.user, child["messages"][0]["id"], "错误锚点")

    def test_durable_turn_is_idempotent_and_finalizes_assistant(self) -> None:
        tree = create_tree(self.user, "marker-turn", "基础问题", "回答一")
        root = tree["nodes"][0]
        anchor = root["messages"][1]["id"]

        started = begin_turn(
            root["id"], self.user, "为什么？", turn_id="client-turn-1",
            fork_message_id=anchor,
        )
        self.assertTrue(started["created"])
        self.assertEqual(started["parent_node_id"], root["id"])
        self.assertEqual(started["assistant_message"]["status"], "streaming")

        retried = begin_turn(
            root["id"], self.user, "为什么？", turn_id="client-turn-1",
            fork_message_id=anchor,
        )
        self.assertFalse(retried["created"])
        self.assertEqual(retried["node_id"], started["node_id"])
        self.assertEqual(retried["user_message"]["id"], started["user_message"]["id"])

        completed = finish_turn("client-turn-1", self.user, "因为这是必要条件。", "completed")
        self.assertEqual(completed["assistant_message"]["status"], "completed")
        self.assertEqual(completed["assistant_message"]["content"], "因为这是必要条件。")
        unchanged = finish_turn("client-turn-1", self.user, "不应覆盖", "failed")
        self.assertEqual(unchanged["assistant_message"]["status"], "completed")
        self.assertEqual(unchanged["assistant_message"]["content"], "因为这是必要条件。")
        child = get_tree(tree["id"], self.user)["nodes"][-1]
        self.assertEqual(len(child["messages"]), 2)

    def test_terminal_message_limits_prospective_fork_context(self) -> None:
        tree = create_tree(self.user, "marker-terminal", "问题一", "回答一")
        root = tree["nodes"][0]
        first_answer = root["messages"][1]["id"]
        append_message(root["id"], self.user, "user", "问题二")
        append_message(root["id"], self.user, "assistant", "回答二")

        context = get_authorized_context(
            root["id"], self.user, terminal_message_id=first_answer
        )
        self.assertEqual([message["content"] for message in context], ["问题一", "回答一"])

    def test_failed_turn_keeps_auditable_user_question(self) -> None:
        tree = create_tree(self.user, "marker-failed", "根问题", "根回答")
        root = tree["nodes"][0]
        started = begin_turn(root["id"], self.user, "失败问题", turn_id="failed-turn")
        failed = finish_turn("failed-turn", self.user, "部分输出", "failed")
        self.assertEqual(failed["node_id"], started["node_id"])
        self.assertEqual(failed["assistant_message"]["status"], "failed")
        self.assertEqual(failed["assistant_message"]["content"], "部分输出")

    def test_sibling_is_not_read_without_explicit_reference(self) -> None:
        tree = create_tree(self.user, "marker-3", "基础问题", "回答")
        root = tree["nodes"][0]
        anchor = root["messages"][1]["id"]
        first = create_fork(root["id"], self.user, anchor, "分支一")
        append_message(first["id"], self.user, "assistant", "分支一回答")
        second = create_fork(root["id"], self.user, anchor, "分支二")
        append_message(second["id"], self.user, "assistant", "分支二回答")
        context = get_authorized_context(first["id"], self.user)
        self.assertNotIn("分支二回答", [m["content"] for m in context])

    def test_archive_restore_and_revision_conflict(self) -> None:
        tree = create_tree(self.user, "marker-4", "问题", "回答")
        root = tree["nodes"][0]
        child = create_fork(root["id"], self.user, root["messages"][1]["id"], "追问")
        archived = archive_node(child["id"], self.user, expected_revision=child["revision"])
        self.assertIsNotNone(archived["archived_at"])
        restored = restore_node(child["id"], self.user, expected_revision=archived["revision"])
        self.assertIsNone(restored["archived_at"])
        with self.assertRaises(RevisionConflict):
            append_message(root["id"], self.user, "user", "过期写入", expected_revision=0)

    def test_legacy_followups_migration_is_idempotent_and_approximate(self) -> None:
        marker_id = save_chat_history(
            self.user,
            "旧问题",
            "旧回答",
            follow_ups=json.dumps([{"question": "旧追问", "answer": "旧追问回答"}], ensure_ascii=False),
        )
        self.assertEqual(migrate_legacy_followups(self.user), 2)
        self.assertEqual(migrate_legacy_followups(self.user), 0)
        tree = get_tree(get_tree_by_history_for_test(marker_id, self.user), self.user, include_archived=True)
        child = next(n for n in tree["nodes"] if n["parent_node_id"])
        self.assertEqual(child["migration_quality"], "legacy_approximate")
        self.assertEqual(child["fork_message_id"], tree["nodes"][0]["messages"][1]["id"])

    def test_lazy_migration_materializes_only_requested_history(self) -> None:
        requested = save_chat_history(self.user, "请求迁移", "回答")
        untouched = save_chat_history(self.user, "暂不迁移", "回答")
        tree = ensure_tree_from_history(requested, self.user)
        self.assertEqual(tree["root_chat_history_id"], requested)
        self.assertIsNone(get_tree_by_history_for_test_optional(untouched, self.user))
        repeated = ensure_tree_from_history(requested, self.user)
        self.assertEqual(repeated["id"], tree["id"])

    def test_context_builder_excludes_current_persisted_turn(self) -> None:
        from app.models.schemas import QARequest
        from app.routers.qa import _authorized_history

        tree = create_tree(self.user, "marker-current", "当前问题", None)
        root = tree["nodes"][0]
        request = QARequest(user_id=self.user, question="当前问题", node_id=root["id"], history=[{"user": "越权", "assistant": "不应读取"}])
        self.assertEqual(_authorized_history(request, self.user), [])

    def test_router_rejects_jwt_for_another_user(self) -> None:
        from app.auth.jwt_handler import create_access_token
        from app.routers.chat_tree import _validated_user_id
        from fastapi import HTTPException

        token = create_access_token({"user_id": self.user})
        self.assertEqual(_validated_user_id(self.user, f"Bearer {token}"), self.user)
        with self.assertRaises(HTTPException) as missing:
            _validated_user_id(self.user, None)
        self.assertEqual(missing.exception.status_code, 401)
        with self.assertRaises(HTTPException) as context:
            _validated_user_id("other-user", f"Bearer {token}")
        self.assertEqual(context.exception.status_code, 403)

    def test_summary_is_versioned_source_linked_and_user_edits_lock(self) -> None:
        tree = create_tree(self.user, "marker-summary", "总结问题", "AI 讲解")
        source_id = tree["nodes"][0]["messages"][1]["id"]
        summary = create_summary_tree(tree["id"], self.user, [{
            "node_type": "conclusion",
            "learning_status": "explained",
            "title": "结论",
            "content": "尚未由学生验证",
            "source_message_ids": [source_id],
        }], created_by="agent")
        self.assertEqual(summary["version"], 1)
        self.assertEqual(json.loads(summary["nodes"][0]["source_message_ids"]), [source_id])
        edited = update_summary_node(summary["nodes"][0]["id"], self.user, content="学生人工修订", lock=True, expected_revision=0)
        self.assertEqual(edited["content"], "学生人工修订")
        self.assertEqual(edited["edited_by_user"], 1)
        self.assertEqual(edited["locked"], 1)

    def test_context_api_reads_repeated_reference_query_parameters(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers.chat_tree import router
        from app.db.chat_tree_db import set_references

        tree = create_tree(self.user, "marker-query", "根问题", "根回答")
        root = tree["nodes"][0]
        anchor = root["messages"][1]["id"]
        first = create_fork(root["id"], self.user, anchor, "分支一")
        second = create_fork(root["id"], self.user, anchor, "分支二")
        answer = append_message(second["id"], self.user, "assistant", "授权回答")
        set_references(first["id"], self.user, [second["id"]], {second["id"]: [answer["id"]]})

        app = FastAPI()
        app.include_router(router)
        from app.auth.jwt_handler import create_access_token
        token = create_access_token({"user_id": self.user})
        response = TestClient(app).get(
            f"/api/chat/nodes/{first['id']}/context",
            params=[("user_id", self.user), ("referenced_node_ids", second["id"])],
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("授权回答", [message["content"] for message in response.json()])

    def test_referenced_answer_does_not_consume_current_user_turn(self) -> None:
        from app.models.schemas import QARequest
        from app.routers.qa import _authorized_history
        from app.db.chat_tree_db import set_references

        tree = create_tree(self.user, "marker-reference-pair", "根问题", "根回答")
        root = tree["nodes"][0]
        anchor = root["messages"][1]["id"]
        current = create_fork(root["id"], self.user, anchor, "当前分支")
        append_message(current["id"], self.user, "assistant", "当前分支回答")
        sibling = create_fork(root["id"], self.user, anchor, "兄弟分支")
        selected = append_message(sibling["id"], self.user, "assistant", "被选中的兄弟回答")
        set_references(current["id"], self.user, [sibling["id"]], {sibling["id"]: [selected["id"]]})
        append_message(current["id"], self.user, "user", "本轮新问题")

        request = QARequest(user_id=self.user, question="本轮新问题", node_id=current["id"], referenced_node_ids=[sibling["id"]])
        history = _authorized_history(request, self.user)
        self.assertNotIn("本轮新问题", [turn["user"] for turn in history])
        self.assertIn("被选中的兄弟回答", [turn["assistant"] for turn in history])
        self.assertIn("[用户显式引用的其他分支回答]", [turn["user"] for turn in history])

    def test_qa_stream_owns_tree_turn_and_uses_fork_context(self) -> None:
        from unittest.mock import patch
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.auth.jwt_handler import create_access_token
        from app.routers.qa import router
        from app.services.qa.streaming_service import sse_done, sse_text

        tree = create_tree(self.user, "marker-stream", "问题一", "回答一")
        root = tree["nodes"][0]
        first_answer = root["messages"][1]["id"]
        append_message(root["id"], self.user, "user", "父节点后续问题")
        append_message(root["id"], self.user, "assistant", "父节点后续回答")
        captured = {}

        async def fake_answer_turn(turn_input):
            captured["history"] = turn_input.history
            captured["node_id"] = turn_input.node_id
            yield sse_text("分支回答")
            yield sse_done(full_text="分支回答", sources=[])

        app = FastAPI()
        app.include_router(router)
        token = create_access_token({"user_id": self.user})
        with patch("app.routers.qa.answer_turn", new=fake_answer_turn):
            response = TestClient(app).post(
                "/api/qa/solve-stream",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "user_id": self.user,
                    "question": "分支问题",
                    "tree_id": tree["id"],
                    "node_id": root["id"],
                    "fork_message_id": first_answer,
                    "client_turn_id": "stream-turn-1",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("event: tree_turn_started", response.text)
        self.assertEqual(
            captured["history"], [{"user": "问题一", "assistant": "回答一"}]
        )
        self.assertNotEqual(captured["node_id"], root["id"])
        updated = get_tree(tree["id"], self.user)
        child = next(node for node in updated["nodes"] if node["id"] == captured["node_id"])
        self.assertEqual(
            [(message["role"], message["status"], message["content"]) for message in child["messages"]],
            [("user", "completed", "分支问题"), ("assistant", "completed", "分支回答")],
        )

    def test_qa_tree_stream_requires_bearer_token(self) -> None:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from app.routers.qa import router

        tree = create_tree(self.user, "marker-auth-stream", "问题", "回答")
        root = tree["nodes"][0]
        app = FastAPI()
        app.include_router(router)
        response = TestClient(app).post(
            "/api/qa/solve-stream",
            json={
                "user_id": self.user,
                "question": "追问",
                "tree_id": tree["id"],
                "node_id": root["id"],
                "client_turn_id": "missing-auth-turn",
            },
        )
        self.assertEqual(response.status_code, 401)


def get_tree_by_history_for_test(marker_id: str, user_id: str) -> str:
    from app.db.chat_tree_db import get_tree_by_history
    return get_tree_by_history(marker_id, user_id)["id"]


def get_tree_by_history_for_test_optional(marker_id: str, user_id: str):
    from app.db.chat_tree_db import get_tree_by_history
    return get_tree_by_history(marker_id, user_id)


if __name__ == "__main__":
    unittest.main()
