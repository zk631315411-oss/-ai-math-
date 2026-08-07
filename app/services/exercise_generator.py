"""智能出题生成器：LLM 流式 Markdown → 结构化 Exercise 对象。"""

import re
import json

STAGE_TO_EXERCISE = {
    0: {"target_stage": 1, "difficulty": "basic",
        "desc": "概念辨析题：给出几个陈述判断对错并解释"},
    1: {"target_stage": 2, "difficulty": "basic",
        "desc": "概念验证题：用自己的话解释概念"},
    2: {"target_stage": 3, "difficulty": "basic",
        "desc": "标准计算题：给定具体数值套公式求解"},
    3: {"target_stage": 4, "difficulty": "variation",
        "desc": "变式题：改变条件，多解法比较"},
    4: {"target_stage": 5, "difficulty": "comprehensive",
        "desc": "综合题：跨概念证明或开放探究"},
    5: {"target_stage": 5, "difficulty": "comprehensive",
        "desc": "自编题、推广、理论延伸"},
}

SYSTEM_PROMPT_TEMPLATE = """你是一位数学出题专家。请生成一道递进式练习题。

## 出题上下文
- 当前章节：{chapter_name}
- 当前页内容摘要：{page_summary}
- 知识白名单（只能使用以下概念）：{whitelist_micro}
- 学生认知阶段：{stage_desc}
- 目标：推到 Bloom 阶段 {target_stage}

## 出题要求
{exercise_desc}

## 输出格式（严格按以下 Markdown 结构，不得添加额外文字）

## 题目
[题目文本，LaTeX 公式用 $...$ 或 $$...$$]

## 答案
[详细解答步骤，每步解释原理]

## 提示
1. [方向提示—最模糊]
2. [中间步骤—较具体]
3. [接近答案—最详细]

## 验证
[将答案代回原条件验证，如"代回原方程，左=...=右 ✓"]

## computable
```json
{{"type": "操作类型", "matrix": [], "expected": []}}
```
"""


def get_stage_config(stage: int | None) -> dict:
    s = stage if stage is not None else 0
    return STAGE_TO_EXERCISE.get(s, STAGE_TO_EXERCISE[2])


def build_exercise_prompt(
    chapter_name: str = "",
    page_summary: str = "",
    whitelist_micro: str = "",
    stage: int | None = None,
    topic: str = "",
) -> str:
    cfg = get_stage_config(stage)
    stage_desc_map = {
        0: "未接触", 1: "记忆（能复述定义）", 2: "理解（能解释原理）",
        3: "应用（能解标准题）", 4: "分析（能比较多解）", 5: "创造（能自编题）",
    }
    stage_desc = stage_desc_map.get(stage, "未知") if stage is not None else "未知"
    return SYSTEM_PROMPT_TEMPLATE.format(
        chapter_name=chapter_name or topic or "未知章节",
        page_summary=page_summary or "（无页面上下文）",
        whitelist_micro=whitelist_micro or topic or "高等代数基础概念",
        stage_desc=stage_desc,
        target_stage=cfg["target_stage"],
        exercise_desc=cfg["desc"],
    )


def parse_markdown_sections(text: str) -> dict:
    """按标题名解析 Markdown → 结构化字段。

    识别 ## 题目 / ## 答案 / ## 提示 / ## 验证 / ## computable。
    缺题目或答案 → 返回空 dict 表示解析失败。
    """
    result = {"question": "", "answer": "", "hints": [], "verification": "", "computable": {}}

    # 按 ## 标题切分
    blocks = re.split(r"\n(?=## )", text)

    # 建立标题→索引映射
    sections = {}
    for i, block in enumerate(blocks):
        m = re.match(r"##\s*(.+?)\s*(\n|$)", block)
        if m:
            title = m.group(1).strip().lower()
            body = re.sub(r"^##\s*.+?\n", "", block).strip()
            # 规范化标题名
            if "题目" in title or title in {"title", "question", "problem"}:
                sections["question"] = body
            elif "答案" in title or title in {"answer", "solution"}:
                sections["answer"] = body
            elif "提示" in title or title in {"hint", "hints"}:
                sections["hints"] = body
            elif "验证" in title or title in {"verification", "verify"}:
                sections["verification"] = body
            elif "computable" in title:
                sections["computable"] = body

    result["question"] = sections.get("question", "").strip()
    result["answer"] = sections.get("answer", "").strip()
    result["verification"] = sections.get("verification", "").strip()

    # 解析提示（编号列表）
    hint_text = sections.get("hints", "")
    if hint_text:
        hints = []
        for line in hint_text.split("\n"):
            line = re.sub(r"^\d+\.\s*", "", line).strip()
            if line:
                hints.append(line)
        result["hints"] = hints[:3]

    # 解析 computable JSON
    comp_text = sections.get("computable", "")
    if comp_text:
        m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", comp_text, re.DOTALL)
        if m:
            try:
                result["computable"] = json.loads(m.group(1))
            except Exception:
                result["computable"] = {}
        else:
            try:
                result["computable"] = json.loads(comp_text)
            except Exception:
                result["computable"] = {}

    # 质量门：缺题目或缺答案 → 失败
    if not result["question"] or not result["answer"]:
        return {}

    return result
