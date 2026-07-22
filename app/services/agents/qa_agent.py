"""QA Agent：数学问答的 Agent 封装。

将 answer_turn() 的流式输出适配为 Agent 统一接口，
使 QA 能力可被 Agent 编排层统一调度。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.services.agents.base import BaseAgent
from app.services.qa.answer_service import answer_turn
from app.services.qa.contracts import QATurnInput
from app.services.qa.streaming_service import sse_error


class QAAgent(BaseAgent):
    """数学问答 Agent：教材定位 + KG 对齐 + 流式回答。"""

    name = "qa"
    description = "数学问答：教材定位 + KG 对齐 + 流式回答"

    async def run(self, input: Any, stream: bool = True) -> AsyncIterator[dict]:
        if input is None:
            yield sse_error("QAAgent 收到空输入，请提供 QATurnInput")
            return
        if not isinstance(input, QATurnInput):
            yield sse_error(f"QAAgent 期望 QATurnInput，收到 {type(input).__name__}")
            return
        async for event in answer_turn(input):
            yield event