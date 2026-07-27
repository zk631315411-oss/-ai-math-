"""智能出题 + 批改 + 错因分析 API。

POST  /api/exercise/generate      — LLM 流式出题（按当前页）
GET   /api/exercise/list          — 历史记录
POST  /api/exercise/{id}/submit   — 提交答案（同步批改 + 异步错因）
POST  /api/exercise/{id}/hint     — 渐进提示
POST  /api/exercise/{id}/report-error — 用户纠错
"""

import json
import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.services.qa.streaming_service import sse_format
from app.models.schemas import (
    ExerciseGenerateRequest, ExerciseSubmitRequest,
    ExerciseSubmitResponse, ExerciseHintResponse,
)
from app.db.exercise_bank_db import (
    attach_user_states, get_exercise, get_user_exercise_state,
    increment_user_hint_level, list_user_exercises, report_user_exercise_error,
    save_exercise, save_user_error_analysis, save_user_exercise_result,
)
from app.db.knowledge_stages_db import get_user_avg_stage
from app.services.exercise_generator import (
    build_exercise_prompt, parse_markdown_sections, get_stage_config,
)

router = APIRouter(prefix="/api/exercise", tags=["exercise"])


def _require_user_id(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    try:
        from app.auth.jwt_handler import decode_token

        user_id = decode_token(parts[1]).get("user_id")
    except Exception:
        user_id = None
    if not user_id:
        raise HTTPException(status_code=401, detail="未登录或 token 无效")
    return user_id


def _validated_user_id(authorization: Optional[str], requested_user_id: str = "") -> str:
    user_id = _require_user_id(authorization)
    if requested_user_id and requested_user_id != user_id:
        raise HTTPException(status_code=403, detail="不能访问其他用户的练习数据")
    return user_id


@router.post("/generate")
async def generate_exercise(
    request: ExerciseGenerateRequest,
    authorization: Optional[str] = Header(None),
):
    """LLM 流式出题：根据当前教材页上下文生成，验算通过才入库。"""
    from app.services.llm_service import llm_service
    from app.db.textbook_section_db import get_page_context
    from app.db.whitelist_db import get_whitelist

    user_id = _validated_user_id(authorization, request.user_id)

    # 1. 获取页面上下文
    chapter_name = request.topic or ""
    page_summary = ""
    sequence_id = ""
    textbook_id = request.textbook_id or "高代上-丘维声"

    if request.page_number:
        try:
            ctx = get_page_context(textbook_id, request.page_number)
            if ctx and "error" not in ctx:
                chapter_name = ctx.get("chapter_name", "") or chapter_name
                page_summary = ctx.get("content", "")[:500]
                sequence_id = ctx.get("sequence_id", "")
        except Exception:
            pass

    # 2. 获取 stage（全局平均兜底）
    stage = get_user_avg_stage(user_id)

    # 3. 获取白名单（按真实 sequence_id）
    whitelist_micro = chapter_name
    if sequence_id:
        try:
            wl = get_whitelist(textbook_id, sequence_id)
            if isinstance(wl, dict):
                whitelist_micro = wl.get("micro", chapter_name)
        except Exception:
            pass

    # 4. 构建 Prompt 并调用 LLM
    prompt = build_exercise_prompt(
        chapter_name=chapter_name,
        page_summary=page_summary,
        whitelist_micro=whitelist_micro,
        stage=stage,
        topic=chapter_name,
    )
    messages = [
        {"role": "system", "content": "你是一位数学出题专家。严格按指定 Markdown 格式输出。"},
        {"role": "user", "content": prompt},
    ]

    cfg = get_stage_config(stage)

    async def stream():
        buffer = ""
        full_text = ""
        try:
            # 阶段1：正在生成
            yield sse_format("stage", {"stage": "generating", "text": "正在生成题目..."})

            stream = llm_service.stream_chat(messages, enable_thinking=False)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                else:
                    continue
                if text:
                    full_text += text
                    yield sse_format("content", {"text": text})

            # 阶段2：解析
            yield sse_format("stage", {"stage": "parsing", "text": "正在解析题目..."})

            parsed = parse_markdown_sections(full_text)
            if not parsed:
                yield sse_format("error", {"error": "题目生成失败：解析结果不完整，缺少题目或答案"})
                return

            computable = parsed.get("computable", {})

            # 阶段3：验算
            quality = 0
            if computable and computable.get("type"):
                yield sse_format("stage", {"stage": "verifying", "text": "正在验算答案..."})

                from app.services.sympy_sandbox import verify_computable
                comp_type = computable.get("type", "")
                comp_expected = computable.get("expected", [])
                v_result = verify_computable(comp_type, computable, comp_expected)
                if not v_result.get("success"):
                    quality = -1
                    verify_err = v_result.get('error', '未知错误')
                    yield sse_format("error", {"error": f"验算失败：{verify_err}"})
                    # 不入库，直接返回
                    return

            # 阶段4：入库
            eid = save_exercise(
                user_id=user_id, topic=chapter_name or request.topic or "",
                difficulty=cfg["difficulty"],
                target_stage=cfg["target_stage"],
                question=parsed["question"],
                answer=parsed["answer"],
                verification=parsed.get("verification", ""),
                hints=parsed.get("hints", []),
                computable=computable,
                sequence_id=sequence_id,
            )

            yield sse_format("done", {"done": True, "exercise_id": eid})

        except Exception as e:
            yield sse_format("error", {"error": str(e)})

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/by-page")
async def exercises_by_page(
    page_number: int,
    user_id: str,
    textbook_id: str = "高代上-丘维声",
    authorization: Optional[str] = Header(None),
):
    """按当前页取教材练习题（秒出，无 LLM）。"""
    from app.db.textbook_section_db import get_page_context
    from app.db.exercise_bank_db import list_by_sequence_id

    authenticated_user_id = _validated_user_id(authorization, user_id)
    ctx = get_page_context(textbook_id, page_number)
    if textbook_id.startswith("高数"):
        return {"exercises": [], "chapter_name": ctx.get("chapter_name", "") if ctx and "error" not in ctx else ""}

    sequence_id = ""
    if ctx and "error" not in ctx:
        sequence_id = ctx.get("sequence_id", "")

    if not sequence_id:
        return {"exercises": [], "chapter_name": ""}

    # 教材题不按 stage 过滤——教材本身未按难度分层，全取
    exercises = list_by_sequence_id(sequence_id, max_stage=5, limit=5)

    # 当前节完全没题 → 回退附近节
    if not exercises and sequence_id:
        prefix = "-".join(sequence_id.split("-")[:2])
        exercises = list_by_sequence_id(prefix, max_stage=5, limit=3)
        if not exercises:
            exercises = list_by_sequence_id(sequence_id.split("-S")[0], max_stage=5, limit=3)

    return {
        "exercises": attach_user_states(exercises, authenticated_user_id),
        "chapter_name": ctx.get("chapter_name", "") if ctx else "",
    }


@router.get("/list")
async def list_user_exercise_history(
    user_id: str,
    topic: str = "",
    limit: int = 20,
    authorization: Optional[str] = Header(None),
):
    authenticated_user_id = _validated_user_id(authorization, user_id)
    return {"exercises": list_user_exercises(authenticated_user_id, topic, limit)}


@router.post("/{exercise_id}/submit")
async def submit_exercise_answer(
    exercise_id: str,
    request: ExerciseSubmitRequest,
    background_tasks: BackgroundTasks,
    authorization: Optional[str] = Header(None),
):
    user_id = _require_user_id(authorization)
    ex = get_exercise(exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")

    # 同步：LLM 批改
    from app.services.llm_service import llm_service

    grading_prompt = f"""你是一位数学批改老师。对比标准答案和学生作答，判断对错并给反馈。

## 题目
{ex['question']}

## 标准答案
{ex['answer']}

## 学生作答
{request.student_answer}

## 输出 JSON
{{"is_correct": true/false, "grading_feedback": "反馈（50字内，对的鼓励，错的指出问题）"}}
"""

    grading_messages = [
        {"role": "system", "content": "只输出 JSON。"},
        {"role": "user", "content": grading_prompt},
    ]

    grading_valid = True
    try:
        grading_raw = await llm_service.chat_async(grading_messages, temperature=0.3)
        import re
        m = re.search(r"\{.*\}", grading_raw, re.DOTALL)
        if not m:
            raise ValueError("批改模型未返回 JSON")
        grading = json.loads(m.group())
        if not isinstance(grading.get("is_correct"), bool):
            raise ValueError("批改结果缺少布尔 is_correct")
    except Exception as exc:
        print(f"[exercise] grading failed for {exercise_id}: {exc}")
        grading_valid = False
        grading = {"is_correct": False, "grading_feedback": "批改异常，请重试"}

    is_correct = grading.get("is_correct", False) if grading_valid else None

    from app.config import config
    from app.db.diagnosis_v2_db import save_exercise_attempt

    state = get_user_exercise_state(user_id, exercise_id) or {}

    attempt_id = save_exercise_attempt(
        exercise=ex,
        student_answer=request.student_answer,
        is_correct=bool(is_correct),
        grading_feedback=grading.get("grading_feedback", ""),
        grader_version=config.PROFILE_LLM_MODEL,
        grading_valid=grading_valid,
        user_id=user_id,
        hint_level=int(state.get("hint_level") or 0),
    )
    grading_status = "completed" if grading_valid else "failed"
    save_user_exercise_result(
        user_id=user_id,
        exercise_id=exercise_id,
        student_answer=request.student_answer,
        is_correct=is_correct,
        grading_feedback=grading.get("grading_feedback", ""),
        grading_status=grading_status,
        attempt_id=attempt_id,
    )

    # 异步：错因分析（BackgroundTasks）
    if is_correct is False and grading_valid:
        background_tasks.add_task(
            _async_error_analysis,
            exercise_id, attempt_id, ex, request.student_answer, user_id,
        )

    return ExerciseSubmitResponse(
        is_correct=bool(is_correct),
        grading_feedback=grading.get("grading_feedback", ""),
        grading_status=grading_status,
    )


async def _async_error_analysis(
    exercise_id: str,
    attempt_id: str,
    ex: dict,
    student_answer: str,
    user_id: str,
):
    """BackgroundTasks 异步执行错因分析；Stage 只由 V2 投影器更新。"""
    from app.services.error_analyzer import analyze_error
    from app.db.math_profile_db import get_math_profile

    # 取真实 weak_points
    weak_points = []
    try:
        mp = get_math_profile(user_id)
        if mp:
            wps = mp.get("weak_points", [])
            if isinstance(wps, str):
                wps = json.loads(wps)
            weak_points = wps if isinstance(wps, list) else []
    except Exception:
        pass

    result = await analyze_error(
        question=ex["question"],
        correct_answer=ex["answer"],
        student_answer=student_answer,
        stage=ex.get("target_stage"),
        weak_points=weak_points,
    )
    if result:
        save_user_error_analysis(user_id, exercise_id, result)
    from app.db.diagnosis_v2_db import update_exercise_attempt_error

    update_exercise_attempt_error(attempt_id, result)


@router.post("/{exercise_id}/hint")
async def request_hint(
    exercise_id: str,
    authorization: Optional[str] = Header(None),
):
    user_id = _require_user_id(authorization)
    ex = get_exercise(exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")

    new_level = increment_user_hint_level(user_id, exercise_id)
    hints = ex.get("hints", [])
    if new_level > 1 and new_level <= len(hints):
        hint_text = hints[new_level - 1]
    elif new_level == 1 and hints:
        hint_text = hints[0]
    else:
        hint_text = hints[-1] if hints else "暂无更多提示"

    return ExerciseHintResponse(
        hint=hint_text,
        hint_level=new_level,
        exhausted=new_level >= 3,
    )


@router.post("/{exercise_id}/report-error")
async def report_exercise_error(
    exercise_id: str,
    authorization: Optional[str] = Header(None),
):
    user_id = _require_user_id(authorization)
    ex = get_exercise(exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")
    created = report_user_exercise_error(user_id, exercise_id)
    return {"status": "reported", "already_reported": not created}
