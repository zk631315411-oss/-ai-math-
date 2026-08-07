"""Independent QA/exercise scorers for Stage and mathematical dimensions."""

from __future__ import annotations

import asyncio
import difflib
import json
import re
from dataclasses import asdict
from typing import Any, Callable

from app.config import config
from app.services.diagnosis.contracts import (
    DiagnosticSignal,
    DimensionObservation,
    ExerciseEvidenceInput,
    KGStageNode,
    KGStageRelation,
    QAEvidenceInput,
    StageObservation,
)


SCORER_VERSION = "v2"
PROMPT_VERSION = "v2.1"
DIMENSIONS = {"mt", "lr", "so", "mr", "ps"}
FACETS = {"coverage", "radius", "technical"}
BEHAVIORS = {
    "question_only", "self_report", "definition_recall", "solution_attempt",
    "explanation", "proof", "counterexample", "transfer",
}
SIGNAL_TYPES = {
    "concept_confusion", "prerequisite_gap", "procedural_error",
    "hint_dependency", "practice_request", "insufficient_evidence",
}
SIGNAL_PROMPT = """
Optionally include a top-level signals array. A signal describes a learning
issue, never a teaching action. Each signal must contain signal_type
(concept_confusion|prerequisite_gap|procedural_error|hint_dependency|
practice_request|insufficient_evidence), concept_ids, an exact student_quote,
confidence from 0 to 1, strength (certain|probable|hypothesis), and rationale.
Do not invent a signal when the student's own text is insufficient.
"""
ABSTRACTION_MARKERS = ("一般", "任意", "推广", "抽象", "结构", "本质", "n维", "对于所有", "归纳")
REASONING_MARKERS = ("因为", "所以", "因此", "由", "可得", "故", "若", "则", "假设", "反证", "充分", "必要")
REPRESENTATION_MARKERS = ("写成", "表示为", "转化为", "对应", "增广矩阵", "坐标", "图像", "几何", "语言描述")
STRATEGY_MARKERS = ("先", "再", "设", "令", "转化", "构造", "分情况", "采用", "选择", "思路", "策略")
TRANSFER_MARKERS = ("变式", "推广", "一般", "任意", "参数", "反例", "类似", "换成", "陌生", "跨", "建模")


SINGLE_EVENT_DIMENSION_RUBRIC = """
【五维边界：只认学生直接展示的行为】
- mt 数学抽象：抽取一般结构、泛化、归纳或讨论任意情形。仅套用已知规则、解释某一定理或完成计算不算 mt。
- lr 逻辑推理：明确使用条件、推论链、证明结构、充分必要关系。只有正确结果或算式不算 lr。
- so 符号运算：对符号、等式、矩阵、算子进行合法形式化或变换。概念性解释本身不算 so。
- mr 多重表征：在语言、符号、矩阵、坐标、图形、几何意义中至少两种表征之间明确转换。只写出一种表征不算 mr。
- ps 问题解决：展示策略选择、问题转化、分解、建模、比较方案或规划步骤。只报告最终答案或执行单个常规步骤不算 ps。

【单事件三分面】
- coverage positive：本事件直接展示该维度的建构性行为；negative：直接展示该维度的混淆、错误或缺失。不能由一次表现推断整体覆盖水平。
- radius positive：只有在变式、参数变化、反例、陌生情境、跨情境迁移中成功激活该维度；标准题一律 not_observed。只有明确面对迁移任务仍固着时才能 negative。
- technical positive：直接展示该维度特有的规范技术、定理或结构方法；negative：直接出现该维度特有的错误、跳步或不合法操作。仅仅答对不能 positive。

【证据强度】
- certain：学生原文直接、完整支持结论，且任务情境和帮助程度足够明确。
- probable：证据间接、过程不完整、任务情境不清或学生接受过具体提示。
- hypothesis：只有迹象，长期画像不采用。
【引文自检】
- student_quote 必须是学生原文中的最小充分子串，并且引文本身就包含该观察所需的行为，不能依赖相邻句或题目替它补足。
- lr 引文本身要有推理连接、条件关系或证明结构；so 要有实际公式、符号或变换；mr 要有“写成/转化/对应”等表征转换；ps 要有策略选择、分解或步骤规划；mt 要有一般化或结构归纳。
- radius 还必须由题目情境明确支持变式或迁移。无法给出合格引文时输出 not_observed 或省略该观察，不要猜测或凑满维度。
没有足够证据必须输出 not_observed 或省略；禁止为了填满五维而评分。
"""


class ObservationValidationError(ValueError):
    pass


def _normalize_stage_candidates(
    candidates: list[str] | list[KGStageNode],
) -> tuple[list[str], list[KGStageNode]]:
    if candidates and isinstance(candidates[0], KGStageNode):
        nodes = list(candidates)
        return [node.name for node in nodes], nodes
    return [str(candidate) for candidate in candidates], []


async def score_qa_stage(event: QAEvidenceInput) -> tuple[list[StageObservation], list[DiagnosticSignal], str]:
    prompt = _qa_stage_prompt(event) + SIGNAL_PROMPT
    data, raw = await _call_and_validate(prompt, lambda value: _validate_qa_stage(value, event))
    observations = [
        StageObservation(
            source_type="qa_turn", source_id=event.turn_id, user_id=event.user_id,
            sequence_id=event.sequence_id, concept_name=item["concept_name"],
            observed_stage=item["observed_stage"], direction=item["direction"],
            strength=item["strength"], student_quote=item["student_quote"],
            behavior=item["behavior"], support_level=event.previous_apprenticeship_level or "unknown",
            scorer_version=SCORER_VERSION,
            concept_id=item["concept_id"], concept_type=item["concept_type"],
            projection_role=item["projection_role"],
            suppressed_reason=item["suppressed_reason"],
            assistant_overlap=_assistant_overlap(_assistant_context(event), item["student_quote"]),
            dialogue_state_action=item["dialogue_state_action"],
            dialogue_state_reason=item["dialogue_state_reason"],
            dialogue_state_rationale=item["dialogue_state_rationale"],
        )
        for item in data.get("observations", [])
    ]
    signals = _diagnostic_signals(
        data, source_type="qa_turn", source_id=event.turn_id,
        user_id=event.user_id, sequence_id=event.sequence_id,
        student_text=event.student_text,
        allowed_concepts=event.kg_candidates,
    )
    return observations, signals, raw


async def score_qa_dimensions(event: QAEvidenceInput) -> tuple[list[DimensionObservation], str]:
    prompt = _qa_dimension_prompt(event)
    data, raw = await _call_and_validate(prompt, lambda value: validate_qa_dimensions(value, event))
    return _dimension_observations(data, "qa_turn", event.turn_id, event.user_id, event.sequence_id), raw


async def score_exercise_stage(
    event: ExerciseEvidenceInput,
    kg_candidates: list[str] | list[KGStageNode],
    kg_relations: list[KGStageRelation] | None = None,
) -> tuple[list[StageObservation], list[DiagnosticSignal], str]:
    candidate_names, candidate_nodes = _normalize_stage_candidates(kg_candidates)
    relations = list(kg_relations or [])
    prompt = _exercise_stage_prompt(event, candidate_names, candidate_nodes, relations) + SIGNAL_PROMPT
    data, raw = await _call_and_validate(
        prompt,
        lambda value: _validate_exercise_stage(
            value, event, candidate_names, candidate_nodes, relations
        ),
    )
    observations = [
        StageObservation(
            source_type="exercise_attempt", source_id=event.attempt_id, user_id=event.user_id,
            sequence_id=event.sequence_id, concept_name=item["concept_name"],
            observed_stage=item["observed_stage"], direction=item["direction"],
            strength=item["strength"], student_quote=item["student_quote"],
            behavior=item["behavior"], support_level=f"hint_level:{event.hint_level}",
            scorer_version=SCORER_VERSION,
            concept_id=item["concept_id"], concept_type=item["concept_type"],
            projection_role=item["projection_role"],
            suppressed_reason=item["suppressed_reason"],
        )
        for item in data.get("observations", [])
    ]
    signals = _diagnostic_signals(
        data, source_type="exercise_attempt", source_id=event.attempt_id,
        user_id=event.user_id, sequence_id=event.sequence_id,
        student_text=event.student_answer,
        allowed_concepts=[*candidate_names, *event.concept_ids],
    )
    return observations, signals, raw


def _diagnostic_signals(
    value: dict[str, Any], *, source_type: str, source_id: str, user_id: str,
    sequence_id: str, student_text: str, allowed_concepts: list[str],
) -> list[DiagnosticSignal]:
    """Validate optional signals independently from Stage observations."""
    raw_signals = value.get("signals", [])
    if not isinstance(raw_signals, list):
        return []
    allowed = set(allowed_concepts)
    signals: list[DiagnosticSignal] = []
    for raw in raw_signals:
        if not isinstance(raw, dict):
            continue
        signal_type = raw.get("signal_type")
        quote = raw.get("student_quote")
        concepts = raw.get("concept_ids") or []
        strength = raw.get("strength")
        confidence = raw.get("confidence")
        if signal_type not in SIGNAL_TYPES:
            continue
        if not isinstance(quote, str) or not quote or quote not in student_text:
            continue
        if not isinstance(concepts, list) or not all(isinstance(item, str) for item in concepts):
            continue
        if allowed and concepts and not set(concepts).issubset(allowed):
            continue
        if strength not in {"certain", "probable", "hypothesis"}:
            continue
        if not isinstance(confidence, (int, float)) or not 0 <= float(confidence) <= 1:
            continue
        signals.append(DiagnosticSignal(
            source_type=source_type,
            source_id=source_id,
            user_id=user_id,
            sequence_id=sequence_id,
            signal_type=signal_type,
            concept_ids=concepts,
            student_quote=quote,
            confidence=float(confidence),
            strength=strength,
            rationale=str(raw.get("rationale") or ""),
            scorer_version=SCORER_VERSION,
        ))
    return signals


async def score_exercise_dimensions(event: ExerciseEvidenceInput) -> tuple[list[DimensionObservation], str]:
    prompt = _exercise_dimension_prompt(event)
    data, raw = await _call_and_validate(prompt, lambda value: validate_exercise_dimensions(value, event))
    return _dimension_observations(
        data, "exercise_attempt", event.attempt_id, event.user_id, event.sequence_id
    ), raw


async def _call_and_validate(
    prompt: str,
    validator: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], str]:
    from app.services.llm_service import llm_service

    messages = [
        {"role": "system", "content": "你是大学数学学习证据评分器。只输出严格 JSON，不补写学生未展示的能力。"},
        {"role": "user", "content": prompt},
    ]
    last_error = ""
    last_raw = ""
    for attempt in range(2):
        if attempt:
            messages.append({"role": "assistant", "content": last_raw})
            messages.append({
                "role": "user",
                "content": (
                    f"上次输出校验失败：{last_error}。请按原 Schema 修正；"
                    "student_quote 必须由对应观察所需的学生原文行为自足支持。"
                    "无法精确引用时删除该观察或改为 not_observed，不得补写、改写或猜测学生能力。"
                ),
            })
        last_raw = await llm_service.chat_async(
            messages,
            model=config.PROFILE_LLM_MODEL,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        try:
            parsed = _parse_json(last_raw)
            return validator(parsed), last_raw
        except ObservationValidationError as exc:
            last_error = str(exc)
    raise ObservationValidationError(last_error or "invalid scorer output")


def _parse_json(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", raw or "")
        if not match:
            raise ObservationValidationError("输出不是 JSON 对象")
        try:
            value = json.loads(match.group())
        except json.JSONDecodeError as exc:
            raise ObservationValidationError("输出不是合法 JSON") from exc
    if not isinstance(value, dict):
        raise ObservationValidationError("顶层必须是 JSON 对象")
    return value


def _assistant_overlap(assistant_text: str, student_quote: str) -> float:
    """Return a conservative lexical overlap ratio for obvious answer copying."""
    assistant = "".join((assistant_text or "").split())
    quote = "".join((student_quote or "").split())
    if not assistant or not quote:
        return 0.0
    if quote in assistant:
        return 1.0
    if assistant in quote:
        return min(1.0, len(assistant) / len(quote))
    # Longest common contiguous span catches copied clauses without pretending
    # to understand semantic equivalence.
    match = difflib.SequenceMatcher(None, quote, assistant, autojunk=False).find_longest_match(
        0, len(quote), 0, len(assistant)
    )
    return match.size / len(quote)


def _assistant_context(event: QAEvidenceInput) -> str:
    history_answers = [
        item.get("assistant", "") for item in event.recent_history if item.get("assistant")
    ]
    if event.previous_ai_answer and event.previous_ai_answer not in history_answers:
        history_answers.append(event.previous_ai_answer)
    return "\n".join(history_answers)


def _validate_qa_stage(value: dict[str, Any], event: QAEvidenceInput) -> dict[str, Any]:
    observations = _stage_items(
        value,
        event.student_text,
        event.kg_candidates,
        event.kg_candidate_nodes,
        event.kg_candidate_relations,
    )
    support = (event.previous_apprenticeship_level or "unknown").lower()
    caps = {"modeling": 2, "coaching": 3, "scaffolding": 3, "fading": 5}
    for item in observations:
        behavior = item["behavior"]
        _validate_stage_behavior(item)
        _validate_dialogue_state_decision(item)
        if item["observed_stage"] > caps.get(support, 5):
            raise ObservationValidationError("QA Stage 超过脚手架上限")
        if behavior in {"question_only", "self_report"} and item["strength"] != "hypothesis":
            raise ObservationValidationError("普通提问和自我报告只能是 hypothesis")
        if support == "unknown" and item["strength"] == "certain":
            raise ObservationValidationError("帮助情况未知时不能输出 certain")
        if set(event.behavior_hints).issubset({"question_only", "self_report"}) and item["behavior"] not in {
            "question_only", "self_report"
        }:
            raise ObservationValidationError("学生原文只有提问或自我报告，不能改判为能力表现")
    return {"observations": observations, "signals": value.get("signals", [])}


def _validate_exercise_stage(
    value: dict[str, Any],
    event: ExerciseEvidenceInput,
    kg_candidates: list[str],
    kg_candidate_nodes: list[KGStageNode] | None = None,
    kg_candidate_relations: list[KGStageRelation] | None = None,
) -> dict[str, Any]:
    observations = _stage_items(
        value,
        event.student_answer,
        kg_candidates,
        kg_candidate_nodes or [],
        kg_candidate_relations or [],
    )
    for item in observations:
        stage = item["observed_stage"]
        _validate_stage_behavior(item)
        if event.hint_level > 0 and stage > 3:
            raise ObservationValidationError("使用提示后的练习最高支持 Stage 3")
        if _looks_like_final_answer_only(event.student_answer) and item["strength"] == "certain":
            raise ObservationValidationError("只有最终答案时证据最高为 probable")
    return {"observations": observations, "signals": value.get("signals", [])}


def _stage_items(
    value: dict[str, Any],
    student_text: str,
    kg_candidates: list[str],
    kg_candidate_nodes: list[KGStageNode] | None = None,
    kg_candidate_relations: list[KGStageRelation] | None = None,
) -> list[dict[str, Any]]:
    raw_items = value.get("observations", [])
    if not isinstance(raw_items, list):
        raise ObservationValidationError("observations 必须是数组")
    if raw_items and not kg_candidates:
        raise ObservationValidationError("KG 候选为空，拒绝 Stage 观察")
    allowed = set(kg_candidates)
    nodes_by_id = {node.node_id: node for node in (kg_candidate_nodes or [])}
    nodes_by_name = {node.name: node for node in (kg_candidate_nodes or [])}
    structured_candidates = bool(nodes_by_id)
    result = []
    seen: set[str] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            raise ObservationValidationError("Stage 观察必须是对象")
        concept = item.get("concept_name")
        concept_id = item.get("concept_id") or ""
        quote = item.get("student_quote")
        stage = item.get("observed_stage")
        direction = item.get("direction")
        strength = item.get("strength")
        behavior = item.get("behavior")
        if concept not in allowed:
            raise ObservationValidationError(f"概念不在 KG 候选中：{concept}")
        if structured_candidates:
            node = nodes_by_id.get(concept_id)
            if not node or node.name != concept:
                raise ObservationValidationError("concept_id 与 KG 概念名不匹配")
        else:
            node = nodes_by_name.get(concept)
        if not isinstance(quote, str) or not quote or quote not in student_text:
            raise ObservationValidationError("Stage 引用必须是学生原文的精确子串")
        if not isinstance(stage, int) or not 0 <= stage <= 5:
            raise ObservationValidationError("observed_stage 必须为 0-5 整数")
        if direction not in {"positive", "negative"}:
            raise ObservationValidationError("direction 非法")
        if strength not in {"certain", "probable", "hypothesis"}:
            raise ObservationValidationError("strength 非法")
        if behavior not in BEHAVIORS:
            raise ObservationValidationError("behavior 非法")
        if concept in seen:
            raise ObservationValidationError("同一评分结果中每个概念只能出现一次")
        seen.add(concept)
        result.append({
            "concept_name": concept, "student_quote": quote, "observed_stage": stage,
            "direction": direction, "strength": strength, "behavior": behavior,
            "concept_id": node.node_id if node else concept_id,
            "concept_type": node.node_type if node else "",
            "projection_role": "primary",
            "suppressed_reason": "",
            "dialogue_state_action": item.get("dialogue_state_action"),
            "dialogue_state_reason": item.get("dialogue_state_reason"),
            "dialogue_state_rationale": item.get("dialogue_state_rationale"),
        })
    return _suppress_part_of_duplicates(
        result, student_text, list(kg_candidate_relations or [])
    )


def _validate_stage_behavior(item: dict[str, Any]) -> None:
    stage = item["observed_stage"]
    behavior = item["behavior"]
    behavior_cap = {
        "question_only": 0,
        "self_report": 1,
        "definition_recall": 2,
        "solution_attempt": 3,
        "proof": 4,
        "explanation": 5,
        "counterexample": 5,
        "transfer": 5,
    }[behavior]
    if stage > behavior_cap:
        raise ObservationValidationError("Stage 超过学生行为上限")
    if stage == 4 and behavior not in {"explanation", "proof", "counterexample", "transfer"}:
        raise ObservationValidationError("Stage 4 必须有概念解释、条件关系或证明")


def _validate_dialogue_state_decision(item: dict[str, Any]) -> None:
    action = item.get("dialogue_state_action")
    reason = item.get("dialogue_state_reason")
    rationale = item.get("dialogue_state_rationale")
    if action not in {"accepted", "abstained"}:
        raise ObservationValidationError("dialogue_state_action 非法")
    if reason not in {
        "independent_evidence", "ai_dependent", "question_only",
        "self_report", "insufficient_context",
    }:
        raise ObservationValidationError("dialogue_state_reason 非法")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ObservationValidationError("dialogue_state_rationale 必须是非空字符串")
    if action == "accepted" and reason != "independent_evidence":
        raise ObservationValidationError("accepted 只能对应 independent_evidence")
    if action == "abstained" and reason == "independent_evidence":
        raise ObservationValidationError("abstained 不能对应 independent_evidence")
    if action == "accepted" and item["strength"] == "hypothesis":
        raise ObservationValidationError("accepted 与 hypothesis 结构矛盾")


def _suppress_part_of_duplicates(
    observations: list[dict[str, Any]],
    student_text: str,
    relations: list[KGStageRelation],
) -> list[dict[str, Any]]:
    by_id = {item["concept_id"]: item for item in observations if item["concept_id"]}
    for relation in relations:
        if relation.rel_type != "PART_OF":
            continue
        child = by_id.get(relation.source_node_id)
        parent = by_id.get(relation.target_node_id)
        if not child or not parent:
            continue
        if child["direction"] != parent["direction"] or child["behavior"] != parent["behavior"]:
            continue
        if not _quotes_overlap(child["student_quote"], parent["student_quote"], student_text):
            continue
        parent["projection_role"] = "supporting"
        parent["suppressed_reason"] = f"part_of_same_evidence:{relation.source_node_id}"
    return observations


def _quotes_overlap(left: str, right: str, source: str) -> bool:
    if left == right or left in right or right in left:
        return True
    left_starts = [match.start() for match in re.finditer(re.escape(left), source)]
    right_starts = [match.start() for match in re.finditer(re.escape(right), source)]
    return any(
        max(left_start, right_start) < min(left_start + len(left), right_start + len(right))
        for left_start in left_starts
        for right_start in right_starts
    )


def _validate_dimensions(value: dict[str, Any], student_text: str) -> dict[str, Any]:
    raw_items = value.get("observations", [])
    if not isinstance(raw_items, list):
        raise ObservationValidationError("observations 必须是数组")
    result = []
    seen: set[tuple[str, str]] = set()
    for item in raw_items:
        if not isinstance(item, dict):
            raise ObservationValidationError("维度观察必须是对象")
        if item.get("status") == "not_observed":
            continue
        dimension, facet = item.get("dimension"), item.get("facet")
        direction, strength, quote = item.get("direction"), item.get("strength"), item.get("student_quote")
        if dimension not in DIMENSIONS or facet not in FACETS:
            raise ObservationValidationError("维度或分面非法")
        if direction not in {"positive", "negative"}:
            raise ObservationValidationError("维度方向非法")
        if strength not in {"certain", "probable", "hypothesis"}:
            raise ObservationValidationError("维度强度非法")
        if not isinstance(quote, str) or not quote or quote not in student_text:
            raise ObservationValidationError("维度引用必须是学生原文的精确子串")
        key = (dimension, facet)
        if key in seen:
            raise ObservationValidationError("同一事件的同一维度分面只能观察一次")
        seen.add(key)
        result.append({
            "dimension": dimension, "facet": facet, "direction": direction,
            "strength": strength, "student_quote": quote,
        })
    return {"observations": result}


def validate_qa_dimensions(value: dict[str, Any], event: QAEvidenceInput) -> dict[str, Any]:
    result = _validate_dimensions(value, event.student_text)
    if set(event.behavior_hints).issubset({"question_only", "self_report"}) and result["observations"]:
        raise ObservationValidationError("普通提问或自我报告不能形成素养观察")
    support = (event.previous_apprenticeship_level or "unknown").lower()
    for item in result["observations"]:
        if support in {"unknown", "modeling", "coaching", "scaffolding"} and item["strength"] == "certain":
            raise ObservationValidationError("帮助不明或接受具体支架时，QA素养证据最高为 probable")
        _validate_dimension_semantics(
            item,
            student_text=event.student_text,
            task_context=event.previous_ai_answer,
            allow_negative=True,
        )
    return result


def validate_exercise_dimensions(
    value: dict[str, Any],
    event: ExerciseEvidenceInput,
) -> dict[str, Any]:
    result = _validate_dimensions(value, event.student_answer)
    for item in result["observations"]:
        if event.hint_level > 0 and item["strength"] == "certain":
            raise ObservationValidationError("使用提示后的练习素养证据最高为 probable")
        _validate_dimension_semantics(
            item,
            student_text=event.student_answer,
            task_context=f"{event.question} {event.difficulty}",
            allow_negative=not event.is_correct,
        )
    return result


def _validate_dimension_semantics(
    item: dict[str, Any],
    *,
    student_text: str,
    task_context: str,
    allow_negative: bool,
) -> None:
    dimension = item["dimension"]
    facet = item["facet"]
    direction = item["direction"]
    quote = item["student_quote"]
    combined_context = f"{student_text} {task_context}"

    if direction == "negative":
        if not allow_negative:
            raise ObservationValidationError("正确且无直接失败证据的事件不能输出负向素养观察")
        if facet == "radius" and not _contains_any(combined_context, TRANSFER_MARKERS):
            raise ObservationValidationError("radius negative 必须来自明确的迁移或变式任务")
        return

    if facet == "radius" and not _contains_any(combined_context, TRANSFER_MARKERS):
        raise ObservationValidationError("标准情境不能形成 radius positive")
    if dimension == "mt" and not _contains_any(quote, ABSTRACTION_MARKERS):
        raise ObservationValidationError("数学抽象正证据必须直接展示泛化、归纳或一般结构")
    if dimension == "lr" and not _contains_any(quote, REASONING_MARKERS):
        raise ObservationValidationError("逻辑推理正证据必须包含明确推理或条件关系")
    if dimension == "so" and not _contains_formal_expression(quote):
        raise ObservationValidationError("符号运算正证据必须包含实际符号或形式变换")
    if dimension == "mr" and not _contains_any(quote, REPRESENTATION_MARKERS):
        raise ObservationValidationError("多重表征正证据必须引用明确的表征转换")
    if dimension == "ps" and not _contains_any(quote, STRATEGY_MARKERS):
        raise ObservationValidationError("问题解决正证据必须引用策略选择、转化或规划")


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in (text or "") for marker in markers)


def _contains_formal_expression(text: str) -> bool:
    return bool(re.search(r"[=<>≤≥]|\bR\d+\b|\[.*?\]|\\(?:frac|sum|int)|\d+\s*[+\-*/]\s*\d+", text or ""))


def _dimension_observations(
    data: dict[str, Any], source_type: str, source_id: str, user_id: str, sequence_id: str,
) -> list[DimensionObservation]:
    return [
        DimensionObservation(
            source_type=source_type, source_id=source_id, user_id=user_id,
            sequence_id=sequence_id, dimension=item["dimension"], facet=item["facet"],
            direction=item["direction"], strength=item["strength"],
            student_quote=item["student_quote"], scorer_version=SCORER_VERSION,
        )
        for item in data.get("observations", [])
    ]


def _looks_like_final_answer_only(text: str) -> bool:
    compact = " ".join((text or "").split())
    return len(compact) < 40 and not any(token in compact for token in ("因为", "所以", "由", "设", "证明"))


def _stage_kg_prompt(
    names: list[str],
    nodes: list[KGStageNode],
    relations: list[KGStageRelation],
) -> str:
    if not nodes:
        return f"KG候选概念名：{json.dumps(names, ensure_ascii=False)}"
    node_payload = [
        {"concept_id": node.node_id, "concept_name": node.name, "concept_type": node.node_type}
        for node in nodes
    ]
    relation_payload = [
        {
            "source_id": relation.source_node_id,
            "source_name": relation.source_name,
            "relation": relation.rel_type,
            "target_id": relation.target_node_id,
            "target_name": relation.target_name,
        }
        for relation in relations
    ]
    return (
        f"KG候选节点：{json.dumps(node_payload, ensure_ascii=False)}\n"
        f"候选间有向关系：{json.dumps(relation_payload, ensure_ascii=False)}"
    )


def _qa_stage_prompt(event: QAEvidenceInput) -> str:
    kg_context = _stage_kg_prompt(
        event.kg_candidates,
        event.kg_candidate_nodes,
        event.kg_candidate_relations,
    )
    return f"""评分 QA 中学生自己展示的概念掌握阶段。AI 回答只能用于判断帮助和证据独立性，禁止把 AI 文本本身当作学生能力证据。

{kg_context}
上一轮脚手架：{event.previous_apprenticeship_level or 'unknown'}
上一轮AI回答（仅帮助上下文）：{event.previous_ai_answer[:1200]}
当前分支最近三轮（仅用于判断任务、提示和语义依赖）：{json.dumps(event.recent_history, ensure_ascii=False)}
学生当前原文：{event.student_text}
行为提示：{json.dumps(event.behavior_hints, ensure_ascii=False)}

阶段：0无证据/陌生，1识别术语，2复述定义，3提示下应用，4独立应用并解释，5迁移/反例/讲解。
普通解题步骤 solution_attempt 最高 Stage 3；Stage 4 必须引用学生针对该概念的解释、条件关系或证明；Stage 5 必须有迁移、反例或完整讲解。
选择最小且不重复的概念集合，不限制概念数量。每个概念必须有各自直接证据；不能因为 A USES/GETS B 就推断学生掌握 B。
若同一原文同时支持 A PART_OF B 两端，优先输出更具体的 A；不同原文展示不同行为时可分别输出。
普通提问或自我报告只能 hypothesis。没有可评分表现时 observations 输出空数组。
对每个观察同时判断学生是否独立展示能力：不能只看字符重合。即使换用同义表达，只要语义上是在复述 AI、沿用跨轮给出的关键推理或答案，也应 abstained/ai_dependent；即使字符重合较高，只要当前回答在任务语境中确实独立构造并展示了能力，也可 accepted/independent_evidence。纯提问、自我报告或上下文不足分别使用 question_only、self_report、insufficient_context。给出简短语义依据。
accepted 必须对应 independent_evidence，且不能与 hypothesis 同时出现；其他情况使用 abstained。
输出：{{"observations":[{{"concept_id":"KG节点ID","concept_name":"KG原名","observed_stage":0,"direction":"positive|negative","strength":"certain|probable|hypothesis","behavior":"question_only|self_report|definition_recall|solution_attempt|explanation|proof|counterexample|transfer","student_quote":"学生原文精确子串","dialogue_state_action":"accepted|abstained","dialogue_state_reason":"independent_evidence|ai_dependent|question_only|self_report|insufficient_context","dialogue_state_rationale":"简短语义依据"}}]}}"""


def _qa_dimension_prompt(event: QAEvidenceInput) -> str:
    return f"""只评价 QA 中学生原文实际展示的数学素养。禁止评价 AI 回答；上一轮AI内容只能说明任务和帮助背景。普通提问和未出现的维度输出 not_observed 或省略。
上一轮脚手架：{event.previous_apprenticeship_level or 'unknown'}
上一轮AI任务/提示（不可作为学生证据）：{event.previous_ai_answer[:1200]}
学生原文：{event.student_text}
{SINGLE_EVENT_DIMENSION_RUBRIC}
帮助不明、modeling、coaching 或 scaffolding 时，强度最高 probable；只有 fading 或无帮助且证据完整时才可 certain。
输出：{{"observations":[{{"dimension":"mt|lr|so|mr|ps","facet":"coverage|radius|technical","status":"observed|not_observed","direction":"positive|negative","strength":"certain|probable|hypothesis","student_quote":"学生原文精确子串"}}]}}"""


def _exercise_stage_prompt(
    event: ExerciseEvidenceInput,
    kg_candidates: list[str],
    kg_candidate_nodes: list[KGStageNode],
    kg_candidate_relations: list[KGStageRelation],
) -> str:
    kg_context = _stage_kg_prompt(
        kg_candidates, kg_candidate_nodes, kg_candidate_relations
    )
    return f"""只评价这次练习中学生答案展示的概念掌握阶段。
{kg_context}
题目：{event.question}
诊断目标：{event.diagnostic_goal}；难度：{event.difficulty}；使用提示次数：{event.hint_level}
学生答案：{event.student_answer}
标准答案（仅供核对）：{event.correct_answer}
批改：is_correct={event.is_correct}；feedback={event.grading_feedback}
题目不预设学生Stage。只按学生原文实际展示的行为判断；用过提示最高Stage 3；只有最终答案最高 probable。普通解题步骤 solution_attempt 最高 Stage 3；Stage 4 必须有概念解释、条件关系或证明；Stage 5 仅限迁移、反例或跨情境应用。
选择最小且不重复的概念集合，不限制概念数量。每个概念必须有各自直接证据；不能因为 A USES/GETS B 就推断学生掌握 B。同一原文同时支持 A PART_OF B 两端时优先更具体的 A。
输出：{{"observations":[{{"concept_id":"KG节点ID","concept_name":"KG原名","observed_stage":0,"direction":"positive|negative","strength":"certain|probable|hypothesis","behavior":"definition_recall|solution_attempt|explanation|proof|counterexample|transfer","student_quote":"学生答案精确子串"}}]}}"""


def _exercise_dimension_prompt(event: ExerciseEvidenceInput) -> str:
    return f"""只评价这次练习中学生答案实际展示的数学素养。
题目：{event.question}
学生答案：{event.student_answer}
正确性：{event.is_correct}；提示次数：{event.hint_level}；批改反馈：{event.grading_feedback}
题目难度：{event.difficulty}
{SINGLE_EVENT_DIMENSION_RUBRIC}
计算题不能自动支持逻辑推理；证明题必须有学生证明过程；表征转换和迁移必须有明确行为。使用过提示时强度最高 probable。未观察到输出 not_observed 或省略。
输出：{{"observations":[{{"dimension":"mt|lr|so|mr|ps","facet":"coverage|radius|technical","status":"observed|not_observed","direction":"positive|negative","strength":"certain|probable|hypothesis","student_quote":"学生答案精确子串"}}]}}"""
