"""search_textbook 工具：在教材中搜索关键词。"""

from __future__ import annotations

from app.services.agents.tool_def import ToolDef
from app.services.qa.grounding_service import ground_text_turn


def _search_textbook_impl(
    keyword: str,
    textbook_id: str | None = None,
    page: int | None = None,
) -> dict:
    """在教材中搜索关键词，返回原文段落和定位信息。"""
    grounding = ground_text_turn(
        textbook_id=textbook_id or "",
        page_number=page,
        question=keyword,
    )
    return {
        "textbook_id": grounding.textbook_id,
        "page_number": grounding.page_number,
        "chapter_name": grounding.chapter_name,
        "content_excerpt": (grounding.content_excerpt or "")[:2000],
        "related_concepts": [
            {"name": node.name, "type": node.node_type or "KGNode"}
            for node in grounding.related_concepts[:10]
            if node.name
        ],
        "confidence": grounding.confidence,
    }


search_textbook_tool = ToolDef(
    name="search_textbook",
    description="在教材中搜索指定概念或关键词的原文段落，返回教材名称、页码、章节名和原文内容",
    input_schema={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，可以是概念名、术语或数学表达式",
            },
            "textbook_id": {
                "type": "string",
                "description": "教材ID，可选，不传时自动检测",
            },
            "page": {
                "type": "integer",
                "description": "页码，可选，指定后返回该页相关内容",
            },
        },
        "required": ["keyword"],
    },
    execute=_search_textbook_impl,
)