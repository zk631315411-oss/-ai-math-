from fastapi import APIRouter, Header, HTTPException
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
from app.models.schemas import QARequest
from app.auth.jwt_handler import decode_token
from app.db.user_profile_db import get_user_profile
from app.services.qa import QATurnInput, answer_turn, has_screenshot_context
from app.services.qa.streaming_service import sse_event
from app.db.chat_tree_db import begin_turn, finish_turn, get_authorized_context, TreeError
from app.services.agents.qa_agent import QAAgent

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

    producer_task = asyncio.create_task(producer())

    try:
        while True:
            event = await events.get()
            if event is None:
                break
            yield event
    finally:
        task.cancel()
        producer_task.cancel()
        await asyncio.gather(task, producer_task, return_exceptions=True)


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


def _authenticated_tree_user(request: QARequest, authorization: str | None) -> tuple[str, str]:
    """Authenticate a tree-backed QA turn and return ``(user_id, token)``."""
    if not authorization:
        raise HTTPException(status_code=401, detail="树对话缺少认证令牌")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="树对话认证令牌格式无效")
    try:
        user_id = decode_token(parts[1]).get("user_id")
    except Exception as exc:
        raise HTTPException(status_code=401, detail="树对话认证令牌无效") from exc
    if not user_id:
        raise HTTPException(status_code=401, detail="树对话认证令牌缺少用户信息")
    if request.user_id and request.user_id != user_id:
        raise HTTPException(status_code=403, detail="不能为其他用户创建树对话")
    return user_id, parts[1]


def _authorized_history(request: QARequest, user_id: str):
    """Construct history from the server-owned node path, never client history."""
    if not request.node_id:
        return request.history
    messages = get_authorized_context(
        request.node_id,
        user_id,
        request.referenced_node_ids,
        request.fork_message_id,
    )
    reference_ids = set(request.referenced_node_ids)

    def pair_turns(items, assistant_only_label=""):
        result = []
        pending_user = None
        for message in items:
            if message["role"] == "user":
                if pending_user is not None:
                    result.append({"user": pending_user, "assistant": ""})
                pending_user = message["content"]
            elif message["role"] == "assistant":
                if pending_user is not None:
                    result.append({"user": pending_user, "assistant": message["content"]})
                    pending_user = None
                elif assistant_only_label:
                    result.append({"user": assistant_only_label, "assistant": message["content"]})
        if pending_user is not None:
            result.append({"user": pending_user, "assistant": ""})
        return result

    path_messages = [message for message in messages if message["node_id"] not in reference_ids]
    pairs = pair_turns(path_messages)
    # The UI persists the new user message before opening the SSE stream.  It
    # is the current turn, not prior context, so do not present it twice.
    if pairs and pairs[-1]["user"] == request.question and pairs[-1]["assistant"] == "":
        pairs.pop()
    for reference_id in request.referenced_node_ids:
        reference_messages = [message for message in messages if message["node_id"] == reference_id]
        pairs.extend(pair_turns(reference_messages, assistant_only_label="[用户显式引用的其他分支回答]"))
    return pairs


def _event_payload(event: dict) -> dict:
    try:
        return json.loads(event.get("data") or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}


@router.post("/solve-stream")
async def solve_question_stream(request: QARequest, authorization: str | None = Header(None)):
    """
    题目答疑接口 - 流式输出 (SSE)
    """
    tree_requested = bool(
        request.client_turn_id or request.node_id or request.tree_id or request.fork_message_id
    )
    tree_auth = None
    if tree_requested:
        if not request.client_turn_id or not request.node_id:
            raise HTTPException(status_code=422, detail="树对话缺少 client_turn_id 或 node_id")
        tree_auth = _authenticated_tree_user(request, authorization)

    async def generate():
        tree_turn = None
        tree_turn_finished = False
        collected_answer = ""
        user_id = ""
        try:
            question = request.question or "请分析这道题"
            teaching_mode = getattr(request, 'teaching_mode', 'socratic') or 'socratic'
            if tree_requested:
                user_id, auth_token = tree_auth
            else:
                user_id, _ = get_user_id_and_profile(request)
                auth_token = request.token
            marker_id = request.marker_id or request.page_id or request.chat_id
            authorized_history = _authorized_history(request, user_id)

            if tree_requested:
                tree_turn = begin_turn(
                    request.node_id,
                    user_id,
                    question,
                    turn_id=request.client_turn_id,
                    fork_message_id=request.fork_message_id,
                    expected_revision=request.expected_node_revision,
                    expected_tree_id=request.tree_id,
                )
                yield sse_event("tree_turn_started", tree_turn)
                if not tree_turn["created"]:
                    persisted = tree_turn["assistant_message"]
                    if persisted["status"] == "completed":
                        collected_answer = persisted["content"]
                        if collected_answer:
                            yield sse_event("content", {"text": collected_answer})
                        yield sse_event(
                            "done",
                            {"full_text": collected_answer, "sources": [], "tree_turn": tree_turn},
                        )
                    else:
                        yield sse_event(
                            "error",
                            {"error": f"该回合已处于 {persisted['status']} 状态，请重新发送"},
                        )
                    tree_turn_finished = True
                    return

            effective_tree_id = tree_turn["tree_id"] if tree_turn else request.tree_id
            effective_node_id = tree_turn["node_id"] if tree_turn else request.node_id

            visual_input = QATurnInput(
                user_id=user_id or "anonymous",
                chat_id=getattr(request, "chat_id", None),
                marker_id=marker_id,
                question=question or "请分析这道题",
                input_type="mixed" if question else "image",
                textbook_id=request.textbook_id,
                page_number=request.page_number,
                history=authorized_history,
                teaching_mode=teaching_mode,
                socratic_submode=getattr(request, "socratic_submode", "unclassified") or "unclassified",
                image_data=request.image_data,
                crop_bbox=request.crop_bbox,
                screenshot_context_id=request.screenshot_context_id,
                token=auth_token,
                tree_id=effective_tree_id,
                node_id=effective_node_id,
                fork_message_id=request.fork_message_id,
                referenced_node_ids=request.referenced_node_ids,
                auto_prepare_practice=request.auto_prepare_practice,
                client_turn_id=request.client_turn_id,
            )
            if not has_screenshot_context(visual_input):
                qa_input = QATurnInput(
                    user_id=user_id or "anonymous",
                    chat_id=getattr(request, "chat_id", None),
                    marker_id=marker_id,
                    question=question,
                    input_type="text",
                    textbook_id=request.textbook_id,
                    page_number=request.page_number,
                    history=authorized_history,
                    teaching_mode=teaching_mode,
                    socratic_submode=getattr(request, "socratic_submode", "unclassified") or "unclassified",
                    token=auth_token,
                    tree_id=effective_tree_id,
                    node_id=effective_node_id,
                    fork_message_id=request.fork_message_id,
                    referenced_node_ids=request.referenced_node_ids,
                    auto_prepare_practice=request.auto_prepare_practice,
                    client_turn_id=request.client_turn_id,
                )
                visual_input = qa_input
            turn_stream = QAAgent().run(visual_input)

            async for event in turn_stream:
                event_type = event.get("event")
                payload = _event_payload(event)
                if event_type == "content":
                    collected_answer += str(payload.get("text") or "")
                elif event_type == "done" and tree_turn:
                    collected_answer = str(payload.get("full_text") or collected_answer)
                    tree_turn = finish_turn(
                        request.client_turn_id, user_id, collected_answer, "completed"
                    )
                    tree_turn_finished = True
                    event = sse_event("done", {**payload, "tree_turn": tree_turn})
                elif event_type == "error" and tree_turn:
                    tree_turn = finish_turn(
                        request.client_turn_id, user_id, collected_answer, "failed"
                    )
                    tree_turn_finished = True
                yield event

            if tree_turn and not tree_turn_finished:
                finish_turn(request.client_turn_id, user_id, collected_answer, "interrupted")
                tree_turn_finished = True

        except asyncio.CancelledError:
            if tree_turn and not tree_turn_finished:
                try:
                    finish_turn(request.client_turn_id, user_id, collected_answer, "interrupted")
                except Exception:
                    pass
            raise
        except Exception as e:
            if tree_turn and not tree_turn_finished:
                try:
                    finish_turn(request.client_turn_id, user_id, collected_answer, "failed")
                except Exception:
                    pass
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(_generate_with_heartbeat(generate()))



