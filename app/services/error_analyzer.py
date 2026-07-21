"""错因分析器：学生提交练习答案 → LLM 分析错因类型 + 补救建议。

仅在练习提交时做完整版（异步 BackgroundTasks）。
QA 流中不做 LLM 调用（用零延迟关键词检测代替）。
"""

import json
import re


ERROR_CATEGORIES = {
    "concept_confusion": [
        "definition_misunderstanding",
        "theorem_misapplication",
        "prerequisite_gap",
        "notation_misunderstanding",
    ],
    "calculation_error": [
        "arithmetic_mistake",
        "algebraic_manipulation",
        "sign_error",
        "missing_solution",
    ],
    "logic_gap": [
        "incomplete_reasoning",
        "incorrect_direction",
        "circular_reasoning",
        "unverified_assumption",
    ],
}


async def analyze_error(
    question: str,
    correct_answer: str,
    student_answer: str,
    stage: int | None,
    weak_points: list[str],
) -> dict | None:
    """异步 LLM 错因分析（在 BackgroundTasks 中调用）。"""
    from app.services.llm_service import llm_service

    prompt = f"""你是一位数学教育诊断专家。请分析学生的错误作答。

## 题目
{question}

## 标准答案
{correct_answer}

## 学生作答
{student_answer}

## 学生画像
- 知识点阶段：{stage if stage is not None else "未知"}
- 薄弱点：{', '.join(weak_points) if weak_points else "暂无"}

## 输出格式（严格 JSON）
{{
  "error_category": "concept_confusion | calculation_error | logic_gap",
  "error_subtype": "子类型",
  "specific_error": "具体错误描述（50字内）",
  "related_concept": "相关数学概念名称",
  "remediation": "补救建议（100字内）",
  "dimension_delta": {{"mt": {{"coverage":0,"radius":0,"technical":0}}, "lr": {{"coverage":0,"radius":0,"technical":0}}, "so": {{"coverage":0,"radius":0,"technical":0}}, "mr": {{"coverage":0,"radius":0,"technical":0}}, "ps": {{"coverage":0,"radius":0,"technical":0}}}},
  "stage_delta": -1
}}
"""

    messages = [
        {"role": "system", "content": "你是一位数学教育诊断专家。只输出 JSON。"},
        {"role": "user", "content": prompt},
    ]

    try:
        response = await llm_service.chat_async(messages, temperature=0.3)
        return _parse_response(response)
    except Exception:
        return None


def _parse_response(text: str) -> dict | None:
    """解析 LLM JSON 输出（容错：regex 提取 JSON）。"""
    try:
        return json.loads(text)
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return None
