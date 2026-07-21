"""QA 回答模块的轻量 Prompt 构造器。"""

from __future__ import annotations

from app.services.diagnosis.contracts import KGContext, StudentStateSummary, TutorPolicy, TurnGrounding
from app.services.scaffolding_controller import (
    STRUGGLE_HINT,
    ApprenticeshipLevel,
    StudentLevel,
    scaffolding_controller,
)

# Socratic 子模式对应的角色段
SUBMODE_ROLE = {
    "preview": "你是一位数学导学教练。学生还没学过这个概念，你需要用生活中的例子和直观类比引入，通过一系列引导性问题让学生自己发现规律。不要直接给出定义和结论，要让学生从具体现象中归纳。",
    "exam_review": "你是一位数学备考教练。学生正在准备考试，你需要快速扫描学生的知识盲区，用典型考题的反例和常见陷阱来检验理解。重点放在审题技巧、易错点、时间分配上。",
    "connected_review": "你是一位数学知识架构师。学生已经分散地学过了各个章节，你需要用引导性问题帮助学生发现跨章节的联系。例如行列式和特征值的关系、线性方程组在不同章节中分别怎么处理。",
    "unclassified": "你是一位博学的数学家，擅长用苏格拉底式提问法引导用户思考。",
}

DIRECT_ROLE = "你是一位博学的数学家。请对题目进行详细讲解，包括完整解题步骤，最终给出正确答案。数学公式必须用 LaTeX 格式。"


def build_tutor_prompt(
    question: str,
    grounding: TurnGrounding,
    student_state: StudentStateSummary,
    policy: TutorPolicy,
    history: list[dict] | None = None,
) -> str:
    """根据定位、学生状态和教学策略构造轻量 Prompt。"""

    concept_names = [node.name for node in grounding.related_concepts if node.name][:12]
    prereq_names = [node.name for node in grounding.prerequisite_concepts if node.name][:8]
    kg_context = grounding.kg_context
    evidence_lines = [
        f"- {span.node_name or '教材'}: {span.text[:180]}"
        for span in grounding.evidence_spans[:5]
        if span.text
    ]
    weak_lines = [
        f"- {gap.name}: stage={gap.stage if gap.stage is not None else '未知'} {gap.evidence}".strip()
        for gap in student_state.weak_prerequisites[:6]
    ]

    return f"""你是“学数有道”的大学数学 AI 私教。请根据教材定位、知识图谱和学生状态回答。

【本轮教材定位】
- 教材：{grounding.textbook_id}
- 页码：{grounding.page_number or '未知'}
- 章节：{grounding.chapter_name or '未知'}
- sequence_id：{grounding.sequence_id}
- section_node_id：{grounding.section_node_id}

【当前页/命中片段】
{grounding.content_excerpt or '（无页面片段）'}

【KG 相关概念】
{_join_or_empty(concept_names)}

【可能支撑/前置概念】
{_join_or_empty(prereq_names)}

【KG 使用边界】
- KG 只作为教材索引、术语边界、关系约束和规则条件参考；若 KG 与当前页原文不一致，以当前页原文为准。
- 可直接用于当前解答的知识范围：当前教材中学生已翻到的页码/小节及之前内容。
- 后续概念只能在学生明确询问“和后面有什么关系/之后会学什么”时点到为止，不能作为当前解法的必要依赖。
- RuleCase 可用于组织严谨步骤：先核验适用条件，再使用对应结论；但不要生成学生诊断结论。

【KG 命中详情】
本节核心：
{_format_kg_nodes(_kg_items(kg_context, "current_nodes"), limit=8)}

问题文本命中：
{_format_kg_nodes(_kg_items(kg_context, "question_matches"), limit=5)}

支撑关系：
{_format_kg_relations(_kg_items(kg_context, "relations"), limit=6)}

后续展望概念：
{_format_kg_nodes(_kg_items(kg_context, "lookahead_nodes"), limit=3)}

规则条件参考：
{_format_rule_cases(_kg_items(kg_context, "rule_cases"), limit=3)}

【教材证据】
{chr(10).join(evidence_lines) if evidence_lines else '（暂无可展示证据片段）'}

【学生状态摘要】
- 当前小节综合 stage：{student_state.current_section_stage if student_state.current_section_stage is not None else '未知'}
- 可能卡点：{student_state.likely_breakpoint or '未知'}
- 最近模式：{student_state.recent_pattern or '暂无'}
- 薄弱前置：
{chr(10).join(weak_lines) if weak_lines else '（暂无明确薄弱前置）'}

【教学策略】
- 模式：{policy.mode}/{policy.submode}
- 先补前置：{policy.should_review_prerequisites}
- 引导式提问：{policy.should_ask_guiding_question}
- 解释规则条件：{policy.should_explain_rule_conditions}
- 允许完整解答：{policy.allow_full_solution}
- 深度：{policy.answer_depth}
- 策略理由：{policy.rationale or '按当前学生状态给出清晰讲解'}

【最近相关历史】
{_format_history(history)}

【学生问题】
{question}

请用中文回答，数学公式用 LaTeX。回答要围绕当前页和 KG 证据，不要无根据扩展。"""


def _format_history(history: list[dict] | None) -> str:
    if not history:
        return "（无）"
    lines: list[str] = []
    for item in history[-3:]:
        user = item.get("user") or item.get("question") or ""
        assistant = item.get("assistant") or item.get("answer") or ""
        if user:
            lines.append(f"- 学生：{user[:180]}")
        if assistant:
            lines.append(f"  老师：{assistant[:260]}")
    return "\n".join(lines) if lines else "（无）"


def _join_or_empty(values: list[str]) -> str:
    return "、".join(values) if values else "（暂无）"


def _kg_items(kg_context: KGContext | dict | None, field_name: str) -> list:
    if kg_context is None:
        return []
    if isinstance(kg_context, dict):
        return kg_context.get(field_name, []) or []
    return getattr(kg_context, field_name, []) or []


def _field(value, name: str, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _format_kg_nodes(nodes: list, limit: int) -> str:
    lines: list[str] = []
    for node in (nodes or [])[:limit]:
        name = _field(node, "name")
        if not name:
            continue
        node_type = _field(node, "type") or _field(node, "node_type") or "KGNode"
        scope = _field(node, "scope") or "allowed"
        evidence = (_field(node, "evidence_span") or "").strip()
        source = _field(node, "source_code") or _field(node, "section_node_id") or ""
        detail = f"- {name}（{node_type}，{scope}"
        if source:
            detail += f"，{source}"
        detail += "）"
        if evidence:
            detail += f"：{evidence[:120]}"
        lines.append(detail)
    return "\n".join(lines) if lines else "（暂无）"


def _format_kg_relations(relations: list, limit: int) -> str:
    lines: list[str] = []
    for rel in (relations or [])[:limit]:
        source = _field(rel, "source") or _field(rel, "source_name")
        target = _field(rel, "target") or _field(rel, "target_name")
        rel_type = _field(rel, "rel_type")
        if not source or not target or not rel_type:
            continue
        scope = _field(rel, "scope") or "allowed"
        lines.append(f"- {source} --{rel_type}--> {target}（{scope}）")
    return "\n".join(lines) if lines else "（暂无）"


def _format_rule_cases(rule_cases: list, limit: int) -> str:
    lines: list[str] = []
    for case in (rule_cases or [])[:limit]:
        owner = _field(case, "owner") or _field(case, "owner_name") or "规则"
        name = _field(case, "rule_case") or _field(case, "name") or ""
        conditions = "；".join((_field(case, "conditions") or [])[:4]) or "未列出"
        outcomes = "；".join((_field(case, "outcomes") or [])[:4]) or "未列出"
        applies_to = "；".join(_field(case, "applies_to") or []) or "未列出"
        logic = _field(case, "condition_logic") or "条件"
        evidence = (_field(case, "evidence_span") or "").strip()
        line = (
            f"- {owner}"
            f"{' / ' + name if name else ''}：适用对象={applies_to}；"
            f"{logic}={conditions}；结论={outcomes}"
        )
        if evidence:
            line += f"；证据={evidence[:120]}"
        lines.append(line)
    return "\n".join(lines) if lines else "（暂无）"


def build_vision_prompt(
    *,
    question,
    page_context,
    whitelist=None,
    profile=None,
    teaching_mode="socratic",
    socratic_submode="unclassified",
    history=None,
    student_stage=None,
    prereq_gaps=None,
    student_level=None,
    apprenticeship_level=None,
    user_message_for_struggle="",
    kg_context: KGContext | dict | None = None,
) -> str:
    """组装视觉版 System Prompt（恒为有图模式）。

    整合 10 路教学信号：角色、教学规则、认知感知、零延迟检测、前置提醒、
    干预块、白名单、画像、教材上下文、历史对话。
    """

    # 1. 角色段（有具体 submode 时不拼接通用前缀）
    if teaching_mode == "direct":
        role = DIRECT_ROLE
    else:
        role = SUBMODE_ROLE.get(socratic_submode, SUBMODE_ROLE["unclassified"])
        # 只有 unclassified 时才用通用前缀兜底
        if socratic_submode == "unclassified":
            prefix = scaffolding_controller.get_role_prefix(student_level, teaching_mode)
            if prefix and prefix not in role:
                role = prefix + "\n" + role

    # 2. 教学规则段（学徒层级）
    if apprenticeship_level is None:
        apprenticeship_level = scaffolding_controller.determine_level(
            student_stage, socratic_submode
        )
    # Socratic 下不强制给完整答案，MODELING 降为 COACHING
    if teaching_mode == "socratic" and apprenticeship_level == ApprenticeshipLevel.MODELING:
        apprenticeship_level = ApprenticeshipLevel.COACHING
    rules = scaffolding_controller.get_prompt_segment(apprenticeship_level)

    # 3. 认知感知段
    cognition = scaffolding_controller.get_cognition_segment(student_stage)

    # 4. 零延迟关键词检测
    struggle_block = ""
    if user_message_for_struggle and scaffolding_controller.detect_struggle(user_message_for_struggle):
        struggle_block = STRUGGLE_HINT

    # 5. 前置提醒块
    from app.services.prerequisite_checker import build_prereq_prompt_block

    prereq_block = build_prereq_prompt_block(prereq_gaps or [])

    # 6. 干预块（诊断报告）
    intervention_text = ""
    if profile:
        diagnostic = profile.get("latest_diagnostic_report", {})
        if isinstance(diagnostic, str):
            import json

            try:
                diagnostic = json.loads(diagnostic)
            except Exception:
                diagnostic = {}
        weak_node = diagnostic.get("weak_node", "") if isinstance(diagnostic, dict) else ""
        suggestion = (
            diagnostic.get("intervention_suggestion", "") if isinstance(diagnostic, dict) else ""
        )
        if weak_node and suggestion:
            intervention_text = f"\n当前学生在「{weak_node}」存在认知薄弱点。教学建议：{suggestion}\n"

    # 7. 知识白名单块
    whitelist_block = ""
    if whitelist:
        macro = whitelist.get("macro", "")
        micro = whitelist.get("micro", "")
        whitelist_block = (
            f"\n【知识点放行清单】\n{macro}\n具体概念：{micro}\n"
            "规则：只使用放行清单中的概念讲解，如需超出名单的概念必须先确认学生是否学过。\n"
        )

    # 8. 学生画像块
    profile_block = ""
    if profile:
        grade = profile.get("grade", "") or ""
        weak_points = profile.get("weak_points", [])
        if isinstance(weak_points, str):
            import json

            try:
                weak_points = json.loads(weak_points)
            except Exception:
                weak_points = []
        weak_str = "、".join(weak_points) if weak_points else "暂无"
        profile_block = f"\n【学生画像】\n年级：{grade}\n薄弱知识点：{weak_str}\n"

    # 9. 教材上下文块
    context_block = ""
    if page_context:
        chapter = page_context.get("chapter_name", "")
        content = page_context.get("content", "")
        start = page_context.get("start_page", "")
        end = page_context.get("end_page", "")
        context_block = (
            f"\n【教材上下文】\n当前章节：{chapter}（第{start}-{end}页）\n章节内容：\n{content}\n"
            if chapter
            else ""
        )

    # 10. 历史对话
    history_text = ""
    if history:
        history_text = "\n【对话历史】\n"
        for i, h in enumerate(history[-6:]):  # 最近 6 轮
            u = h.get("user", "") or h.get("question", "")
            a = h.get("assistant", "") or h.get("answer", "")
            if u:
                history_text += f"学生：{u[:300]}\n"
            if a:
                history_text += f"老师：{a[:2000]}\n"

    # 语言指令：只约束语言选择，不要求输出思考过程
    lang_rule = "你只能使用中文进行思考和回答。\n所有数学公式必须用 $...$（行内）或 $$...$$（独立行）包裹。\n\n"

    # 视觉特有：从教材上下文中提取对应公式原文
    formula_ref = ""
    if page_context and "error" not in page_context:
        formula_ref = "注意：你现在是在看图回答问题。请扫描【教材上下文】中的 MD 源码，找出与截图对应的 LaTeX 公式，在回答中显式写出它们。\n"

    kg_block = ""
    if kg_context:
        kg_block = f"""
【KG 使用边界】
- KG 只作为教材索引、术语边界、关系约束和规则条件参考；若 KG 与当前页原文不一致，以当前页原文为准。
- 可直接用于当前解答的知识范围：当前教材中学生已翻到的页码/小节及之前内容。
- 后续概念只能在学生明确询问“和后面有什么关系/之后会学什么”时点到为止，不能作为当前解法的必要依赖。
- RuleCase 可用于组织严谨步骤：先核验适用条件，再使用对应结论；但不要生成学生诊断结论。

【KG 命中详情】
本节核心：
{_format_kg_nodes(_kg_items(kg_context, "current_nodes"), limit=8)}

问题文本命中：
{_format_kg_nodes(_kg_items(kg_context, "question_matches"), limit=5)}

支撑关系：
{_format_kg_relations(_kg_items(kg_context, "relations"), limit=6)}

后续展望概念：
{_format_kg_nodes(_kg_items(kg_context, "lookahead_nodes"), limit=3)}

规则条件参考：
{_format_rule_cases(_kg_items(kg_context, "rule_cases"), limit=3)}
"""

    assembled = f"""{lang_rule}{role}{intervention_text}{whitelist_block}{profile_block}{prereq_block}{cognition}{struggle_block}
{rules}{formula_ref}
{history_text}
题目：{question}

{kg_block}
{context_block}

现在开始你的回答："""

    return assembled
