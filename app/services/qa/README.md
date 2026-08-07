# app/services/qa/ — QA 回答模块

## 为什么存在

处理「学生在教材某一页上的提问」，产出带教材出处（sources）与 KG 概念锚点的流式回答。
整个模块只做一件事：**把一次提问变成可追溯的回答记录**，不改学生长期画像、不触发诊断。

## 主链路（text 输入）

```text
QATurnInput（文本）
  → grounding_service.ground_text_turn()      # KG 定位：教材页 → section → 概念/前置/规则案例
  → intervention_service.compose_for_turn()   # 组装学生状态 + 教学策略（兜底走 tutor_policy.decide_tutor_policy）
  → scaffolding_controller.determine_level()  # 计算脚手架层级，写入 QATurnRecord
  → prompt_builder.build_tutor_prompt()       # 统一 prompt（whitelist + 证据 + 策略 + 历史）
  → llm_service.stream_chat()                 # LLM 流式，token 直接 yield 给 SSE 路由
  → 回答结束：StreamBus.emit(done)
       ├── start_persist_consumer()           # 异步持久化 QATurnRecord（不阻塞 SSE）
       └── listen_qa_done()                   # 诊断模块订阅，自行触发 V2 诊断
```

注意：回答 token 是通过 async generator **直接**交给 SSE 路由（`app/routers/qa.py`）的；
`StreamBus`（`event_bus.py`）是每轮结束时的 per-turn 小总线，只广播「完成」信号给异步消费者，
不承担正文转发。

## 截图（vision）链路

`vision_extraction.extract_vision_problem()` 先从截图可信提取题目（带版本号
`VISION_EXTRACTION_VERSION`，与截图缓存联动避免重复识别）；识别足够可靠时走
`answer_turn_with_tools()`（复用 agents 的 ToolRuntime，支持工具调用与可视化），
否则回退到直接结合图片的 `_answer_vision_direct()`。

## 三个关键边界（为什么这样设计）

1. **不触发诊断**：QA 只负责回答 + 写 `QATurnRecord`。诊断由
   `app/services/diagnostic_worker.py::listen_qa_done` 订阅 StreamBus 的 done 事件**自行**触发，
   QA 不知道也不关心诊断何时跑。
2. **只读 Stage**：`tutor_policy` / prompt 构造只读 `StudentStateSummary`
   （来自 `diagnosis/contracts.py`）来调整讲解风格，**只读不写**——不更新 stage、不生成诊断结论。
3. **生产消费解耦**：持久化在独立 task 中执行，`persist_done` 不阻塞 SSE 响应；
   持久化失败不会拖垮回答流。

## SSE 事件类型

`streaming_service.py` 统一产出 `{event, data}` 事件：`stage`（搜索/规划/生成各阶段提示）、
`content`（正文 token）、`done`（完整回答 + sources + 工具统计）、`error`、
`heartbeat`（路由层每 15s 注入防超时）、`tree_turn_started`（树对话）、
`tool_call` / `tool_result` / `visualization`（工具调用链路，见 `agents/README.md`）。

## 记录与失败兜底

- `turn_store.save_turn_record()` 写 `qa_turn_records`（完整 `context_snapshot` 快照），
  同时兼容写旧 `chat_logs` / `chat_history`。
- 回答中途异常时兜底生成带 `error` 字段的 `QATurnRecord`，并 `yield sse_error`，
  保证前端能拿到明确错误而不是挂起。

## 选路与超时

- 路由层按是否有截图上下文选路：有截图走 image / mixed 输入，否则走 text。
- `QAAgent` 按输入类型套用超时（`QA_TEXT_TURN_TIMEOUT_SECONDS` /
  `QA_SCREENSHOT_TURN_TIMEOUT_SECONDS`，0 表示不限），超时 `yield sse_error`。
- 树对话：路由层通过 `client_turn_id` / `node_id` 开启树对话（`app/db/chat_tree_db.py`），
  由服务端构建 `authorized_history`，客户端历史不作为信任输入。

## 文件职责

| 文件 | 职责 |
|------|------|
| `answer_service.py` | 主编排：text / vision 两条链路 + 工具化入口 `answer_turn_with_tools` |
| `grounding_service.py` | 把提问定位到教材页 / section / KG 节点（只读） |
| `prompt_builder.py` | 统一 prompt 构造（`build_tutor_prompt` / `build_lightweight_prompt` / `build_vision_prompt`） |
| `tutor_policy.py` | 基于 `StudentStateSummary` 的保守策略兜底 |
| `contracts.py` | 数据契约：`QATurnInput` / `QATurnRecord` / `QAStreamEvent` 等 |
| `event_bus.py` | per-turn `StreamBus`，解耦生产与消费 |
| `streaming_service.py` | SSE 事件序列化辅助 |
| `turn_store.py` | `QATurnRecord` 异步持久化 |
| `vision_extraction.py` / `vision_context_service.py` | 截图题目提取 + PDF 截图上下文准备 |

## 依赖规则

- 模块间传 `contracts.py` 里的 dataclass，不传裸 dict。
- 可**只读**引用 `diagnosis/contracts.py` 的 `StudentStateSummary`、`KGContext`、
  `TurnGrounding`、`WeakPrerequisite` 等契约；不得反向 import 诊断的服务函数。
- 教学策略的实际组装来自 `services/intervention`（干预指令），QA 侧 `tutor_policy`
  只是它的兜底路径。
- 完整链路约束见 `docs/design/diagnosis-README.md` 与
  `docs/adr/ADR-001-qa-diagnosis-decouple.md`。

## 思路变动历史

- 2026-07-22：Phase 1+2 — 引入 `StreamBus` 事件总线 + Agent 统一接口，SSE 格式统一。
- 2026-07-23：Phase 3+4 — 持久化异步化（`start_persist_consumer`）+ 诊断实时触发
  （`listen_qa_done`），回答流不再被落盘阻塞。
- 2026-07-24：工具调用架构落地，SSE 事件扩展 `tool_call` / `tool_result` / `visualization`
  （详见 `agents/README.md`）；`QAStreamEvent` 同步预留 `practice_draft` 事件类型。
