"""最小 QA 回答编排入口。"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass, replace
import asyncio
import re
import time
import uuid
from typing import AsyncIterator

from fastapi.concurrency import run_in_threadpool

from app.config import config
from app.services.llm_service import llm_service
from app.services.qa.contracts import QATurnInput, QATurnRecord
from app.services.qa.event_bus import StreamBus
from app.services.qa.grounding_service import ground_text_turn
from app.services.qa.prompt_builder import build_tutor_prompt
from app.services.qa.streaming_service import sse_done, sse_error, sse_event, sse_stage, sse_text
from app.services.qa.turn_store import save_turn_record, start_persist_consumer
from app.services.qa.tutor_policy import decide_tutor_policy
from app.services.qa.vision_context_service import (
    build_screenshot_locator_prompt,
    prepare_screenshot_context,
)
from app.services.diagnosis.contracts import KGContext, StudentStateSummary, WeakPrerequisite


async def answer_turn(
    turn_input: QATurnInput,
    *,
    student_state_summary: StudentStateSummary | dict | None = None,
) -> AsyncIterator[dict]:
    """统一 QA 入口。

    student_state_summary 是给后续认知诊断模块接入的只读提示信号。
    QA 模块只能用它调整回答风格，不能在这里更新 stage 或触发诊断。
    """

    if turn_input.input_type == "text":
        async for event in _answer_text_turn(turn_input, student_state_summary=student_state_summary):
            yield event
        return

    async for event in _answer_vision_turn(turn_input):
        yield event


async def _answer_text_turn(
    turn_input: QATurnInput,
    *,
    student_state_summary: StudentStateSummary | dict | None = None,
) -> AsyncIterator[dict]:
    if not turn_input.question:
        yield sse_error("未能识别题目内容")
        return

    turn_id = str(uuid.uuid4())
    started_at = time.perf_counter()
    full_response = ""
    record: QATurnRecord | None = None
    apprenticeship_level: str | None = None  # 异常时兜底默认值

    try:
        yield sse_stage("searching", "正在匹配教材与知识图谱...")
        grounding = ground_text_turn(
            turn_input.textbook_id or "",
            turn_input.page_number,
            turn_input.question,
        )
        kg_concepts = [node.name for node in grounding.related_concepts if node.name]
        sources = _build_sources(grounding, kg_concepts)

        yield sse_stage("planning", "正在组织本轮讲解策略...")
        student_state = _coerce_student_state(turn_input.user_id, student_state_summary)
        policy = decide_tutor_policy(
            student_state,
            turn_input.teaching_mode,
            turn_input.socratic_submode,
        )
        # 计算脚手架层级，供 QATurnRecord 持久化
        from app.services.scaffolding_controller import scaffolding_controller
        apprenticeship_level = scaffolding_controller.determine_level(
            student_state.current_section_stage, turn_input.socratic_submode,
        ).value
        prompt = build_tutor_prompt(
            turn_input.question,
            grounding,
            student_state,
            policy,
            history=turn_input.history,
        )
        messages = [{"role": "user", "content": prompt}]

        yield sse_stage("generating", "正在生成回答...")
        stream = llm_service.stream_chat(messages, enable_thinking=False)

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta or not delta.content:
                continue
            token = delta.content
            full_response += token
            yield sse_text(token)

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        record = QATurnRecord(
            turn_id=turn_id,
            user_id=turn_input.user_id,
            chat_id=turn_input.chat_id,
            input_type="text",
            question=turn_input.question,
            marker_id=turn_input.marker_id or turn_input.chat_id,
            apprenticeship_level=apprenticeship_level,
            answer=full_response,
            textbook_id=grounding.textbook_id,
            page_number=grounding.page_number,
            sequence_id=grounding.sequence_id,
            section_node_id=grounding.section_node_id,
            chapter_name=grounding.chapter_name,
            sources=sources,
            context_snapshot={
                "input_context": {
                    "marker_id": turn_input.marker_id or turn_input.chat_id,
                    "chat_id": turn_input.chat_id,
                    "page_number": turn_input.page_number,
                    "tree_id": turn_input.tree_id,
                    "node_id": turn_input.node_id,
                    "fork_message_id": turn_input.fork_message_id,
                    "referenced_node_ids": turn_input.referenced_node_ids,
                },
                "grounding": {
                    "textbook_id": grounding.textbook_id,
                    "page_number": grounding.page_number,
                    "sequence_id": grounding.sequence_id,
                    "section_node_id": grounding.section_node_id,
                    "chapter_name": grounding.chapter_name,
                    "content_excerpt": grounding.content_excerpt,
                    "related_concepts": [node.__dict__ for node in grounding.related_concepts],
                    "prerequisite_concepts": [node.__dict__ for node in grounding.prerequisite_concepts],
                    "rule_cases": [case.__dict__ for case in grounding.rule_cases],
                    "evidence_spans": [span.__dict__ for span in grounding.evidence_spans],
                    "kg_context": _snapshot_value(grounding.kg_context),
                    "confidence": grounding.confidence,
                },
                "student_state_summary": getattr(student_state, "__dict__", student_state),
                "tutor_policy": getattr(policy, "__dict__", policy),
                "history": turn_input.history or [],
            },
            messages_snapshot=messages,
            prompt_preview=prompt[:2000],
            model_name=config.QA_LLM_MODEL,
            latency_ms=latency_ms,
        )
        # 持久化改为异步，不阻塞 SSE 响应
        persist_done = asyncio.Event()
        bus = StreamBus()
        asyncio.create_task(start_persist_consumer(bus, record, persist_done))
        # 注册实时诊断消费者（延迟 import 避免循环依赖）
        from app.services.diagnostic_worker import listen_qa_done
        asyncio.create_task(listen_qa_done(bus, turn_input.user_id, persist_done))
        # 让出控制权，确保消费者 task 先调度再 emit 事件
        await asyncio.sleep(0)
        bus.emit({"type": "done"})
        bus.close()

        yield sse_done(
            full_text=full_response,
            thinking="",
            sources=sources,
            sequence_id=grounding.sequence_id,
            qa_turn_id=turn_id,
        )

    except Exception as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if record is None:
            record = QATurnRecord(
                turn_id=turn_id,
                user_id=turn_input.user_id,
                chat_id=turn_input.chat_id,
                input_type="text",
                question=turn_input.question,
                marker_id=turn_input.marker_id or turn_input.chat_id,
                apprenticeship_level=apprenticeship_level,
                answer=full_response,
                textbook_id=turn_input.textbook_id,
                page_number=turn_input.page_number,
                model_name=config.QA_LLM_MODEL,
                latency_ms=latency_ms,
                error=str(exc),
            )
            save_turn_record(record, write_chat_log=False)
        yield sse_error(str(exc))


def _coerce_student_state(
    user_id: str,
    student_state_summary: StudentStateSummary | dict | None,
) -> StudentStateSummary:
    if isinstance(student_state_summary, StudentStateSummary):
        return student_state_summary
    if isinstance(student_state_summary, dict):
        allowed = StudentStateSummary.__dataclass_fields__.keys()
        values = {key: value for key, value in student_state_summary.items() if key in allowed}
        values.setdefault("user_id", user_id)
        values["weak_prerequisites"] = [
            _coerce_weak_prerequisite(item)
            for item in values.get("weak_prerequisites", []) or []
        ]
        return StudentStateSummary(**values)
    return StudentStateSummary(user_id=user_id)


def _coerce_weak_prerequisite(value) -> WeakPrerequisite:
    if isinstance(value, WeakPrerequisite):
        return value
    if isinstance(value, dict):
        allowed = WeakPrerequisite.__dataclass_fields__.keys()
        values = {key: item for key, item in value.items() if key in allowed}
        values.setdefault("name", "")
        values.setdefault("stage", None)
        return WeakPrerequisite(**values)
    return WeakPrerequisite(name=str(value), stage=None)


async def _answer_vision_turn(turn_input: QATurnInput) -> AsyncIterator[dict]:
    """Extract a trustworthy problem first, then hand it to the shared ToolRuntime."""
    from app.db.screenshot_context_cache_db import (
        get_screenshot_context_cache,
        update_screenshot_context_cache,
    )
    from app.services.qa.vision_extraction import (
        VISION_EXTRACTION_VERSION,
        VisionExtraction,
        extract_vision_problem,
        format_extracted_question,
    )

    try:
        textbook_id, page_context, _sequence_id, _whitelist, _profile = await _load_vision_page_context(turn_input)
        yield sse_stage("reading_pdf", "正在读取 PDF 原图区域...")
        screenshot_context = await run_in_threadpool(
            prepare_screenshot_context, turn_input, textbook_id, page_context,
        )
        image_for_model = (screenshot_context.get("pdf_crop") or {}).get("data_url") or turn_input.image_data
        if not image_for_model:
            raise RuntimeError("未能获取截图图像")
        locator_prompt = build_screenshot_locator_prompt(
            screenshot_context["locator_result"], screenshot_context["reused_cache"],
        )
        cached = await run_in_threadpool(
            get_screenshot_context_cache, screenshot_context["cache_id"], turn_input.user_id,
        )
        extraction = None
        if cached and cached.get("vision_extraction") \
                and cached.get("extraction_version") == VISION_EXTRACTION_VERSION \
                and cached.get("vision_model") == config.QA_VL_MODEL:
            try:
                import json
                extraction = VisionExtraction.model_validate(json.loads(cached["vision_extraction"]))
            except Exception:
                extraction = None
        if extraction is None:
            yield sse_stage("recognizing", "正在识别题目与公式...")
            extraction = await extract_vision_problem(
                image_for_model, locator_prompt, turn_input.question,
            )
            await run_in_threadpool(
                update_screenshot_context_cache,
                screenshot_context["cache_id"],
                vision_extraction=extraction.model_dump(),
                extraction_version=VISION_EXTRACTION_VERSION,
                vision_model=config.QA_VL_MODEL,
            )
        if extraction.can_use_tools():
            extracted_input = replace(
                turn_input,
                question=format_extracted_question(extraction, turn_input.question),
                input_type="mixed",
                textbook_id=textbook_id,
                screenshot_context_id=screenshot_context["cache_id"],
            )
            async for event in answer_turn_with_tools(extracted_input):
                yield event
            return
        yield sse_stage("recognition_fallback", "题目细节识别不够可靠，正在直接结合图片回答...")
    except asyncio.CancelledError:
        raise
    except Exception:
        yield sse_stage("recognition_fallback", "结构化识别暂不可用，正在直接结合图片回答...")

    async for event in _answer_vision_direct(turn_input):
        yield event


async def _answer_vision_direct(turn_input: QATurnInput) -> AsyncIterator[dict]:
    turn_id = str(uuid.uuid4())
    started_at = time.perf_counter()
    full_answer = ""
    record: QATurnRecord | None = None
    student_state_payload: dict = {}  # 异常时兜底默认值

    try:
        textbook_id, page_context, sequence_id, whitelist, user_profile = await _load_vision_page_context(turn_input)
        grounding = ground_text_turn(textbook_id, turn_input.page_number, turn_input.question)
        section_node_id = grounding.section_node_id
        chapter_name = (
            page_context.get("chapter_name", "")
            if page_context and "error" not in page_context
            else grounding.chapter_name
        )

        yield sse_stage("reading_pdf", "正在读取 PDF 原图区域...")
        screenshot_context = await run_in_threadpool(
            prepare_screenshot_context,
            turn_input,
            textbook_id,
            page_context,
        )

        yield sse_stage("locating", "正在匹配教材上下文...")
        locator_prompt = build_screenshot_locator_prompt(
            screenshot_context["locator_result"],
            screenshot_context["reused_cache"],
        )
        prompt_question = f"{locator_prompt}\n\n学生问题：{turn_input.question or '请分析这道题'}"

        student_state_payload = await _load_vision_student_state(
            turn_input,
            textbook_id,
            page_context,
            sequence_id,
            user_profile,
        )
        prompt_text = _build_vision_prompt(
            turn_input=turn_input,
            prompt_question=prompt_question,
            page_context=page_context,
            whitelist=whitelist,
            user_profile=user_profile,
            student_state_payload=student_state_payload,
            kg_context=grounding.kg_context,
        )
        sources = _build_vision_sources(textbook_id, page_context, grounding)
        image_for_model = (screenshot_context.get("pdf_crop") or {}).get("data_url") or turn_input.image_data
        if not image_for_model:
            raise RuntimeError("未能获取截图图像，请重新截取教材区域后再试")

        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_for_model}},
                {"type": "text", "text": prompt_text},
            ],
        }]

        yield sse_stage("generating", "正在生成回答...")
        response = llm_service.vision_chat(image_for_model, prompt_text, stream=True)

        for chunk in response:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if not delta:
                continue
            content = getattr(delta, "content", "")
            for token in _iter_vision_text(content):
                full_answer += token
                yield sse_text(token)

        if screenshot_context.get("cache_id") and full_answer:
            await run_in_threadpool(
                _update_vision_summary,
                screenshot_context["cache_id"],
                full_answer[:4000],
            )

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        record = QATurnRecord(
            turn_id=turn_id,
            user_id=turn_input.user_id,
            chat_id=turn_input.chat_id,
            input_type=turn_input.input_type,
            question=turn_input.question or "请分析这道题",
            marker_id=turn_input.marker_id or turn_input.chat_id,
            apprenticeship_level=_apprenticeship_name(student_state_payload.get("apprenticeship_level")),
            answer=full_answer,
            textbook_id=textbook_id,
            page_number=turn_input.page_number,
            sequence_id=sequence_id,
            section_node_id=section_node_id,
            chapter_name=chapter_name,
            sources=sources,
            context_snapshot={
                "input_context": {
                    "marker_id": turn_input.marker_id or turn_input.chat_id,
                    "chat_id": turn_input.chat_id,
                    "page_number": turn_input.page_number,
                    "screenshot_context_id": turn_input.screenshot_context_id,
                    "tree_id": turn_input.tree_id,
                    "node_id": turn_input.node_id,
                    "fork_message_id": turn_input.fork_message_id,
                    "referenced_node_ids": turn_input.referenced_node_ids,
                },
                "page_context": _compact_page_context(page_context),
                "grounding": {
                    "textbook_id": grounding.textbook_id,
                    "page_number": grounding.page_number,
                    "sequence_id": grounding.sequence_id,
                    "section_node_id": grounding.section_node_id,
                    "chapter_name": grounding.chapter_name,
                    "content_excerpt": grounding.content_excerpt,
                    "related_concepts": [node.__dict__ for node in grounding.related_concepts],
                    "prerequisite_concepts": [node.__dict__ for node in grounding.prerequisite_concepts],
                    "rule_cases": [case.__dict__ for case in grounding.rule_cases],
                    "evidence_spans": [span.__dict__ for span in grounding.evidence_spans],
                    "kg_context": _snapshot_value(grounding.kg_context),
                    "confidence": grounding.confidence,
                },
                "screenshot_context": {
                    key: value
                    for key, value in screenshot_context.items()
                    if key != "pdf_crop"
                },
                "pdf_crop": {
                    "path": (screenshot_context.get("pdf_crop") or {}).get("path"),
                    "bbox": (screenshot_context.get("pdf_crop") or {}).get("bbox"),
                },
                "student_state_payload": student_state_payload,
                "history": turn_input.history or [],
            },
            messages_snapshot=messages,
            image_hash=screenshot_context.get("image_hash"),
            crop_bbox=screenshot_context.get("crop_bbox") or turn_input.crop_bbox,
            screenshot_context_id=screenshot_context.get("cache_id"),
            prompt_preview=prompt_text[:2000],
            model_name=config.QA_VL_MODEL,
            latency_ms=latency_ms,
        )
        # 持久化改为异步，不阻塞 SSE 响应
        persist_done = asyncio.Event()
        bus = StreamBus()
        asyncio.create_task(start_persist_consumer(bus, record, persist_done))
        # 注册实时诊断消费者（延迟 import 避免循环依赖）
        from app.services.diagnostic_worker import listen_qa_done
        asyncio.create_task(listen_qa_done(bus, turn_input.user_id, persist_done))
        # 让出控制权，确保消费者 task 先调度再 emit 事件
        await asyncio.sleep(0)
        bus.emit({"type": "done"})
        bus.close()

        yield sse_done(
            full_text=full_answer,
            thinking="",
            sources=sources,
            sequence_id=sequence_id,
            screenshot_context_id=screenshot_context.get("cache_id"),
            qa_turn_id=turn_id,
        )

    except Exception as exc:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        if record is None:
            record = QATurnRecord(
                turn_id=turn_id,
                user_id=turn_input.user_id,
                chat_id=turn_input.chat_id,
                input_type=turn_input.input_type,
                question=turn_input.question or "请分析这道题",
                marker_id=turn_input.marker_id or turn_input.chat_id,
                apprenticeship_level=_apprenticeship_name(student_state_payload.get("apprenticeship_level")),
                answer=full_answer,
                textbook_id=turn_input.textbook_id,
                page_number=turn_input.page_number,
                model_name=config.QA_VL_MODEL,
                latency_ms=latency_ms,
                error=str(exc),
            )
            save_turn_record(record, write_chat_log=False)
        yield sse_error(str(exc))


async def _load_vision_page_context(turn_input: QATurnInput) -> tuple[str, dict, str, dict, dict | None]:
    textbook_id = turn_input.textbook_id or "高代上-丘维声"
    sequence_id = "V1-C01-S01"
    page_context = {"error": "未提供页码，无法获取教材上下文"}
    whitelist = {"macro": "允许使用本教材涉及的所有概念和定理", "micro": ""}

    if turn_input.page_number:
        page_context, textbook_id = await _get_page_context_with_fallback(textbook_id, turn_input.page_number)
        if page_context and "error" not in page_context:
            sequence_id = page_context.get("sequence_id", sequence_id)
            whitelist = await run_in_threadpool(_safe_get_whitelist, textbook_id, sequence_id)

    user_profile = await run_in_threadpool(_safe_get_user_profile, turn_input.user_id)
    return textbook_id, page_context, sequence_id, whitelist, user_profile


async def _get_page_context_with_fallback(textbook_id: str, page_number: int) -> tuple[dict, str]:
    from app.db.textbook_section_db import get_page_context

    candidates = [textbook_id, "高代上-丘维声", "高代下-丘维声"]
    seen: set[str] = set()
    last_context: dict = {"error": "未提供页码，无法获取教材上下文"}
    last_textbook_id = textbook_id
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        context = await run_in_threadpool(get_page_context, candidate, page_number)
        last_context = context
        last_textbook_id = candidate
        if context and "error" not in context:
            return context, candidate
    return last_context, last_textbook_id


def _safe_get_whitelist(textbook_id: str, sequence_id: str) -> dict:
    try:
        from app.db.whitelist_db import get_whitelist

        return get_whitelist(textbook_id, sequence_id)
    except Exception:
        return {"macro": "允许使用本教材涉及的所有概念和定理", "micro": ""}


def _apprenticeship_name(value) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str):
        return enum_value
    if isinstance(value, str):
        return value.lower()
    return str(value).lower()


def _safe_get_user_profile(user_id: str) -> dict | None:
    try:
        from app.db.user_profile_db import get_user_profile

        return get_user_profile(user_id)
    except Exception:
        return None


async def _load_vision_student_state(
    turn_input: QATurnInput,
    textbook_id: str,
    page_context: dict,
    sequence_id: str,
    user_profile: dict | None,
) -> dict:
    try:
        from app.db.knowledge_stages_db import get_stage, get_user_avg_stage
        from app.services.prerequisite_checker import get_prereq_gaps
        from app.services.scaffolding_controller import scaffolding_controller

        prereq_gaps = await run_in_threadpool(
            get_prereq_gaps,
            sequence_id,
            turn_input.user_id,
            textbook_id,
        )
        chapter_name = page_context.get("chapter_name", "") if page_context and "error" not in page_context else ""
        student_stage = None
        if chapter_name and turn_input.user_id:
            student_stage = await run_in_threadpool(get_stage, turn_input.user_id, chapter_name)
            if student_stage is None:
                student_stage = await run_in_threadpool(get_user_avg_stage, turn_input.user_id)

        apprenticeship_level = scaffolding_controller.determine_level(student_stage, turn_input.socratic_submode)
        profile_avg = user_profile.get("overall_average", 1.5) if user_profile else 1.5
        student_level = scaffolding_controller.classify_student_level(profile_avg)
        return {
            "prereq_gaps": prereq_gaps,
            "student_stage": student_stage,
            "student_level": student_level,
            "apprenticeship_level": apprenticeship_level,
        }
    except Exception:
        return {
            "prereq_gaps": [],
            "student_stage": None,
            "student_level": None,
            "apprenticeship_level": None,
        }


def _build_vision_prompt(
    *,
    turn_input: QATurnInput,
    prompt_question: str,
    page_context: dict,
    whitelist: dict,
    user_profile: dict | None,
    student_state_payload: dict,
    kg_context: KGContext | dict | None = None,
) -> str:
    from app.services.qa.prompt_builder import build_vision_prompt

    return build_vision_prompt(
        question=prompt_question,
        page_context=page_context,
        whitelist=whitelist,
        profile=user_profile,
        teaching_mode=turn_input.teaching_mode,
        socratic_submode=turn_input.socratic_submode,
        history=turn_input.history,
        student_stage=student_state_payload.get("student_stage"),
        prereq_gaps=student_state_payload.get("prereq_gaps") or [],
        student_level=student_state_payload.get("student_level"),
        apprenticeship_level=student_state_payload.get("apprenticeship_level"),
        user_message_for_struggle=turn_input.question or "",
        kg_context=kg_context,
    )


def _build_vision_sources(textbook_id: str, page_context: dict, grounding) -> list[dict]:
    if page_context and "error" not in page_context:
        return [
            {
                "textbook_name": textbook_id,
                "chapter": page_context.get("chapter_name", ""),
                "snippet": page_context.get("content", "")[:500],
                "sequence_id": page_context.get("sequence_id") or grounding.sequence_id,
                "section_node_id": grounding.section_node_id,
                "kg_concepts": [node.name for node in grounding.related_concepts if node.name][:8],
                "kg_used": bool(grounding.related_concepts),
                **_kg_source_summary(grounding),
            }
        ]
    return []


def _iter_vision_text(content) -> list[str]:
    if isinstance(content, list):
        return [
            item["text"]
            for item in content
            if isinstance(item, dict) and item.get("text")
        ]
    if content:
        return [str(content)]
    return []


def _update_vision_summary(cache_id: str, summary: str) -> None:
    from app.db.screenshot_context_cache_db import update_screenshot_context_cache

    update_screenshot_context_cache(cache_id, vision_summary=summary)


def _compact_page_context(page_context: dict) -> dict:
    if not page_context:
        return {}
    return {
        "textbook_id": page_context.get("textbook_id"),
        "sequence_id": page_context.get("sequence_id"),
        "chapter_num": page_context.get("chapter_num"),
        "chapter_name": page_context.get("chapter_name"),
        "start_page": page_context.get("start_page"),
        "end_page": page_context.get("end_page"),
        "content_excerpt": (page_context.get("content") or "")[:4000],
        "error": page_context.get("error"),
    }


def _build_sources(grounding, kg_concepts: list[str]) -> list[dict]:
    if not grounding.content_excerpt:
        return []
    return [
        {
            "textbook_name": grounding.textbook_id,
            "chapter": grounding.chapter_name,
            "snippet": grounding.content_excerpt[:500],
            "sequence_id": grounding.sequence_id,
            "section_node_id": grounding.section_node_id,
            "kg_concepts": kg_concepts[:8],
            "kg_used": bool(kg_concepts),
            **_kg_source_summary(grounding),
        }
    ]


def _kg_source_summary(grounding) -> dict:
    kg_context = getattr(grounding, "kg_context", None)
    return {
        "kg_support_concepts": _node_names(_kg_items(kg_context, "support_nodes"), limit=6),
        "kg_lookahead_concepts": _node_names(_kg_items(kg_context, "lookahead_nodes"), limit=6),
        "kg_rule_cases_count": len(_kg_items(kg_context, "rule_cases")),
    }


def _kg_items(kg_context, field_name: str) -> list:
    if kg_context is None:
        return []
    if isinstance(kg_context, dict):
        return kg_context.get(field_name, []) or []
    return getattr(kg_context, field_name, []) or []


def _node_names(nodes: list, limit: int) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for node in nodes or []:
        name = str(_field(node, "name") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
        if len(names) >= limit:
            break
    return names


def _field(value, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _snapshot_value(value):
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    return value


async def answer_turn_with_tools(
    turn_input: QATurnInput,
    *,
    tools: list[dict] | None = None,
    tool_defs: list | None = None,
    max_tool_rounds: int | None = None,
) -> AsyncIterator[dict]:
    """Compatibility entry point backed exclusively by ToolRuntime."""
    from app.db.tool_trace_db import save_tool_trace
    from app.db.visualization_db import save_visualization
    from app.services.agents.tool_def import ToolDef
    from app.services.agents.tool_runtime import (
        ToolRuntime,
        ToolRuntimeConfig,
        ToolRuntimeContext,
    )
    from app.services.agents.tools import get_qa_tool_defs
    from app.services.qa.event_bus import StreamBus
    from app.services.qa.turn_store import start_persist_consumer

    del tools  # ToolDef is the canonical schema and execution registry.
    if not turn_input.question:
        yield sse_error("未能识别题目内容")
        return

    started_at = time.perf_counter()
    turn_id = turn_input.client_turn_id or str(uuid.uuid4())
    tool_def_list: list[ToolDef] = tool_defs or get_qa_tool_defs()
    full_response = ""
    runtime_result = None

    try:
        yield sse_stage("searching", "正在匹配教材与知识图谱...")
        grounding = ground_text_turn(
            turn_input.textbook_id or "", turn_input.page_number, turn_input.question,
        )
        kg_concepts = [node.name for node in grounding.related_concepts if node.name]
        sources = _build_sources(grounding, kg_concepts)

        yield sse_stage("planning", "正在组织本轮讲解策略...")
        student_state = _coerce_student_state(turn_input.user_id, None)
        policy = decide_tutor_policy(
            student_state, turn_input.teaching_mode, turn_input.socratic_submode,
        )
        from app.services.qa.prompt_builder import build_lightweight_prompt
        prompt = build_lightweight_prompt(
            turn_input.question, grounding, student_state, policy, history=turn_input.history,
        )
        prompt += (
            "\n\n当函数曲线、向量或二维线性变换能明显帮助理解时，请调用 "
            "create_math_visualization。每回合最多生成一个示意图；简单定义题不要为了装饰而画图。"
        )

        async def handle_artifact(artifact: dict, _outcome) -> dict:
            artifact = _ensure_requested_animation(artifact, turn_input.question)
            return await asyncio.to_thread(
                save_visualization,
                artifact,
                user_id=turn_input.user_id,
                turn_id=turn_id,
                chat_history_id=turn_input.chat_id or turn_input.marker_id,
            )

        async def handle_trace(payload: dict) -> None:
            context = payload["context"]
            outcome = payload["outcome"]
            await asyncio.to_thread(
                save_tool_trace,
                turn_id=context.turn_id,
                user_id=context.user_id,
                chat_history_id=context.chat_history_id,
                assistant_message_id=context.assistant_message_id,
                round_index=payload["round_index"],
                tool_call_id=outcome.tool_call_id,
                tool_name=outcome.tool_name,
                call_fingerprint=payload["fingerprint"],
                arguments=outcome.normalized_arguments,
                status=outcome.status,
                error_code=outcome.error_code,
                retryable=outcome.retryable,
                duration_ms=outcome.duration_ms,
                artifact_ids=payload["artifact_ids"],
                model_name=context.model_name,
            )

        runtime = ToolRuntime(
            tools=tool_def_list,
            model_call=llm_service.chat_with_tools_async,
            config=ToolRuntimeConfig(
                max_model_rounds=max_tool_rounds or config.TOOL_MAX_MODEL_ROUNDS,
                max_total_calls=config.TOOL_MAX_TOTAL_CALLS,
                max_consecutive_failure_rounds=config.TOOL_MAX_CONSECUTIVE_FAILURE_ROUNDS,
            ),
            artifact_handler=handle_artifact,
            trace_handler=handle_trace,
        )
        yield sse_stage("thinking", "正在思考...")
        async for runtime_event in runtime.run(
            [{"role": "user", "content": prompt}],
            ToolRuntimeContext(
                turn_id=turn_id,
                user_id=turn_input.user_id,
                chat_history_id=turn_input.chat_id or turn_input.marker_id,
                model_name=config.QA_LLM_MODEL,
            ),
        ):
            if runtime_event.type == "tool_call":
                yield sse_event("tool_call", runtime_event.data)
            elif runtime_event.type == "tool_result":
                yield sse_event("tool_result", runtime_event.data)
            elif runtime_event.type == "visualization":
                yield sse_event("visualization", runtime_event.data)
            elif runtime_event.type == "final":
                runtime_result = runtime_event.data["result"]

        if runtime_result is None:
            raise RuntimeError("工具运行时未返回最终回答")
        full_response = runtime_result.content
        if full_response:
            yield sse_text(full_response)

        latency_ms = int((time.perf_counter() - started_at) * 1000)
        record = QATurnRecord(
            turn_id=turn_id,
            user_id=turn_input.user_id,
            chat_id=turn_input.chat_id,
            input_type=turn_input.input_type,
            question=turn_input.question,
            marker_id=turn_input.marker_id or turn_input.chat_id,
            apprenticeship_level=None,
            answer=full_response,
            textbook_id=grounding.textbook_id,
            page_number=grounding.page_number,
            sequence_id=grounding.sequence_id,
            section_node_id=grounding.section_node_id,
            chapter_name=grounding.chapter_name,
            sources=sources,
            context_snapshot={
                "input_context": {
                    "marker_id": turn_input.marker_id or turn_input.chat_id,
                    "chat_id": turn_input.chat_id,
                    "page_number": turn_input.page_number,
                    "tree_id": turn_input.tree_id,
                    "node_id": turn_input.node_id,
                },
                "tool_runtime": {
                    "model_rounds": runtime_result.model_rounds,
                    "stats": runtime_result.stats,
                    "degraded": runtime_result.degraded,
                    "degradation_code": runtime_result.degradation_code,
                },
            },
            messages_snapshot=runtime_result.messages,
            screenshot_context_id=turn_input.screenshot_context_id,
            prompt_preview=prompt[:2000],
            model_name=config.QA_LLM_MODEL,
            latency_ms=latency_ms,
        )
        persist_done = asyncio.Event()
        bus = StreamBus()
        asyncio.create_task(start_persist_consumer(bus, record, persist_done))
        from app.services.diagnostic_worker import listen_qa_done
        asyncio.create_task(listen_qa_done(bus, turn_input.user_id, persist_done))
        await asyncio.sleep(0)
        bus.emit({"type": "done"})
        bus.close()

        done_data = {
            "full_text": full_response,
            "thinking": "",
            "sources": sources,
            "sequence_id": grounding.sequence_id,
            "qa_turn_id": turn_id,
            "visualizations": runtime_result.visualizations,
            "degraded": runtime_result.degraded,
            "tool_stats": runtime_result.stats,
        }
        if turn_input.screenshot_context_id:
            done_data["screenshot_context_id"] = turn_input.screenshot_context_id
        if runtime_result.degradation_code:
            done_data["degradation_code"] = runtime_result.degradation_code
        yield sse_done(**done_data)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        yield sse_error(str(exc))


def _ensure_requested_animation(artifact: dict, question: str) -> dict:
    """Attach only a bounded recipe when the user explicitly requested animation.

    The model may omit an optional nested field even after selecting the plot tool.
    Rebuilding through the same validated spec builder keeps this fallback inside the
    four-template protocol and never executes model-provided code.
    """
    from app.services.visualization.spec_builder import build_visualization

    if artifact.get("animation_available"):
        return artifact
    text = question or ""
    if not re.search(r"(?:\u52a8\u753b|\u52a8\u6001|\u64ad\u653e|\u6f14\u793a|animate|animation)", text, re.IGNORECASE):
        return artifact
    lowered = text.lower()
    if "\u5272\u7ebf" in text or "\u5207\u7ebf" in text or "secant" in lowered or "tangent" in lowered:
        template = "secant_to_tangent"
    elif "\u9ece\u66fc" in text or "\u7ec6\u5206" in text or "riemann" in lowered:
        template = "riemann_refinement"
    elif "\u77e9\u9635" in text or "\u7ebf\u6027\u53d8\u6362" in text or "linear_map" in lowered:
        template = "linear_map_2d"
    elif "\u5f62\u53d8" in text or "\u53d8\u6362" in text or "transform" in lowered:
        template = "function_transform"
    else:
        return artifact

    kind = artifact.get("kind")
    spec = artifact.get("spec") or {}
    parameters: dict[str, float] = {}
    if template == "secant_to_tangent":
        match = re.search(r"(?:x\s*[_0]?\s*=|x0\s*=)\s*(-?\d+(?:\.\d+)?)", text, re.IGNORECASE)
        parameters["x0"] = float(match.group(1)) if match else 0.0
    try:
        if template in {"secant_to_tangent", "riemann_refinement", "function_transform"}:
            if kind != "function_2d":
                return artifact
            series = [
                {key: item[key] for key in ("expression", "label", "color") if item.get(key)}
                for item in (spec.get("series") or [])
            ]
            rebuilt = build_visualization(
                kind=kind,
                title=artifact.get("title", ""),
                series=series,
                domain=spec.get("domain"),
                samples=max(32, min(600, len((spec.get("series") or [{}])[0].get("points") or []))),
                animation={"template": template, "parameters": parameters},
            )
        elif template == "linear_map_2d" and kind == "linear_transform_2d":
            rebuilt = build_visualization(
                kind=kind,
                title=artifact.get("title", ""),
                matrix=spec.get("matrix"),
                vectors=spec.get("vectors"),
                animation={"template": template, "parameters": parameters},
            )
        else:
            return artifact
    except (KeyError, TypeError, ValueError, IndexError):
        return artifact
    rebuilt["id"] = artifact.get("id", rebuilt["id"])
    return rebuilt
