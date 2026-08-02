"""QA 回答模块的数据契约。

这些对象只描述一次问答如何发生，不负责诊断学生长期状态。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


QAInputType = Literal["text", "image", "mixed"]


@dataclass(frozen=True)
class QATurnInput:
    """用户发起的一轮 QA 输入。"""

    user_id: str
    question: str
    input_type: QAInputType = "text"
    chat_id: str | None = None
    marker_id: str | None = None
    textbook_id: str | None = None
    page_number: int | None = None
    history: list[dict] | None = None
    teaching_mode: str = "socratic"
    socratic_submode: str = "unclassified"
    image_data: str | None = None
    crop_bbox: dict[str, Any] | None = None
    screenshot_context_id: str | None = None
    token: str | None = None
    tree_id: str | None = None
    node_id: str | None = None
    fork_message_id: str | None = None
    referenced_node_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class QATurnContext:
    """模型回答前整理出的上下文快照。"""

    turn_id: str
    input_type: QAInputType
    textbook_id: str | None = None
    page_number: int | None = None
    marker_id: str | None = None
    sequence_id: str | None = None
    section_node_id: str | None = None
    chapter_name: str = ""
    page_excerpt: str = ""
    sources: list[dict] = field(default_factory=list)
    image_hash: str | None = None
    crop_bbox: dict[str, Any] | None = None
    pdf_crop_path: str | None = None
    screenshot_context_id: str | None = None
    locator_result: dict[str, Any] | None = None
    model_name: str | None = None
    prompt_preview: str = ""
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    messages_snapshot: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class QAAnswerResult:
    """模型回答完成后的结果。"""

    turn_id: str
    answer: str
    thinking: str = ""
    sources: list[dict] = field(default_factory=list)
    sequence_id: str | None = None
    section_node_id: str | None = None
    model_name: str | None = None
    latency_ms: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class QAStreamEvent:
    """对外流式输出事件的统一形状。"""

    event: Literal[
        "stage", "content", "thinking", "thinking_chunk",
        "done", "error", "heartbeat",
        "wait_for_input", "progress",
        "tool_call", "tool_result",
    ]
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class QATurnRecord:
    """需要持久化、也给认知诊断模块离线消费的一轮 QA 事实记录。"""

    turn_id: str
    user_id: str
    chat_id: str | None
    input_type: QAInputType
    question: str
    marker_id: str | None = None
    apprenticeship_level: str | None = None  # 脚手架层级（MODELING/COACHING/SCAFFOLDING/FADING）
    answer: str = ""
    textbook_id: str | None = None
    page_number: int | None = None
    sequence_id: str | None = None
    section_node_id: str | None = None
    chapter_name: str = ""
    sources: list[dict] = field(default_factory=list)
    context_snapshot: dict[str, Any] = field(default_factory=dict)
    messages_snapshot: list[dict] = field(default_factory=list)
    image_hash: str | None = None
    crop_bbox: dict[str, Any] | None = None
    screenshot_context_id: str | None = None
    prompt_preview: str = ""
    model_name: str | None = None
    latency_ms: int | None = None
    error: str | None = None
    created_at: str | None = None
