"""工具定义模型。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDef:
    """工具定义。"""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    execute: Callable[..., Any] | None = None

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI Function Calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }