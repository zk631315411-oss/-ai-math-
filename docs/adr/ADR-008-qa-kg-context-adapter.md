# ADR-008: QA-KG 上下文适配

**日期**：2026-07-03

## 背景

QA 极简化后只负责回答与写入 `QATurnRecord`，但 v4.4 KG 中的本节节点、同书文本命中、一跳关系和 RuleCase 条件尚未形成稳定的 QA 上下文。模型容易只依赖页文本，或在没有边界的情况下扩展到后续知识。

## 决策

在 `app/db/kg_v44.py` 增加按书过滤的同书文本反查、一跳关系、RuleCase 查询；在 `TurnGrounding` 中新增 `KGContext` dataclass，由 `qa/grounding_service.py` 组装本节核心、问题命中、支撑关系、后续展望和规则条件。QA prompt 只读该上下文，不触发诊断、不更新 stage。

RuleCase 查询种子包含本节核心节点、问题文本命中节点和非 lookahead 支撑节点，并按当前小节、问题相关性、支撑来源排序。lookahead 判断优先使用前端传入页码对应的教材页边界；无法定位到页时回退到章节/小节顺序。

前端页码徽标/线程 ID 通过 `marker_id` 进入 QA 记录，只用于 UI 标记与 `qa_turn_records` 的可追踪绑定；KG 的不超纲边界仍以教材页码和 `textbook_sections.sequence_id` 为准，不把 UI 标记当作教材结构来源。

## 理由

KG 在 QA 中的角色是教材索引、术语边界、关系约束和规则条件参考。教材原文仍是主证据；后续概念只用于展望；RuleCase 可帮助组织严谨步骤，但不生成学生诊断结论。

## 后果

- `diagnosis/contracts.py` 新增 `KGContext` / `KGRelationRef`
- 扩展 `KGNodeRef` / `RuleCaseRef` 以承载 scope、owner、条件逻辑等字段
- `qa_turn_records.context_snapshot` 保留 KG 上下文快照
- prompt 内使用压缩预算展示 KG：核心节点、文本命中、关系、lookahead 和 RuleCase 分别限量
- 前端展示 KG 命中详情暂列后续任务
