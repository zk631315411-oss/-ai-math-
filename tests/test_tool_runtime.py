from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict

from app.config import config
from app.db.connection import init_db
from app.db.tool_trace_db import query_tool_traces, redact_arguments, save_tool_trace
from app.db.screenshot_context_cache_db import (
    find_screenshot_context_cache,
    get_screenshot_context_cache,
    save_screenshot_context_cache,
)
from app.db.chat_history_db import delete_chat_history, migrate_user_id, save_chat_history
from app.services.agents.tool_def import ToolDef
from app.services.agents.tool_runtime import ToolRuntime, ToolRuntimeConfig, ToolRuntimeContext
from app.services.qa.vision_extraction import VisionExtraction, _extract_vision_problem_sync


class AddInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    values: list[int]


def _call(call_id: str, name: str, arguments: dict | str):
    raw = arguments if isinstance(arguments, str) else json.dumps(arguments)
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=raw))


def _response(*, content: str = "", calls: list | None = None):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=calls or []))]
    )


class ScriptedModel:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def __call__(self, **kwargs):
        self.requests.append(kwargs)
        return self.responses.pop(0)


async def _collect(runtime: ToolRuntime):
    events = []
    async for event in runtime.run([{"role": "user", "content": "test"}], ToolRuntimeContext("turn-1", "user-1", model_name="fake")):
        events.append(event)
    return events


class ToolRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_tool_call(self):
        model = ScriptedModel([_response(content="直接回答")])
        runtime = ToolRuntime(tools=[], model_call=model)
        result = (await _collect(runtime))[-1].data["result"]
        self.assertEqual(result.content, "直接回答")
        self.assertFalse(result.degraded)

    async def test_stringified_array_is_validated_and_executed(self):
        executions = []

        def add(values):
            executions.append(values)
            return {"sum": sum(values)}

        tool = ToolDef("add", "add", input_model=AddInput, execute=add, display_name="正在计算")
        model = ScriptedModel([
            _response(calls=[_call("c1", "add", {"values": "[1,2,3]"})]),
            _response(content="结果是 6"),
        ])
        events = await _collect(ToolRuntime(tools=[tool], model_call=model))
        self.assertEqual(executions, [[1, 2, 3]])
        self.assertEqual(events[-1].data["result"].stats["succeeded"], 1)
        call_event = next(event for event in events if event.type == "tool_call")
        self.assertNotIn("arguments", call_event.data)

    async def test_same_batch_and_cross_round_duplicates_execute_once(self):
        executions = 0

        def add(values):
            nonlocal executions
            executions += 1
            return {"sum": sum(values)}

        tool = ToolDef("add", "add", input_model=AddInput, execute=add)
        same = {"values": [1, 2]}
        model = ScriptedModel([
            _response(calls=[_call("c1", "add", same), _call("c2", "add", same)]),
            _response(calls=[_call("c3", "add", same)]),
            _response(content="done"),
        ])
        result = (await _collect(ToolRuntime(tools=[tool], model_call=model)))[-1].data["result"]
        self.assertEqual(executions, 1)
        self.assertEqual(result.stats["skipped"], 2)

    async def test_changed_arguments_retry_and_artifact_once(self):
        executions = []
        saved = []

        def artifact(values):
            executions.append(values)
            return {"model_result": {"ok": True}, "artifacts": [{"id": str(values)}]}

        async def save(item, _outcome):
            saved.append(item)
            return item

        tool = ToolDef("artifact", "artifact", input_model=AddInput, execute=artifact, kind="artifact", max_calls_per_turn=2)
        model = ScriptedModel([
            _response(calls=[_call("c1", "artifact", {"values": [1]})]),
            _response(calls=[_call("c2", "artifact", {"values": [2]})]),
            _response(content="done"),
        ])
        events = await _collect(ToolRuntime(tools=[tool], model_call=model, artifact_handler=save))
        result = events[-1].data["result"]
        self.assertEqual(executions, [[1], [2]])
        self.assertEqual(len(saved), 2)
        self.assertEqual(len(result.visualizations), 2)
        self.assertEqual(
            [event.type for event in events],
            ["tool_call", "tool_result", "visualization", "tool_call", "tool_result", "visualization", "final"],
        )

    async def test_failure_budget_forces_final_answer(self):
        tool = ToolDef("add", "add", input_model=AddInput, execute=lambda values: {"sum": sum(values)})
        model = ScriptedModel([
            _response(calls=[_call("bad1", "add", "not-json")]),
            _response(calls=[_call("bad2", "missing", {})]),
            _response(content="基于现有信息回答"),
        ])
        result = (await _collect(ToolRuntime(
            tools=[tool], model_call=model,
            config=ToolRuntimeConfig(max_consecutive_failure_rounds=2),
        )))[-1].data["result"]
        self.assertTrue(result.degraded)
        self.assertEqual(result.degradation_code, "tool_failures")
        self.assertEqual(model.requests[-1]["tool_choice"], "none")
        self.assertEqual(result.content, "基于现有信息回答")

    async def test_cancellation_propagates(self):
        started = asyncio.Event()

        async def model(**_kwargs):
            started.set()
            await asyncio.sleep(10)

        task = asyncio.create_task(_collect(ToolRuntime(tools=[], model_call=model)))
        await started.wait()
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task


class ToolTraceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path = config.DB_PATH
        config.DB_PATH = f"{self.tmp.name}/trace.db"
        init_db()

    def tearDown(self):
        config.DB_PATH = self.old_path
        self.tmp.cleanup()

    def test_trace_redaction_and_query(self):
        summary = redact_arguments({"api_key": "secret", "points": list(range(100)), "query": "sin(x)"})
        self.assertEqual(summary["api_key"], "[redacted]")
        self.assertEqual(summary["points"]["count"], 100)
        save_tool_trace(
            turn_id="turn-x", user_id="user-x", round_index=1, tool_call_id="call-x",
            tool_name="verify_math", call_fingerprint="abc", arguments={"api_key": "secret"},
            status="success", error_code=None, retryable=False, duration_ms=12,
            artifact_ids=[], model_name="fake", chat_history_id="chat-x",
        )
        rows = query_tool_traces(turn_id="turn-x")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["arguments_summary"]["api_key"], "[redacted]")

    def test_trace_follows_chat_migration_and_deletion(self):
        chat_id = save_chat_history("anon-a", "question")
        save_tool_trace(
            turn_id="turn-life", user_id="anon-a", round_index=1, tool_call_id="call-life",
            tool_name="search_textbook", call_fingerprint="life", arguments={"keyword": "极限"},
            status="success", error_code=None, retryable=False, duration_ms=1,
            artifact_ids=[], model_name="fake", chat_history_id=chat_id,
        )
        migrate_user_id("anon-a", "student-a")
        self.assertEqual(query_tool_traces(chat_id=chat_id)[0]["user_id"], "student-a")
        delete_chat_history(chat_id)
        self.assertEqual(query_tool_traces(chat_id=chat_id), [])

    def test_screenshot_cache_is_user_scoped(self):
        cache_id = save_screenshot_context_cache(
            user_id="student-a", image_hash="image-hash", textbook_id="book",
            page_number=3, crop_bbox=None, crop_bbox_hash="bbox", full_context_hash="context",
            pdf_crop_path=None, md_match_status="miss", md_match_confidence=0,
            md_match_text="", locator_signals={}, vision_model="vl-model",
        )
        self.assertIsNotNone(get_screenshot_context_cache(cache_id, "student-a"))
        self.assertIsNone(get_screenshot_context_cache(cache_id, "student-b"))
        self.assertIsNotNone(find_screenshot_context_cache(
            "student-a", "image-hash", "book", 3, "bbox", "context",
        ))
        self.assertIsNone(find_screenshot_context_cache(
            "student-b", "image-hash", "book", 3, "bbox", "context",
        ))


class VisionExtractionTests(unittest.TestCase):
    def test_extraction_uses_compatible_multimodal_client(self):
        content = json.dumps({
            "version": "vision-extraction-v1",
            "problem_text": "求函数 y=x^2 在 x=1 处的切线",
            "formulas": ["y=x^2"],
            "diagram_description": "一条抛物线和一条割线",
            "question_intent": "解释导数的几何意义",
            "confidence": 0.95,
            "tool_ready": True,
        }, ensure_ascii=False)
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )
        with patch(
            "app.services.qa.vision_extraction.llm_service.vision_chat",
            return_value=response,
        ) as vision_chat:
            result = _extract_vision_problem_sync("data:image/png;base64,AA==", "", "")
        self.assertTrue(result.can_use_tools())
        vision_chat.assert_called_once()

    def test_tool_readiness_requires_threshold_and_problem(self):
        ready = VisionExtraction(
            problem_text="求 y=sin(x) 的导数", formulas=[r"y=\sin x"],
            confidence=0.9, tool_ready=True,
        )
        self.assertTrue(ready.can_use_tools(0.7))
        self.assertFalse(ready.model_copy(update={"confidence": 0.69}).can_use_tools(0.7))
        self.assertFalse(ready.model_copy(update={"tool_ready": False}).can_use_tools(0.7))

    def test_invalid_extraction_is_rejected(self):
        with self.assertRaises(Exception):
            VisionExtraction.model_validate({
                "problem_text": "", "formulas": [], "confidence": 2,
                "tool_ready": True, "unexpected": "unsafe",
            })
