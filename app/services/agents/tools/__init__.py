"""Agent tool implementations and the canonical QA tool list."""

from __future__ import annotations

from app.services.agents.tool_def import ToolDef


def get_qa_tool_defs() -> list[ToolDef]:
    from app.services.agents.tools.create_math_visualization import create_math_visualization_tool
    from app.services.agents.tools.lookup_kg_node import lookup_kg_node_tool
    from app.services.agents.tools.search_textbook import search_textbook_tool
    from app.services.agents.tools.verify_math import verify_math_tool

    return [
        search_textbook_tool,
        lookup_kg_node_tool,
        verify_math_tool,
        create_math_visualization_tool,
    ]


__all__ = ["get_qa_tool_defs"]
