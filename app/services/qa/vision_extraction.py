"""Versioned structured extraction for screenshot-to-ToolRuntime handoff."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.config import config
from app.services.llm_service import llm_service


VISION_EXTRACTION_VERSION = "vision-extraction-v1"


class VisionExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = VISION_EXTRACTION_VERSION
    problem_text: str = Field(min_length=1, max_length=8000)
    formulas: list[str] = Field(default_factory=list, max_length=50)
    diagram_description: str = Field(default="", max_length=4000)
    question_intent: str = Field(default="", max_length=1000)
    confidence: float = Field(ge=0, le=1)
    tool_ready: bool

    def can_use_tools(self, threshold: float | None = None) -> bool:
        cutoff = config.VISION_EXTRACTION_CONFIDENCE if threshold is None else threshold
        return bool(self.tool_ready and self.problem_text.strip() and self.confidence >= cutoff)


async def extract_vision_problem(image_data: str, locator_prompt: str, student_question: str) -> VisionExtraction:
    """Ask the existing DashScope VL model for a strict extraction object."""
    return await asyncio.to_thread(
        _extract_vision_problem_sync, image_data, locator_prompt, student_question,
    )


def _extract_vision_problem_sync(image_data: str, locator_prompt: str, student_question: str) -> VisionExtraction:
    prompt = f"""你是数学题目转写器。只识别题意，不解题。
请根据图片和定位上下文返回一个 JSON 对象，禁止 Markdown 代码块和额外文字。
字段必须为：
- version: 固定为 {VISION_EXTRACTION_VERSION}
- problem_text: 完整、可独立理解的题目文字
- formulas: 图片中公式的 LaTeX 字符串数组
- diagram_description: 图形、坐标轴和标注的客观描述，无图则为空字符串
- question_intent: 学生要求求解、证明、解释或作图的目标
- confidence: 0 到 1，公式或关键条件不清楚时必须降低
- tool_ready: 只有题目、公式和关键条件足够可靠时才为 true

不要猜测模糊字符；不能可靠识别时 tool_ready=false。

定位上下文：
{locator_prompt[:2400]}

学生补充问题：{student_question or '请分析这道题'}"""
    response = llm_service.vision_chat(image_data, prompt)
    choices = getattr(response, "choices", None) or []
    if not choices:
        raise RuntimeError("图片结构化识别未返回内容")
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", "")
    text = "".join(_content_text(content)).strip()
    return VisionExtraction.model_validate(_parse_json_object(text))


def format_extracted_question(extraction: VisionExtraction, student_question: str) -> str:
    parts = [f"【截图识别题目】\n{extraction.problem_text}"]
    if extraction.formulas:
        parts.append("【识别公式】\n" + "\n".join(extraction.formulas))
    if extraction.diagram_description:
        parts.append("【图形描述】\n" + extraction.diagram_description)
    if extraction.question_intent:
        parts.append("【题目意图】\n" + extraction.question_intent)
    if student_question:
        parts.append("【学生补充问题】\n" + student_question)
    return "\n\n".join(parts)


def _content_text(content: Any) -> list[str]:
    if isinstance(content, list):
        return [str(item.get("text")) for item in content if isinstance(item, dict) and item.get("text")]
    return [str(content)] if content else []


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fence:
        cleaned = fence.group(1)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("视觉提取结果必须是 JSON 对象")
    return value
