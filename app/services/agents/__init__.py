"""Agent 基础设施模块。

导出所有 Agent 类和注册表操作函数，
路由层通过此模块统一使用 Agent 能力。
"""

from __future__ import annotations

from app.services.agents.base import BaseAgent
from app.services.agents.exercise_agent import ExerciseAgent
from app.services.agents.qa_agent import QAAgent
from app.services.agents.registry import AGENT_REGISTRY, clear, get_agent, list_agents, register
from app.services.agents.tool_def import ToolDef
from app.services.agents.tool_executor import execute_tool_call, execute_tool_calls
from app.services.agents.tool_runtime import ToolRuntime, ToolRuntimeConfig, ToolRuntimeContext

# 注册工具
def _register_tools() -> None:
    """注册所有工具定义到各 Agent。"""
    pass  # 工具已通过各 tool 文件模块级注册


__all__ = [
    "AGENT_REGISTRY",
    "BaseAgent",
    "ExerciseAgent",
    "QAAgent",
    "ToolDef",
    "ToolRuntime",
    "ToolRuntimeConfig",
    "ToolRuntimeContext",
    "execute_tool_call",
    "execute_tool_calls",
    "clear",
    "get_agent",
    "list_agents",
    "register",
]
