# 认知诊断模块 V2

## 版本状态与归档

V1 已归档，不再属于运行时诊断路径。它的模式是“聊天记录 -> 单个混合 LLM -> 单轮 Stage/15维 delta -> 直接写画像”，原始实现保留在 `app/legacy/diagnosis_v1/` 供历史审计；旧模块中的直接证据写入入口已禁用。

V2 是唯一允许生产画像更新的架构：QA 与练习分别评分，先写入证据账本，再由确定性投影器更新长期状态。旧导入路径保留薄兼容桥，但不得恢复 V1 的混合 Prompt 或直接写画像。

当前发布档位为 `shadow`：V2 会保存运行记录和证据，但不会改 Stage 或15维画像。切换顺序固定为 `shadow -> stage_only -> full`：先人工抽查真实证据和 Stage 投影日志，再开启15维五事件聚合。

## 定位

诊断模块只生产长期画像：概念 Stage 与 15 维数学素养。即时认知卡点暂由 QA 根据当前输入和长期画像处理，诊断模块不控制 QA，也不进入本轮回答延迟链路。

核心原则：**QA 与练习分别建模、分别评分；评分结果统一入账；Stage 和素养分别投影。**

## 数据流

```text
qa_turn_records -> QA适配器 -> QA Stage评分器 / QA素养评分器
exercise_attempts -> 练习适配器 -> 练习Stage评分器 / 练习素养评分器

四路观察 -> diagnostic_evidence
StageObservation -> Stage投影器 -> knowledge_stages
DimensionObservation -> 同章节五事件窗口 -> math_profiles
```

`answer` 是 AI 输出，只能作为帮助上下文，不能作为学生能力证据。QA 当前学生文本的帮助程度取同一 `chat_id` 的上一轮 `apprenticeship_level`。

## 分源评分

- QA Stage：普通提问只记 hypothesis；定义复述最高 Stage 2；提示下应用最高 Stage 3；独立解释与证明最高 Stage 4；迁移和反例最高 Stage 5。
- 练习 Stage：目标 Stage 是上限；使用提示最高 Stage 3；只有最终答案最高 probable；Stage 5 必须有迁移、反例或解释行为。
- 普通 `solution_attempt` 最高 Stage 3；Stage 4 必须引用学生针对该概念的解释、条件关系或证明。
- Stage 候选携带 KG 节点 ID、类型和候选间关系。只有共用同一证据的 `PART_OF` 父节点会降为 supporting；`USES/GETS` 不代表掌握继承，也不自动去重。
- QA 素养：只评价学生原文，普通提问和未出现维度为 `not_observed`。
- 练习素养：结合题型、学生步骤、正确性和提示次数，禁止由题目或标准答案反推学生能力。

四个评分器使用独立 Prompt、Schema 和版本号。

## 校验与状态更新

- 引用必须是学生原文或学生答案的精确子串。
- Stage 概念必须逐字命中 KG；KG 为空时不产生 Stage 观察。
- 单条 `certain` 正证据可以初始化或晋升 Stage。
- supporting Stage 观察保留在证据账本并写入 `suppressed` 投影日志，但不修改正式 Stage、置信度或反证计数。
- 第一条强反证只降置信度；两条不同事件的强反证才降一级。
- 单条维度观察不更新画像；同章节累计五个不同事件后，每个分面至少三个事件、同向权重至少三分之二且达到 2.0 才调整一级（certain=1.0，probable=0.5）。
- `diagnosis_runs`、`diagnostic_evidence` 和 `state_projection_log` 提供幂等、审计和离线重放能力。

## 发布档位

通过 `DIAGNOSIS_V2_MODE` 控制：

- `shadow`：默认，只运行评分并保存证据，不修改画像。
- `stage_only`：开启 Stage 投影，素养仍只记证据。
- `full`：开启 Stage 和同章节五事件素养聚合。

旧画像保留为 `legacy_v1` 基线，新更新标记 `projection_version=v2`。

## 主要文件

- `contracts.py`：分源输入和统一观察契约。
- `adapters.py`：QA/练习独立适配。
- `scorers.py`：四个独立评分器及来源专属校验。
- `v2_service.py`：评分编排与运行状态。
- `projectors.py`：Stage 与 15 维确定性投影。
- `app/db/diagnosis_v2_db.py`：事件、运行、证据和审计存储。
