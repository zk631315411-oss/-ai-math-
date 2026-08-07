# app/services/practice/ — 教材优先自适应练习

## 为什么存在

把练习从「LLM 凭空出题」改成**教材优先的自适应练习**：练习永远来自服务端构建的
已审核教材题池，模型只负责在候选集内做受控选择，不能靠生成器兜底。

## 硬边界（`service.py` 模块 docstring 即契约）

- 模型只能从服务端构建的候选集选择，**不能凭空造题**；
- 候选集默认限定当前 / 前置概念，**只有独立答对（correct 且无提示）才放行相邻后继概念**
  （`allow_successors`），模型不能自行解锁；
- **不能无证据宣告掌握**：掌握必须由显式选择的验证题（purpose=verify，受
  `SELECTION_USES` 语义白名单约束）+ 独立答对确认，见 `_is_legal_mastery`。

## 核心流程

```text
证据上下文（service._load_turn_context：从 qa_turn_records 提取 grounding/概念/证据引文）
  → repo.create_draft() + practice_worker.enqueue()   # 草稿入库 + 入队
  → worker → agents.build_draft()                     # 后台从已审核教材题池构建候选集（repository.list_items）
  → 会话开始时 service._model_select()                # LLM 挑选，受 SELECTION_USES + 强校验约束
  → 作答 submit_attempt → service._grade()            # 独立 LLM 批改（含确定性兜底）
  → repo.save_attempt() 入库为练习证据                 # exercise_attempts
  → _record_diagnostic() → diagnostic_worker          # 练习证据被 V2 诊断消费
```

- LLM 挑选失败（3 次尝试内校验不通过）会回落到 `_deterministic_select()` 的确定性选择，
  保证功能可用；若连候选都没有，草稿标记 `failed`。
- `SELECTION_USES` 是模型可选语义白名单（diagnostic / remedial / verify / advance 等），
  `_validate_selection` 对 purpose、目标概念、证据引用逐项强校验，不在白名单直接拒绝。
- 候选集只来自已审核教材题池：`agents.build_draft` 显式 `include_machine=False`（MVP 关闭 AI 生成），
  另挂一道教材例题（worked_example）用于第三级提示后的补救讲解。

## 会话生命周期

- draft：`queued → running → ready / failed`，支持 stale 标记与 recover 重入队；
- session：`active → completed / inconclusive`；不可批改的作答最多重试 2 次后判定
  `inconclusive`（掌握不可判定），不会硬给结论；
- 提示三级递增，第三级提示后展示同概念的教材例题（worked_example）；
- 重新生成（`regenerate`）基于父草稿 + 版本 nonce，避免重复命中同一上下文哈希
  （`context_hash` 去重）。

## 批改与防重复

- `_grade` 用独立 LLM 批改器（`EXERCISE_GRADER_MODEL`）给出 `correct / partial /
  incorrect / ungradable` 四档，并抽取学生原文证据引文；LLM 不可用时回落确定性关键字批改。
- 同一草稿按 `context_hash` 幂等复用；会话内已作答题目（attempted 集合）不会再进候选。

## 路由接线

`app/routers/practice.py` 暴露 draft 创建 / 查询、session 开始、作答提交（submit）、
三级提示（hint）与重新生成（regenerate）端点；worker 与 diagnostic 均为后台任务，
不占请求路径。

## 质量门

`quality.py` 提供确定性质量门（`validate_item` / `verify_item_math`）与 JSON 解析
（`parse_json_object`，service 与 intervention 共用）；`kg_validation.py` 做教材 KG
映射的硬边界校验（概念必须在教材章节范围内、前置必须一跳可达）。

## 依赖

- `services/intervention`：练习是干预载体（`create_from_intervention` 由干预动作触发；
  干预会标记旧草稿 stale 并把 `intervention_action_id` 回写草稿）；
- `services/diagnosis`：练习作答作为 `exercise_attempt` 证据被 V2 分源评分消费
  （`diagnostic_worker.run_diagnostic_for_user`）。

## 后续计划导航

- [`docs/practice-v2-deferred-todo.md`](../../../docs/practice-v2-deferred-todo.md)：V2 延后事项
- [`docs/practice-mvp-test-todo.md`](../../../docs/practice-mvp-test-todo.md)：MVP 测试待办

## 思路变动历史

- 2026-08-07：自适应教材练习 MVP 落地（仅从已审核教材题池选题，AI 生成关闭）。
