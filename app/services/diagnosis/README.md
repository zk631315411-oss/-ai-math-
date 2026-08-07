# app/services/diagnosis/ — 认知诊断模块（V2）

## 为什么存在

把「学生说了什么 / 做了什么」变成**可审计**的长期画像（概念 Stage + 15 维数学素养）。
V1 是混合单次 LLM 直接改画像，不可审计；V2 改为**分源评分、统一入账、确定性投影**，
每条画像更新都能追溯到具体证据。

## V2 架构一句话

```text
qa_turn_records / exercise_attempts
  → adapters.py       # QA / 练习独立适配，产出 QAEvidenceInput / ExerciseEvidenceInput
  → scorers.py        # 4 个独立评分器：qa_stage / qa_dimension / exercise_stage / exercise_dimension
  → diagnostic_evidence   # 统一证据账本（app/db/diagnosis_v2_db.py）
  → projectors.py     # Stage 投影器 → knowledge_stages；素养投影器（同章节五事件窗口）→ math_profiles
```

- **分源评分**：四个评分器各自独立 Prompt、Schema、版本号（`SCORER_VERSION` /
  `PROMPT_VERSION`），一个来源失败不影响另一个。
- **确定性投影**：`certain=1.0` / `probable=0.5` 权重；第一条强反证只降置信度，
  两条不同事件的强反证才降一级（demote）；素养需要同章节五个不同事件、分面至少 3 个观察、
  同向权重 ≥ 2/3 且 ≥ 2.0 才调整一级。
- 证据强度分 `certain` / `probable` / `hypothesis`；`hypothesis` 只入账，不进长期画像。
- 编排：`v2_service.py` 负责评分运行状态（幂等去重、`ObservationValidationError` 拒绝入账）；
  后台消费由 `app/services/diagnostic_worker.py` 承担。

## 契约与评分要点

`contracts.py` 定义分源输入（`QAEvidenceInput` / `ExerciseEvidenceInput`）与统一观察
（`StageObservation` / `DimensionObservation` / `DiagnosticSignal`）。

- QA Stage：普通提问只记 `hypothesis`；定义复述最高 2；提示下应用最高 3；
  证明最高 4；独立解释、迁移与反例最高 5。
- 练习 Stage：题目不预设学生 Stage，只按学生原文展示的行为判断；使用提示最高 3；
  只有最终答案最高 `probable`；Stage 5 必须展示迁移、反例或解释行为。
- 引文必须是学生原文 / 学生答案的精确子串；Stage 概念必须逐字命中 KG，
  KG 为空时不产生 Stage 观察。

## 审计三件套

`diagnosis_runs`（每次评分运行）、`diagnostic_evidence`（证据账本）、
`state_projection_log`（每次投影的前后值）共同提供幂等、审计和离线重放能力。

## 发布档位

`DIAGNOSIS_V2_MODE` 控制：`shadow`（当前，默认）→ `stage_only` → `full`。
- `shadow`：只评分 + 存证据，**不改任何画像**；
- `stage_only`：开启 Stage 投影，素养仍只记证据；
- `full`：再开启同章节五事件素养聚合。

## 影子消费者：对话概率状态

`dialogue_state.py` 是证据账本旁的独立影子消费者（表 `dialogue_knowledge_states`），
只消费已校验的 QA Stage 证据，为「用户-知识点」维护 Stage 0-5 概率分布（ordinal-bayes）；
**不读写 `knowledge_stages`、不进 QA Prompt / 画像 API / 前端，只记录不生效**。
由 `DIALOGUE_STATE_MODE=off|shadow` 控制，默认 shadow；模型版本由
`DIALOGUE_STATE_MODEL_VERSION` 固定，在线更新与离线重放用同一公式，结果可复现。
模型给出 `accepted|abstained` 语义决定（含同义改写 / 跨轮提示 / 复述 AI 的独立性判断），
程序只对 `accepted` 且独立证据更新分布；`supporting` 证据由程序强制弃权。

## 离线重放

- 对话概率状态支持按用户离线重放（`replay_dialogue_states`），以用户为事务边界，
  异常时该用户原状态完整回滚；`get_dialogue_state` 读取当前分布。
- Stage / 素养投影同样可从 `state_projection_log` 追溯，每次投影记录 before/after。

## 与干预的衔接

评分完成后 `v2_service` 会发布快照给 `services/intervention`（`publish_snapshot`）；
快照发布失败不影响诊断，诊断证据仍是权威。

## 版本与归档

- V1 已归档到 `app/legacy/diagnosis_v1/`，仅历史审计；`app/db/math_profile_standard.py`
  等保留薄兼容桥，但不得恢复 V1 的混合 Prompt 或直接写画像。
- **V2 是唯一允许更新画像的路径。**

## 与 QA 的关系

- QA 只读本模块契约（`StudentStateSummary` / `KGContext` / `TurnGrounding`）调整回答风格；
- QA 不触发诊断：`diagnostic_worker.listen_qa_done()` 订阅 StreamBus 的 done 事件自行触发。
  依赖方向见 `docs/adr/ADR-001-qa-diagnosis-decouple.md`。

## 详细设计导航

本 README 只做导航，不重复内容。数据流、分源评分规则、校验与状态更新策略的完整说明见
[`docs/design/diagnosis-README.md`](../../../docs/design/diagnosis-README.md)；
待办见 [`docs/design/diagnosis-TODO.md`](../../../docs/design/diagnosis-TODO.md)。

## 思路变动历史

- V1 归档：`app/legacy/diagnosis_v1/`，旧路径只留审计与薄兼容桥。
- 2026-08-02：V2 shadow 上线 + 对话概率状态（`dialogue_state.py`）落地。
