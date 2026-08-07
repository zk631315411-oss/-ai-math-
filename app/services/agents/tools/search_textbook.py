"""Search textbook grounding through a validated agent tool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.services.agents.tool_def import ToolDef
from app.services.qa.grounding_service import ground_text_turn


class SearchTextbookInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str = Field(min_length=1, max_length=180, description="概念名、术语或数学表达式")
    textbook_id: str | None = Field(default=None, max_length=200)
    page: int | None = Field(default=None, ge=1, le=10000)


def _search_textbook_impl(keyword: str, textbook_id: str | None = None, page: int | None = None) -> dict:
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
    display_name="查询教材",
    description="在教材中搜索指定概念或关键词，返回页码、章节、原文摘要和相关概念。",
    input_model=SearchTextbookInput,
    execute=_search_textbook_impl,
)
