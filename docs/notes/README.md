# docs/notes/ 备忘录索引

本目录存放架构设计与实现过程中的**思路备忘录**，记录"为什么这么设计"的决策过程，以及对外部系统的借鉴分析。

## 文件列表

| 文件 | 内容 | 对应阶段 |
|------|------|----------|
| `stream-bus-lesson.md` | StreamBus 事件总线设计思路——借鉴 DeepTutor 的 per-turn asyncio.Queue 解耦方案 | Phase 2-4 |
| `agent-design-lesson.md` | Agent 系统设计思路——BaseAgent 统一接口 + Registry 注册表 | Phase 1 |

## Phase 1-4 落地映射表

从备忘录到代码的实现追踪：

| 备忘录建议 | 对应代码 | Phase |
|-----------|---------|-------|
| 定义 Agent 统一接口 | `app/services/agents/base.py` | Phase 1 |
| Agent 注册表 | `app/services/agents/registry.py` | Phase 1 |
| 封装 QAAgent | `app/services/agents/qa_agent.py` | Phase 1 |
| 封装 ExerciseAgent（占位） | `app/services/agents/exercise_agent.py` | Phase 1 |
| 事件类型标准化 | `app/services/qa/contracts.py` — `QAStreamEvent` 枚举 | Phase 2 |
| 引入 StreamBus | `app/services/qa/event_bus.py` | Phase 2 |
| SSE 格式统一 | `app/services/qa/streaming_service.py` — `sse_format()` | Phase 2 |
| 持久化异步化 | `app/services/qa/turn_store.py` — `start_persist_consumer()` | Phase 3 |
| 诊断实时触发 | `app/services/diagnostic_worker.py` — `listen_qa_done()` | Phase 4 |
| Function Calling 预留 | `BaseAgent.get_tools()` 返回空列表，`QAStreamEvent` 预留 `tool_call`/`tool_result` | 预留 |
| 统一 /chat 入口 | 待后续 | 未开始 |

### Phase 说明

- **Phase 1**：Agent 框架搭建 — BaseAgent 统一接口、Registry、QAAgent/ExerciseAgent 封装。不改变现有 service 内部实现，只在外层包一层。
- **Phase 2**：StreamBus 事件总线引入 — `answer_turn` 内部用 `bus.emit()` 替代直接 `yield`，路由端 `subscribe` 消费。事件类型标准化。
- **Phase 3**：持久化异步化 — `save_turn_record` 从串行阻塞改为独立的 `persist_consumer`，通过 StreamBus 订阅 `DONE` 事件异步执行。
- **Phase 4**：诊断实时触发 — 诊断模块从 30s 轮询 DB 改为监听 StreamBus 的 `qa_completed` 事件，实时触发诊断流水线。

详细设计见 [`stream-bus-lesson.md`](./stream-bus-lesson.md) 和 [`agent-design-lesson.md`](./agent-design-lesson.md)。
