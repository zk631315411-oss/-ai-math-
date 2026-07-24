"""工具执行器。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.services.agents.tool_def import ToolDef

# 工具执行超时（秒）
TOOL_TIMEOUT_SECONDS = 15


class ToolExecutionError(Exception):
    """工具执行异常。"""
    pass


async def execute_tool_call(
    tool_call: Any,
    tools: list[ToolDef],
) -> dict[str, Any]:
    """执行单个 tool_call。"""
    tool_name = tool_call.function.name
    tool = _find_tool(tool_name, tools)

    if tool is None or tool.execute is None:
        raise ToolExecutionError(f"工具 '{tool_name}' 未注册或未实现")

    try:
        arguments = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise ToolExecutionError(f"工具 '{tool_name}' 参数解析失败: {e}")

    try:
        # 工具可以是同步函数或异步函数，统一处理
        if asyncio.iscoroutinefunction(tool.execute):
            result = await asyncio.wait_for(
                tool.execute(**arguments),
                timeout=TOOL_TIMEOUT_SECONDS,
            )
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(tool.execute, **arguments),
                timeout=TOOL_TIMEOUT_SECONDS,
            )
    except asyncio.TimeoutError:
        raise ToolExecutionError(f"工具 '{tool_name}' 执行超时（{TOOL_TIMEOUT_SECONDS}s）")
    except Exception as e:
        raise ToolExecutionError(f"工具 '{tool_name}' 执行异常: {e}")

    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(result, ensure_ascii=False),
    }


async def execute_tool_calls(
    tool_calls: list[Any],
    tools: list[ToolDef],
) -> list[dict[str, Any]]:
    """并发执行多个 tool_call。"""
    tasks = [execute_tool_call(tc, tools) for tc in tool_calls]
    return await asyncio.gather(*tasks, return_exceptions=True)


def _find_tool(name: str, tools: list[ToolDef]) -> ToolDef | None:
    for tool in tools:
        if tool.name == name:
            return tool
    return None