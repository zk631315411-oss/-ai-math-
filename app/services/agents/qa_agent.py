"""QA Agent：数学问答的 Agent 封装。

将 answer_turn() 和 answer_turn_with_tools() 的流式输出适配为 Agent 统一接口，
使 QA 能力可被 Agent 编排层统一调度。
"""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from app.config import config
from app.services.agents.base import BaseAgent
from app.services.qa.answer_service import answer_turn
from app.services.qa.contracts import QATurnInput
from app.services.qa.streaming_service import sse_error

class QAAgent(BaseAgent):
    """数学问答 Agent：教材定位 + KG 对齐 + 流式回答。"""

    name = "qa"
    description = "数学问答：教材定位 + KG 对齐 + 流式回答"

    def get_tools(self) -> list[dict]:
        """返回工具列表，启用工具调用模式。"""
        return [tool.to_openai_tool() for tool in self.get_tool_defs()]

    def get_tool_defs(self) -> list:
        from app.services.agents.tools import get_qa_tool_defs
        return get_qa_tool_defs()

    async def run(self, input: Any, stream: bool = True) -> AsyncIterator[dict]:
        if input is None:
            yield sse_error("QAAgent 收到空输入，请提供 QATurnInput")
            return
        if not isinstance(input, QATurnInput):
            yield sse_error(f"QAAgent 期望 QATurnInput，收到 {type(input).__name__}")
            return

        async def events():
            tool_defs = self.get_tool_defs()
            if input.input_type == "text" and tool_defs:
                from app.services.qa.answer_service import answer_turn_with_tools
                async for event in answer_turn_with_tools(input, tool_defs=tool_defs):
                    yield event
            else:
                async for event in answer_turn(input):
                    yield event

        timeout = (
            config.QA_TEXT_TURN_TIMEOUT_SECONDS
            if input.input_type == "text"
            else config.QA_SCREENSHOT_TURN_TIMEOUT_SECONDS
        )
        try:
            if timeout > 0:
                async with asyncio.timeout(timeout):
                    async for event in events():
                        yield event
            else:
                async for event in events():
                    yield event
        except TimeoutError:
            yield sse_error("本轮回答超时，请稍后重试")
