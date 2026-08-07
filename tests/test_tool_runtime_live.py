"""Opt-in live DashScope tool-calling smoke tests.

Run with RUN_LIVE_TOOL_SMOKE=1 after configuring QA_LLM_API_KEY.
"""

from __future__ import annotations

import os
import unittest

from app.config import config
from app.services.agents.tool_runtime import ToolRuntime, ToolRuntimeContext
from app.services.agents.tools import get_qa_tool_defs
from app.services.llm_service import llm_service


@unittest.skipUnless(os.getenv("RUN_LIVE_TOOL_SMOKE") == "1", "live model smoke disabled")
class LiveToolRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def _assert_calls(self, prompt: str, expected_tool: str) -> None:
        runtime = ToolRuntime(tools=get_qa_tool_defs(), model_call=llm_service.chat_with_tools_async)
        called = []
        final = None
        async for event in runtime.run(
            [{"role": "user", "content": prompt}],
            ToolRuntimeContext(f"live-{expected_tool}", "live-smoke", model_name=config.QA_LLM_MODEL),
        ):
            if event.type == "tool_call":
                called.append(event.data["name"])
            elif event.type == "final":
                final = event.data["result"]
        self.assertIn(expected_tool, called)
        self.assertIsNotNone(final)
        self.assertTrue(final.content)

    async def test_function_plot(self):
        await self._assert_calls(
            "必须调用 create_math_visualization 绘制 y=sin(x)，然后简短解释。",
            "create_math_visualization",
        )

    async def test_shear_matrix_plot(self):
        await self._assert_calls(
            "必须调用 create_math_visualization 展示矩阵 [[1,1],[0,1]] 对向量 (1,1) 的二维变换。",
            "create_math_visualization",
        )

    async def test_textbook_search(self):
        await self._assert_calls("必须调用 search_textbook 查询特征值的教材定义。", "search_textbook")

    async def test_kg_lookup(self):
        await self._assert_calls("必须调用 lookup_kg_node 查询矩阵相似的知识关系。", "lookup_kg_node")

    async def test_math_verification(self):
        await self._assert_calls("必须调用 verify_math 验证多项式 x^2-1 的因式分解。", "verify_math")
