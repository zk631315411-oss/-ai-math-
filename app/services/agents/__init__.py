"""Agent 基础设施模块。

导出所有 Agent 类和注册表操作函数，
路由层通过此模块统一使用 Agent 能力。
"""

from __future__ import annotations

from app.services.agents.base import BaseAgent
from app.services.agents.exercise_agent import ExerciseAgent
from app.services.agents.qa_agent import QAAgent
from app.services.agents.registry import AGENT_REGISTRY, clear, get_agent, list_agents, register

__all__ = [
    "AGENT_REGISTRY",
    "BaseAgent",
    "ExerciseAgent",
    "QAAgent",
    "clear",
    "get_agent",
    "list_agents",
    "register",
]