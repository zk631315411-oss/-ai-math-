from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from app.models.schemas import QARequest
from app.auth.jwt_handler import decode_token
from app.db.user_profile_db import get_user_profile
from app.services.qa import QATurnInput, answer_turn, has_screenshot_context
from app.services.qa.streaming_service import sse_event

router = APIRouter(prefix="/api/qa", tags=["题目答疑"])


# SSE 心跳间隔（秒），每 15s 发一次 heartbeat 防止前端超时断开
SSE_HEARTBEAT_INTERVAL = 15


async def _heartbeat(events: asyncio.Queue):
    """后台心跳任务，每 15s 发一次 heartbeat 事件。"""
    try:
        while True:
            await asyncio.sleep(SSE_HEARTBEAT_INTERVAL)
            events.put_nowait(sse_event("heartbeat", {"text": ""}))
    except asyncio.CancelledError:
        pass


async def _generate_with_heartbeat(generate):
    """在 generate() 基础上叠加心跳事件。"""
    events: asyncio.Queue = asyncio.Queue()
    task = asyncio.create_task(_heartbeat(events))

    async def producer():
        try:
            async for event in generate:
                events.put_nowait(event)
        finally:
            task.cancel()
            # 消费完所有事件后，放入 sentinel 标记结束
            events.put_nowait(None)

    asyncio.create_task(producer())

    while True:
        event = await events.get()
        if event is None:
            break
        yield event


def get_user_id_and_profile(request: QARequest) -> tuple:
    """从request中获取user_id和用户画像"""
    user_id = request.user_id
    profile = None

    # 优先从token解析
    if request.token:
        try:
            token_data = decode_token(request.token)
            user_id = token_data.get("user_id")
        except Exception:
            pass

    # 如果有user_id，获取用户画像
    if user_id:
        profile = get_user_profile(user_id)

    return user_id or f"anon_{request.device_id or 'unknown'}", profile


@router.post("/solve-stream")
async def solve_question_stream(request: QARequest):
    """
    题目答疑接口 - 流式输出 (SSE)
    """
    async def generate():
        try:
            question = request.question
            teaching_mode = getattr(request, 'teaching_mode', 'socratic') or 'socratic'

            # 优先获取 user_id（图片和非图片分支都需要）
            user_id, _ = get_user_id_and_profile(request)
            marker_id = request.marker_id or request.page_id or request.chat_id

            visual_input = QATurnInput(
                user_id=user_id or "anonymous",
                chat_id=getattr(request, "chat_id", None),
                marker_id=marker_id,
                question=question or "请分析这道题",
                input_type="mixed" if question else "image",
                textbook_id=request.textbook_id,
                page_number=request.page_number,
                history=request.history,
                teaching_mode=teaching_mode,
                socratic_submode=getattr(request, "socratic_submode", "unclassified") or "unclassified",
                image_data=request.image_data,
                crop_bbox=request.crop_bbox,
                screenshot_context_id=request.screenshot_context_id,
                token=request.token,
            )
            if has_screenshot_context(visual_input):
                async for event in answer_turn(visual_input):
                    yield event
                return

            if not question:
                yield {"event": "error", "data": json.dumps({"error": "未能识别题目内容"})}
                return

            qa_input = QATurnInput(
                user_id=user_id or "anonymous",
                chat_id=getattr(request, "chat_id", None),
                marker_id=marker_id,
                question=question,
                input_type="text",
                textbook_id=request.textbook_id,
                page_number=request.page_number,
                history=request.history,
                teaching_mode=teaching_mode,
                socratic_submode=getattr(request, "socratic_submode", "unclassified") or "unclassified",
                token=request.token,
            )
            async for event in answer_turn(qa_input):
                yield event

        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(_generate_with_heartbeat(generate()))



