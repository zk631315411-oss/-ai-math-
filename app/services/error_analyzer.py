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

    # 从题目中提取概念名，查询规则案例
    rule_cases_block = _build_rule_cases_block(question, correct_answer)

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

{rule_cases_block}
## 输出格式（严格 JSON）
{{{{
  "error_category": "concept_confusion | calculation_error | logic_gap",
  "error_subtype": "子类型",
  "specific_error": "具体错误描述（50字内）",
  "related_concept": "相关数学概念名称",
  "remediation": "补救建议（100字内）",
  "dimension_delta": {{{{"mt": {{{{"coverage":0,"radius":0,"technical":0}}}}, "lr": {{{{"coverage":0,"radius":0,"technical":0}}}}, "so": {{{{"coverage":0,"radius":0,"technical":0}}}}, "mr": {{{{"coverage":0,"radius":0,"technical":0}}}}, "ps": {{{{"coverage":0,"radius":0,"technical":0}}}}}}}},
  "stage_delta": -1
}}}}
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


def _build_rule_cases_block(question: str, correct_answer: str) -> str:
    """尝试从题目/答案中提取关键概念，查询规则案例并构建 prompt 块。

    如果查询不到规则案例，返回空字符串。
    """
    try:
        from app.db.kg_v44 import get_rule_cases_for_node

        # 从题目和答案中提取可能的数学概念名（取第一个出现的概念）
        candidate = _guess_concept(question, correct_answer)
        if not candidate:
            return ""

        cases = get_rule_cases_for_node(candidate, limit=3)
        if not cases:
            return ""

        lines = ["## 相关规则案例（知识图谱结构化数据）"]
        for case in cases:
            owner = case.get("owner_name", "")
            name = case.get("rule_case", "")
            applies_to = "、".join(case.get("applies_to") or []) or "未指定"
            condition_logic = case.get("condition_logic", "条件")
            conditions = "；".join(case.get("conditions") or []) or "未列出"
            outcomes = "；".join(case.get("outcomes") or []) or "未列出"
            lines.append(f"- {owner} / {name}：适用对象={applies_to}；{condition_logic}={conditions}；结论={outcomes}")
            evidence = (case.get("evidence_span") or "").strip()
            if evidence:
                lines.append(f"  教材出处：{evidence[:200]}")

        lines.append("")
        lines.append("请基于以上规则案例分析学生的错因，判断学生是：")
        lines.append("1. 条件理解错误（如条件中的关键概念没理解）")
        lines.append("2. 条件→结论映射错误（满足条件但推导出错误的结论）")
        lines.append("3. 适用对象错误（用错了定理/规则）")
        return "\n".join(lines)
    except Exception:
        return ""


def _guess_concept(question: str, answer: str) -> str | None:
    """从题目和答案中猜测主要概念名。

    简单策略：匹配常见的数学概念关键词。
    如果找不到，返回 None。
    """
    # 常见数学概念关键词
    keywords = [
        "行列式", "矩阵", "特征值", "特征向量", "线性无关", "线性相关",
        "线性方程组", "逆矩阵", "伴随矩阵", "秩", "向量组",
        "导数", "积分", "极限", "微分", "偏导",
        "特征多项式", "相似矩阵", "对角化",
    ]
    text = f"{question} {answer}"
    for kw in keywords:
        if kw in text:
            return kw
    return None
