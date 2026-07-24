"""QA Agent：数学问答的 Agent 封装。

将 answer_turn() 和 answer_turn_with_tools() 的流式输出适配为 Agent 统一接口，
使 QA 能力可被 Agent 编排层统一调度。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.services.agents.base import BaseAgent
from app.services.qa.answer_service import answer_turn
from app.services.qa.contracts import QATurnInput
from app.services.qa.streaming_service import sse_error

# 延迟 import 避免循环依赖
def _get_tools() -> list:
    """获取 QAAgent 注册的工具列表。"""
    from app.services.agents.tools.search_textbook import search_textbook_tool
    from app.services.agents.tools.lookup_kg_node import lookup_kg_node_tool
    from app.services.agents.tools.verify_math import verify_math_tool
    return [
        search_textbook_tool.to_openai_tool(),
        lookup_kg_node_tool.to_openai_tool(),
        verify_math_tool.to_openai_tool(),
    ]


class QAAgent(BaseAgent):
    """数学问答 Agent：教材定位 + KG 对齐 + 流式回答。"""

    name = "qa"
    description = "数学问答：教材定位 + KG 对齐 + 流式回答"

    def get_tools(self) -> list[dict]:
        """返回工具列表，启用工具调用模式。"""
        return _get_tools()

    async def run(self, input: Any, stream: bool = True) -> AsyncIterator[dict]:
        if input is None:
            yield sse_error("QAAgent 收到空输入，请提供 QATurnInput")
            return
        if not isinstance(input, QATurnInput):
            yield sse_error(f"QAAgent 期望 QATurnInput，收到 {type(input).__name__}")
            return

        tools = self.get_tools()
        if tools:
            from app.services.qa.answer_service import answer_turn_with_tools
            async for event in answer_turn_with_tools(input, tools=tools):
                yield event
        else:
            async for event in answer_turn(input):
                yield event