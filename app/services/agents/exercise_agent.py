"""Exercise Agent：智能出题的 Agent 封装（占位实现）。

当前仅提供占位事件，后续 Phase 再对接 exercise 路由的流式接口。
"""

from __future__ import annotations

from typing import Any, AsyncIterator

from app.models.schemas import ExerciseGenerateRequest
from app.services.agents.base import BaseAgent
from app.services.qa.streaming_service import sse_event


class ExerciseAgent(BaseAgent):
    """智能出题 Agent：根据教材页上下文生成练习题（占位）。"""

    name = "exercise"
    description = "智能出题：根据教材页上下文生成练习题"

    async def run(self, input: Any, stream: bool = True) -> AsyncIterator[dict]:
        if input is None:
            yield sse_event("error", {"error": "ExerciseAgent 收到空输入，请提供 ExerciseGenerateRequest"})
            return
        if not isinstance(input, ExerciseGenerateRequest):
            yield sse_event("error", {"error": f"ExerciseAgent 期望 ExerciseGenerateRequest，收到 {type(input).__name__}"})
            return
        yield sse_event("stage", {"stage": "not_implemented", "text": "ExerciseAgent 尚未对接流式接口"})