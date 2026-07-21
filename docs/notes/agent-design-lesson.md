# Agent 系统设计思路借鉴

## DeepTutor 的做法（一句话总结）

通过 `CapabilityRegistry` 注册表 + `BaseCapability` 统一接口 + `StreamBus` 事件总线，实现"一个 Agent 解决一类问题"，并通过 AutoCapability 作为元 Agent 进行意图路由和组合。

---

## 我们项目当前的情况

### 没有显式的"Agent"概念

ai-math 当前的架构是**服务导向**（Service-Oriented），而非 Agent 导向：

- **入口是 router**：`/api/qa/solve-stream`、`/api/exercise/generate` 等端点直接调用服务函数
- **服务是编排函数**：`answer_turn()`、`generate_exercise()` 等，内部顺序调用多个 helper 函数
- **没有注册表**：每个功能直接调用对应的 service，没有按名称获取的机制
- **没有统一接口**：不同功能的签名各异（`answer_turn(QATurnInput)`、`generate_exercise(ExerciseGenerateRequest)`）

### 实际上有类似 Agent 的雏形

虽然没有显式 Agent，但项目已经按**问题类型**划分了独立模块：

| 功能 | 入口文件 | 核心服务 | 类似 Agent 的地方 |
|------|----------|----------|-------------------|
| 问答 | `routers/qa.py` | `answer_turn()` | 已有 `input_type` 分流（text/vision） |
| 出题 | `routers/exercise.py` | `generate_exercise()` | 有独立的 prompt 构建和验算流程 |
| 诊断 | `services/diagnostic_worker.py` | `run_diagnostic_batch()` | 后台消费 QA 记录，异步执行 |

**关键区别**：这些是"服务模块"，不是"可组合的 Agent"。路由直接调用服务，没有中间层做意图识别或委托。

### 数据契约已经具备

`contracts.py` 里定义了 `QATurnInput`、`QATurnRecord`、`StudentStateSummary` 等 dataclass，这是 Agent 模式的前置条件。模块间已经通过 dataclass 通信，而非裸 dict。

---

## 可以借鉴的点

### 1. 统一入口 + 意图路由

**现状**：前端需要知道调用哪个端点（`/api/qa/solve-stream`、`/api/exercise/generate`）。

**借鉴**：可以加一个 `/api/chat` 统一入口，由 Agent 判断用户意图（问答/出题/诊断报告），然后委托给对应 Capability。

```python
# 伪代码
@router.post("/chat")
async def unified_chat(request: ChatRequest):
    intent = await detect_intent(request.message)  # "qa" / "exercise" / "diagnosis"
    agent = agent_registry.get(intent)
    async for event in agent.run(request):
        yield event
```

### 2. Capability 层薄化 + 逻辑下沉

**现状**：`answer_service.py` 有 600+ 行，包含 KG 定位、prompt 构建、流式输出、记录持久化等所有逻辑。

**借鉴**：DeepTutor 的 Capability 文件只有 20-30 行，只做参数传递。可以把 `answer_service.py` 拆成：
- `QAAgent`（薄层）：注册 + 参数转换
- `qa_pipeline/` 目录：`grounding.py`、`prompt_builder.py`、`streaming.py` 等

### 3. Agent 之间通过事件解耦

**现状**：诊断模块通过 `diagnostic_worker.py` 后台消费 `QATurnRecord`，但这是硬编码的消费关系。

**借鉴**：可以引入轻量事件总线，QA 完成后发布 `QATurnCompleted` 事件，诊断 Agent 订阅处理。未来还可以加"错题推荐"、"知识点复习"等订阅者。

```python
# 伪代码
await event_bus.publish("qa_turn_completed", turn_record)
# 诊断、推荐、统计等 Agent 各自订阅并处理
```

### 4. 可复用的 Agent 注册表

**现状**：如果要新增一个"错题本导出"功能，需要新建 router + service，前端单独调用。

**借鉴**：可以维护一个 `AGENT_REGISTRY` 字典，按名称获取 Agent。这样：
- 新增 Agent 只需注册，不用改 router
- 可以通过配置决定启用哪些 Agent
- 方便测试时 mock 特定 Agent

### 5. Auto Agent 作为总调度器

**现状**：如果用户说"给我出一道行列式的题"，前端需要自己判断调用 `/api/exercise/generate`。

**借鉴**：加一个 `AutoAgent`，分析用户消息，识别意图后委托给 `QAAgent` 或 `ExerciseAgent`。类似于 DeepTutor 的 `AutoCapability`。

---

## 不建议照搬的地方

### 1. 不需要 8 个 Capability + 4 个独立 Agent

DeepTutor 面向通用对话，有 `deep_solve`、`deep_research`、`visualize`、`math_animator` 等。

ai-math 是垂直的数学学习场景，核心只需要：
- **QAAgent**：问答（已有）
- **ExerciseAgent**：出题（已有）
- **DiagnosisAgent**：认知诊断（已有后台 Worker）
- **可选的 AutoAgent**：意图路由

### 2. 不需要复杂的 StreamBus

DeepTutor 的 `StreamBus` 用于多 Agent 协作时的消息广播。

ai-math 目前是单轮问答，没有"多 Agent 并行协作"的场景。简单的 asyncio Queue 或直接调用即可。

### 3. 不需要上下文切换机制

DeepTutor 通过 `context.active_capability` 切换当前 Agent，是因为对话可能跨多个 Agent。

ai-math 的每轮对话是独立的，用户不会在同一个 session 里"先问问题、再出题、再生成动画"。

---

## 建议的落地方式

### 第一步：定义 Agent 接口（不破坏现有代码）

在 `app/services/` 下新建 `agents/` 目录：

```python
# app/services/agents/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator, Any

class BaseAgent(ABC):
    name: str  # 唯一标识
    
    @abstractmethod
    async def run(self, input: Any, stream: bool = True) -> AsyncIterator[dict]:
        """统一入口，返回 SSE 事件流"""
        pass
```

### 第二步：封装现有服务为 Agent

不改动现有 `answer_service.py`，只在外面包一层：

```python
# app/services/agents/qa_agent.py
class QAAgent(BaseAgent):
    name = "qa"
    
    async def run(self, input: ChatInput, stream: bool = True) -> AsyncIterator[dict]:
        qa_input = QATurnInput(...)  # 参数转换
        async for event in answer_turn(qa_input):
            yield event
```

### 第三步：加注册表

```python
# app/services/agents/registry.py
AGENTS = {
    "qa": QAAgent(),
    "exercise": ExerciseAgent(),
}

def get_agent(name: str) -> BaseAgent:
    return AGENTS.get(name)
```

### 第四步：加统一入口（可选）

```python
# app/routers/chat.py
@router.post("/stream")
async def unified_chat(request: ChatRequest):
    # 简单版：根据显式参数选择 Agent
    agent = get_agent(request.agent or "qa")
    # 进阶版：加意图识别，委托给 AutoAgent
    ...
```

### 第五步：事件驱动（更远期）

QA 完成后发布事件，诊断 Agent 订阅：

```python
# 在 QAAgent.run 结束时
await event_bus.publish("qa_completed", turn_record)
```

---

## 总结

| 维度 | 当前 | 目标 |
|------|------|------|
| 入口 | 多个独立端点 | 统一 `/chat` + 意图路由（可选） |
| 服务层 | 直接调用函数 | 通过 Agent 注册表获取 |
| 服务代码 | 600 行大函数 | 薄 Agent 层 + 拆分的 pipeline |
| 模块通信 | 直接调用 + 后台任务 | 事件发布/订阅（可选） |
| Agent 数量 | N/A | 2-3 个核心 Agent + 1 个可选的 AutoAgent |

**核心收益**：让系统更易扩展、易测试、易替换，同时保持现有架构不变。

---

## 参考文件

- `D:\ai-math\ARCHITECTURE.md` — 架构规则和模块依赖
- `D:\ai-math\app\services\qa\answer_service.py` — QA 主编排入口（600+ 行）
- `D:\ai-math\app\services\qa\prompt_builder.py` — Prompt 构造器
- `D:\ai-math\app\services\qa\contracts.py` — QA 数据契约
- `D:\ai-math\app\routers\qa.py` — QA 路由端点
- `D:\ai-math\app\routers\exercise.py` — 出题路由端点
- `D:\ai-math\app\routers\chat.py` — 聊天历史 API
- `D:\ai-math\app\services\diagnosis\contracts.py` — 诊断模块数据契约
- `D:\ai-math\app\services\diagnostic_worker.py` — 后台诊断 Worker