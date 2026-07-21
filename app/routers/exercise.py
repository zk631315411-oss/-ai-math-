"""智能出题 + 批改 + 错因分析 API。

POST  /api/exercise/generate      — LLM 流式出题（按当前页）
GET   /api/exercise/list          — 历史记录
POST  /api/exercise/{id}/submit   — 提交答案（同步批改 + 异步错因）
POST  /api/exercise/{id}/hint     — 渐进提示
POST  /api/exercise/{id}/report-error — 用户纠错
"""

import json
import asyncio

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse

from app.models.schemas import (
    ExerciseGenerateRequest, ExerciseSubmitRequest,
    ExerciseSubmitResponse, ExerciseHintResponse,
)
from app.db.exercise_bank_db import (
    save_exercise, get_exercise, list_exercises, submit_answer,
    record_result, update_hint_level, report_error,
)
from app.db.knowledge_stages_db import get_user_avg_stage
from app.services.exercise_generator import (
    build_exercise_prompt, parse_markdown_sections, get_stage_config,
)

router = APIRouter(prefix="/api/exercise", tags=["exercise"])


@router.post("/generate")
async def generate_exercise(request: ExerciseGenerateRequest):
    """LLM 流式出题：根据当前教材页上下文生成，验算通过才入库。"""
    from app.services.llm_service import llm_service
    from app.db.textbook_section_db import get_page_context
    from app.db.whitelist_db import get_whitelist

    user_id = request.user_id

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
            yield f"data: {json.dumps({'status': 'generating', 'text': '正在生成题目...'})}\n\n"

            stream = llm_service.stream_chat(messages, enable_thinking=False)
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    text = chunk.choices[0].delta.content
                else:
                    continue
                if text:
                    full_text += text
                    yield f"data: {json.dumps({'content': text})}\n\n"

            # 阶段2：解析
            yield f"data: {json.dumps({'status': 'parsing', 'text': '正在解析题目...'})}\n\n"

            parsed = parse_markdown_sections(full_text)
            if not parsed:
                yield f"data: {json.dumps({'error': '题目生成失败：解析结果不完整，缺少题目或答案'})}\n\n"
                return

            computable = parsed.get("computable", {})

            # 阶段3：验算
            quality = 0
            if computable and computable.get("type"):
                yield f"data: {json.dumps({'status': 'verifying', 'text': '正在验算答案...'})}\n\n"

                from app.services.sympy_sandbox import verify_computable
                comp_type = computable.get("type", "")
                comp_expected = computable.get("expected", [])
                v_result = verify_computable(comp_type, computable, comp_expected)
                if not v_result.get("success"):
                    quality = -1
                    verify_err = v_result.get('error', '未知错误')
                    yield f"data: {json.dumps({'error': f'验算失败：{verify_err}'})}\n\n"
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

            yield f"data: {json.dumps({'done': True, 'exercise_id': eid})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@router.get("/by-page")
async def exercises_by_page(page_number: int, user_id: str, textbook_id: str = "高代上-丘维声"):
    """按当前页取教材练习题（秒出，无 LLM）。"""
    from app.db.textbook_section_db import get_page_context
    from app.db.exercise_bank_db import list_by_sequence_id

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

    return {"exercises": exercises, "chapter_name": ctx.get("chapter_name", "") if ctx else ""}


@router.get("/list")
async def list_user_exercises(user_id: str, topic: str = "", limit: int = 20):
    return {"exercises": list_exercises(user_id, topic, limit)}


@router.post("/{exercise_id}/submit")
async def submit_exercise_answer(
    exercise_id: str, request: ExerciseSubmitRequest, background_tasks: BackgroundTasks
):
    ex = get_exercise(exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")

    # 原子 CAS 防重
    affected = submit_answer(exercise_id, request.student_answer)
    if affected == 0:
        return ExerciseSubmitResponse(
            is_correct=ex.get("is_correct") or False,
            grading_feedback="该题已提交过答案",
            already_submitted=True,
            error_analysis=ex.get("error_analysis"),
        )

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
    except Exception:
        grading_valid = False
        grading = {"is_correct": False, "grading_feedback": "批改异常，请重试"}

    is_correct = grading.get("is_correct", False)
    record_result(exercise_id, is_correct)

    from app.config import config
    from app.db.diagnosis_v2_db import save_exercise_attempt

    attempt_id = save_exercise_attempt(
        exercise=ex,
        student_answer=request.student_answer,
        is_correct=is_correct,
        grading_feedback=grading.get("grading_feedback", ""),
        grader_version=config.PROFILE_LLM_MODEL,
        grading_valid=grading_valid,
    )

    # 异步：错因分析（BackgroundTasks）
    if not is_correct and grading_valid:
        background_tasks.add_task(
            _async_error_analysis,
            exercise_id, attempt_id, ex, request.student_answer, ex["user_id"],
        )

    return ExerciseSubmitResponse(
        is_correct=is_correct,
        grading_feedback=grading.get("grading_feedback", ""),
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
        record_result(exercise_id, ex.get("is_correct") or False, result)
    from app.db.diagnosis_v2_db import update_exercise_attempt_error

    update_exercise_attempt_error(attempt_id, result)


@router.post("/{exercise_id}/hint")
async def request_hint(exercise_id: str):
    ex = get_exercise(exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")

    new_level = update_hint_level(exercise_id)
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
async def report_exercise_error(exercise_id: str):
    ex = get_exercise(exercise_id)
    if not ex:
        raise HTTPException(404, "Exercise not found")
    report_error(exercise_id)
    return {"status": "reported"}
