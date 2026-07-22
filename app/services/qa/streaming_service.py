"""QA 流式输出辅助函数。"""

from __future__ import annotations

import json

from app.services.qa.event_bus import StreamBus


def sse_event(event: str, data: dict) -> dict:
    """统一生成 EventSourceResponse 可直接消费的事件。"""

    return {"event": event, "data": json.dumps(data, ensure_ascii=False)}


def sse_stage(stage: str, text: str) -> dict:
    return sse_event("stage", {"stage": stage, "text": text})


def sse_text(text: str) -> dict:
    return sse_event("content", {"text": text})


def sse_done(**data) -> dict:
    return sse_event("done", data)


def sse_error(error: str) -> dict:
    return sse_event("error", {"error": error})


def sse_format(event: str, data: dict) -> str:
    """生成 SSE 格式字符串，用于 StreamingResponse 直接消费。"""
    return f"data: {json.dumps({'event': event, 'data': data}, ensure_ascii=False)}\n\n"


def emit_event(bus: StreamBus, event: str, data: dict) -> None:
    """向 StreamBus 发布事件。"""
    bus.emit({"event": event, "data": json.dumps(data, ensure_ascii=False)})

