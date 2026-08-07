# app/services/agents/ — Agent 层

## 为什么存在

把 QA / 练习等业务能力收敛到「统一流式接口 + 注册表」的 Agent 编排层，
并在其上落地**有界、可观测的 function calling 运行时**（工具调用三重边界），
避免模型在工具循环里失控。

## 组成

| 文件 | 职责 |
|------|------|
| `base.py` | `BaseAgent`：统一 `run()` 流式接口 + `get_tools()` 扩展点 |
| `registry.py` | `AGENT_REGISTRY`：注册 / 查询 / 列表 / 清空 |
| `qa_agent.py` | `QAAgent`（name="qa"）：把 `answer_turn[_with_tools]` 适配为统一接口 |
| `exercise_agent.py` | `ExerciseAgent`（占位，尚未对接流式接口） |
| `tool_def.py` | `ToolDef`：工具定义 + 参数校验 + 单轮/单轮次调用上限 |
| `tool_executor.py` | `prepare_tool_call` / `execute_prepared_tool_call` |
| `tool_runtime.py` | `ToolRuntime`：有界可观测的工具循环，产出 `RuntimeEvent` |
| `tools/` | 4 个 QA 工具：search_textbook / lookup_kg_node / verify_math / create_math_visualization |

## ToolRuntime：有界可观测

`ToolRuntimeConfig` 三道硬边界（默认值，可由环境变量覆盖，见 `app/config.py`）：
- `max_model_rounds=5`：模型最多 5 轮工具循环；
- `max_total_calls=8`：整轮最多 8 次工具调用；
- `max_consecutive_failure_rounds=2`：连续 2 轮失败即降级收尾。

超出边界进入降级收尾（`degraded`，`degradation_code`：
`tool_budget_exceeded` / `tool_failures` / `tool_round_limit`）：强制模型只用已有结果
收尾回答，并以 `tool_choice=none` 阻止继续调用工具。

`RuntimeEvent` 四种类型：`tool_call` / `tool_result` / `visualization` / `final`；
同参调用按 fingerprint 去重，防止模型重复调用同一工具。每轮还有单工具上限
（`ToolDef.max_calls_per_round` / `max_calls_per_turn`，默认 3）。

**参数校验在执行前**：`ToolDef.validate_arguments` 用 pydantic `input_model` 强校验，
非法参数转为 error 结果并**计入失败轮次**（连续 2 轮失败即降级收尾）。

**可视化是工具产物**：`create_math_visualization` 返回的 artifact 经 `artifact_handler`
挂到工具结果上，由 `app/services/visualization/` 校验与入库（详见 `visualization/README.md`）。

## Registry 用法

```python
from app.services.agents import register, get_agent, list_agents

register(QAAgent())              # 同名覆盖旧实例
agent = get_agent("qa")          # 未注册时 raise KeyError
summary = list_agents()          # [{name, description}, ...]
```

当前 `app/routers/qa.py` 直接引用 `QAAgent`（`QAAgent().run()`），注册表是路由解耦的
目标机制，目前尚无生产调用点。`ExerciseAgent` 是占位实现，尚未对接流式接口。

## 边界

- Agent 层不碰业务数据：工具只读 KG / 教材，可视化产物走 artifact 通道落库。
- 具体 Agent 实现（`QAAgent` / `ExerciseAgent`）不应被业务 service 反向依赖：
  目前只有路由层引用 Agent，service 层仅惰性引用 `ToolRuntime` 原语。

## 设计动机

QA 原本只有 `answer_turn` 一个流式入口、练习是另一套非流式调用；Agent 层把它们统一为
`BaseAgent.run()` 流式接口，为后续任意 Agent 编排留出扩展点。工具调用侧则要防止模型
在循环里失控（无界调用 / 重复调用 / 连环失败），所以全部收敛到有边界的 `ToolRuntime`。

## 详细设计导航

- [`docs/notes/agent-design-lesson.md`](../../../docs/notes/agent-design-lesson.md)：Phase 1 设计备忘
- [`docs/design/tool-calling-architecture.md`](../../../docs/design/tool-calling-architecture.md)：工具调用架构设计

## 思路变动历史

- 2026-07-22：Phase 1+2 — `BaseAgent` 统一接口 + Registry 注册表 + StreamBus 事件总线。
- 2026-07-24：工具调用架构落地 — `ToolDef` / `ToolExecutor` / 3 个工具 / Agent 循环；
  后续补充 `create_math_visualization` 工具与 `ToolRuntime` 运行时。
