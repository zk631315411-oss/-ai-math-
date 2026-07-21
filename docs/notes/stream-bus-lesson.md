# StreamBus 思路借鉴备忘录

## DeepTutor 的做法（一句话总结）

DeepTutor 的 StreamBus 是一个 per-turn 的 `asyncio.Queue` 事件总线：Agent 只管 emit 语义事件（CONTENT / THINKING / TOOL_CALL / ERROR / WAIT_FOR_INPUT 等），不关心谁在消费；CLI、WebSocket、日志模块各自 subscribe，新订阅者先收到历史快照回放，支持双向等待用户输入。

## 我们项目当前的情况

当前 ai-math 的流式响应模式是**函数内直接 yield dict**：

- `answer_service.py` 的 `answer_turn()` 是一个 `AsyncIterator[dict]`，内部直接 `yield sse_stage(...)`、`yield sse_text(...)`、`yield sse_done(...)` 推送给**唯一消费者**——SSE 路由。
- `routers/qa.py` 直接 `async for event in answer_turn(...): yield event`，没有中间总线，也没有多消费者。
- `exercise.py` 的流式出题也是类似的模式：在 `stream()` 闭包内直接 `yield f"data: ..."`，硬编码 SSE 格式。
- `turn_store.py` 的持久化（写入 DB、更新 chat_logs、更新 chat_history）是在 `answer_turn()` 结尾**同步阻塞地**调 `save_turn_record()`，与流式输出串行。
- 诊断模块（`diagnostic_worker.py`）通过**轮询 DB 表**来消费 QATurnRecord，不是实时事件驱动。

### 痛点

| 痛点 | 具体表现 |
|------|----------|
| **单消费者耦合** | `answer_turn()` 产出的每个 dict 只有 SSE 路由消费；如果以后想加 WebSocket、日志流、实时诊断，需要改 `answer_turn` 本体 |
| **持久化阻塞流式** | `save_turn_record()` 在 answer 生成完才同步执行，写 DB / 写 chat_logs 的耗时直接增加用户等待 |
| **诊断延迟高** | 诊断 Worker 每 30s 轮询 DB，不是实时触发。一轮 QA 结束后最快 30s 后才能更新学生状态 |
| **事件格式不统一** | `qa.py` 的 SSE 事件走 `dict` + `json.dumps`，`exercise.py` 走 `f"data: {json.dumps(...)}\n\n"` 字符串拼接，两套格式 |
| **无历史重放** | 新消费者（如 WebSocket 新连接）无法获取之前的事件历史，除非自己去查 DB |
| **双向通信缺失** | 无法实现 Agent 暂停等待用户输入的场景（如苏格拉底式追问需要等待学生回答后再继续） |

## 可以借鉴的点

### 1. 事件类型标准化 → 统一 event 枚举

当前 `QAStreamEvent` 只有 `stage / content / thinking / done / error / heartbeat` 五个事件类型。可以扩展成 StreamBus 风格：

```
TEXT_CHUNK / THINKING_CHUNK / TOOL_CALL / TOOL_RESULT
STAGE_CHANGE / PROGRESS / SOURCES / ERROR
DONE / WAIT_FOR_INPUT / HEARTBEAT
```

好处：`prompt_builder` 调用了 KG 定位、策略决策等多个子步骤，每个步骤都可以 emit 对应的语义事件，前端可以针对性地渲染（比如 TOOL_CALL 显示加载状态、THINKING 显示思考过程面板）。

### 2. 引入 asyncio.Queue 解耦生产者与消费者

`answer_turn()` 不再直接 `yield`，而是往一个 `asyncio.Queue` 里 put 事件：

```python
# 当前：生产者直接 yield
async for token in stream:
    yield sse_text(token)

# 改为：生产者 emit 到总线
bus = StreamBus()
# 在 answer_turn 内部：
bus.emit(QAStreamEvent("content", {"text": token}))
# 路由端：
async for event in bus.subscribe():
    yield event
```

这样路由、WebSocket、日志模块可以各自独立 subscribe。

### 3. 持久化从串行改为事件驱动

`save_turn_record()` 当前阻塞在 `answer_turn` 末尾。改为 emit 一个 `DONE` 事件，由独立的持久化消费者异步处理写 DB / 写 chat_logs，不阻塞 SSE 响应。

```python
# 在总线侧注册持久化消费者
bus.subscribe("persistence", handle_persist)
```

### 4. 实时诊断触发器

诊断模块不再轮询 DB，而是通过总线监听 `DONE` 事件后直接触发诊断流水线：

```python
bus.subscribe("diagnosis", lambda event: asyncio.create_task(run_diagnostic_batch(user_id)))
```

### 5. 事件历史快照支持新订阅者重放

`StreamBus` 内部维护一个 `deque` 存储最近 N 个事件（或本轮所有事件）。新 subscribe 时先把历史快照发一遍，解决 WebSocket 重连或日志迟到的场景。

## 不建议照搬的地方

| DeepTutor 的做法 | 我们不需要照搬的理由 |
|-----------------|-------------------|
| **per-turn 的 Queue 实例** | 我们每轮 QA 本身就是 `answer_turn()` 一次调用，生命周期清晰，可以照搬 |
| **12+ 事件类型** | 我们当前只需要 5-8 个事件类型（stage, content, thinking, done, error, heartbeat, wait_for_input）。TOOL_CALL / TOOL_RESULT 等事件在我们目前纯 LLM 回答的场景下意义不大，除非将来引入 Agent 式的多步骤推理 |
| **WAIT_FOR_INPUT 双向通信** | 当前架构是纯 SSE（服务端推送），没有反向通道。如果要实现苏格拉底追问需要学生回答，前端需要另发一个 HTTP 请求回传答案，不是 StreamBus 能单独解决的 |
| **多消费者无限订阅** | 当前实际消费者只有 SSE 路由 + 未来可能的 WebSocket。过度设计会导致不必要的复杂度。建议先支持 2-3 个消费者（SSE、持久化、诊断），预留扩展接口 |

## 建议的落地方式

### 轻量方案：不引入新依赖，用 `asyncio.Queue` + `asyncio.Event`

在 `app/services/qa/` 下新增 `event_bus.py`：

```python
# app/services/qa/event_bus.py
import asyncio
from dataclasses import dataclass, field
from typing import AsyncIterator, Callable

@dataclass
class StreamBus:
    """轻量 per-turn 事件总线。"""
    max_history: int = 100
    _queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    _history: list = field(default_factory=list)
    _subscribers: dict[str, asyncio.Queue] = field(default_factory=dict)
    _done: asyncio.Event = field(default_factory=asyncio.Event)

    def emit(self, event: dict) -> None:
        self._history.append(event)
        if len(self._history) > self.max_history:
            self._history.pop(0)
        for q in self._subscribers.values():
            q.put_nowait(event)

    def subscribe(self, name: str, replay: bool = True) -> AsyncIterator[dict]:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers[name] = q
        if replay:
            for event in self._history:
                yield event
        try:
            while not self._done.is_set():
                try:
                    event = await asyncio.wait_for(q.get(), timeout=1.0)
                    yield event
                except asyncio.TimeoutError:
                    continue
        finally:
            self._subscribers.pop(name, None)

    def close(self) -> None:
        self._done.set()
```

然后在 `answer_service.py` 中：

```python
async def answer_turn(turn_input, *, student_state_summary=None) -> AsyncIterator[dict]:
    bus = StreamBus()
    # 启动后台持久化消费者
    asyncio.create_task(_persist_consumer(bus, turn_input, ...))
    # 启动后台诊断消费者
    asyncio.create_task(_diagnosis_consumer(bus))
    # answer_turn 内部用 bus.emit() 替代 yield
    ...
    # 路由端 subscribe
    async for event in bus.subscribe("sse"):
        yield event
```

### 分步实施建议

1. **Phase 1**（当前即可做）：把 `streaming_service.py` 的 `sse_*` 函数扩展成统一的 `StreamEvent` 枚举 + emit 接口，但 `answer_turn` 仍保持 `yield`，不改消费者
2. **Phase 2**：引入 `StreamBus` 类，`answer_turn` 内部创建总线实例 emit 事件，路由端 subscribe 消费
3. **Phase 3**：将 `save_turn_record` 从串行改为总线消费者
4. **Phase 4**：诊断模块通过总线监听 `done` 事件实时触发，逐步淘汰轮询

## 参考文件

| 文件 | 关键内容 |
|------|---------|
| `app/services/qa/answer_service.py` | 主编排，当前直接 yield dict，共 644 行 |
| `app/services/qa/streaming_service.py` | SSE 辅助函数，当前只有 28 行，非常薄 |
| `app/services/qa/contracts.py` | `QAStreamEvent` 定义（5 种事件类型） |
| `app/services/qa/turn_store.py` | 持久化逻辑，串行阻塞在 answer_turn 末尾 |
| `app/routers/qa.py` | SSE 路由，唯一消费者 |
| `app/routers/exercise.py` | 另一套 SSE 模式（字符串拼接），可统一 |
| `app/services/diagnostic_worker.py` | 诊断 Worker，30s 轮询 DB |
| `app/services/llm_service.py` | LLM 调用封装 |
| `app/services/diagnosis/contracts.py` | 诊断数据契约，QA 只读消费 |

---

## 工具调用（Function Calling）思路借鉴

### 我们需要工具调用吗？

**短期不需要，中期可以考虑。**

当前 ai-math 的 QA 链路是**纯文本生成**模式：

1. `grounding_service.py` 做教材定位 + KG 查询（纯本地计算，不调 LLM）
2. `prompt_builder.py` 把所有上下文（KG 节点、学生状态、教学策略、历史）拼成一段长 prompt
3. `llm_service.stream_chat()` 单次流式调用，LLM 一口气生成回答
4. 没有 `tools` 参数，没有 `tool_calls`，没有多轮 LLM 交互

这个模式对**当前业务完全够用**：学生问一个数学题，LLM 结合教材上下文直接回答，不需要查网页、不需要执行代码、不需要多步骤推理。

但有几类场景**当前的纯文本模式处理得不好**：

### 如果引入工具调用，什么场景合适

#### 场景 1：LLM 自主触发「教材翻页定位」

当前定位是**服务器端硬编码的**：`ground_text_turn()` 根据 `page_number` 去查 DB，LLM 只是被动接收定位结果。但如果学生问的是跨页问题（"第三章和第五章的行列式性质有什么联系"），或者没给页码只给了概念名，LLM 自己应该有能力决定"我需要查一下第三章的内容"。

工具方案：暴露 `search_textbook(concept: str, page: int | None)` 工具，LLM 按需调用，而不是服务器猜定位结果塞进 prompt。

#### 场景 2：苏格拉底追问中的「检查学生回答」

当前苏格拉底模式是：LLM 生成一个引导性问题 → 学生回复 → 新的一轮 QA。但 LLM 看不到"学生答得对不对"，下一轮只能重新 grounding + 重新生成，没有"检查答案"这个独立步骤。

工具方案：暴露 `check_student_answer(question: str, student_answer: str, reference: str) -> dict` 工具，LLM 可以在同一轮内调用来决定下一步是继续追问还是给解答。

#### 场景 3：知识图谱深度追问

当前 KG 信息是一次性塞进 prompt 的。如果学生追问某个概念的定义，LLM 只能凭记忆回答。如果引入 `lookup_kg_node(node_name: str) -> KGNodeRef` 工具，LLM 可以按需查 KG，不需要一开始就把所有节点塞进上下文。

### 借鉴 DeepTutor 的设计

如果将来要引入工具调用，建议借鉴以下设计：

#### 1. 工具注册表 + BaseTool 基类

```python
# app/services/tools/registry.py
class BaseTool(ABC):
    name: str
    description: str

    @abstractmethod
    def get_definition(self) -> dict:
        """返回 OpenAI Function Calling 格式的 JSON Schema"""
        ...

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        ...

class ToolRegistry:
    _tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None: ...
    def list_definitions(self) -> list[dict]: ...  # 生成 tools 参数
    async def execute(self, name: str, args: dict) -> Any: ...
```

每个工具一个文件，`get_definition()` 返回 schema，`execute()` 做实际工作。这与当前 `grounding_service.py` 的纯函数风格不同——工具调用模式下，**LLM 决定"要不要查"**，而不是服务器决定。

#### 2. 工具执行与流式输出解耦

当前 `answer_turn()` 的流式输出是 `yield dict`。工具调用需要改为：

```python
# answer_turn 内部
messages = [{"role": "user", "content": prompt}]
while True:
    response = llm_service.chat(messages, tools=tool_definitions)
    if response.choices[0].finish_reason == "tool_calls":
        # 并行执行工具
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(execute_tool(tc)) for tc in tool_calls]
        # 结果追加到 messages
        for result in results:
            messages.append({"role": "tool", ...})
        yield sse_tool_result(...)  # 通知前端
        continue  # LLM 下一轮
    else:
        # 正常流式输出
        ...
```

这与 StreamBus 的思路一致：工具执行结果也是事件，前端可以渲染"正在查教材"之类的状态。

#### 3. 工具上下文注入

DeepTutor 在 Agent 层给工具注入知识库名称等上下文。对应到 ai-math，可以给工具注入 `user_id`、`textbook_id` 等，工具执行时自动带上当前会话上下文。

### 不建议照搬的地方

| DeepTutor 的做法 | 不照搬的理由 |
|-----------------|-------------|
| **18 个工具，含 code_execution、cron、exec** | ai-math 是数学教育场景，不需要代码执行、定时任务、GitHub 操作。最多 3-5 个工具 |
| **用户可开关的工具（brainstorm、paper_search 等）** | 当前教学策略由 `tutor_policy.py` 和 `scaffolding_controller.py` 控制，不需要让用户手动开关工具 |
| **load_tools 延迟加载机制** | 工具数量少，一次性注册即可，不需要渐进式加载 |
| **ask_user 工具暂停 turn** | 当前 SSE 架构没有反向通道，学生回答走新的 HTTP 请求。这个功能需要前后端一起改，优先级低 |
| **write_memory / read_memory 记忆工具** | 当前学生状态由 `diagnosis` 模块维护，走 DB 持久化，不需要 LLM 自己读写记忆 |

### 建议的落地方式

**Phase 0（不做，先观察）**：保持当前纯 prompt 模式。对于 90% 的数学题问答场景，prompt_builder 已经足够好。工具调用的主要价值在"LLM 自主决策何时查什么"——但当前 grounding_service 在服务端已经做得很好了。

**Phase 1（如果真要引入）**：只加一个工具。

```python
class SearchTextbook(BaseTool):
    name = "search_textbook"
    description = "在教材中搜索指定概念或关键词的原文"
    parameters = {
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "搜索关键词"},
            "page": {"type": "integer", "description": "可选，限定搜索页码"},
        },
        "required": ["keyword"],
    }

    async def execute(self, keyword: str, page: int | None = None) -> dict:
        # 复用 grounding_service 的 _safe_question_node_rows 等
        ...
```

然后在 `answer_turn()` 中增加一个 `if tools:` 分支，只在特定 submode（如 `exam_review`，学生可能问跨页比较题）时挂载工具。

**Phase 2**：如果 Phase 1 验证有效，再加 `check_student_answer` 工具，用于苏格拉底追问的即时校验。

**核心原则**：不要为了用工具而用工具。当前 prompt_builder 把 KG、学生状态、教学策略全部拼成一段 text，对主流 LLM 来说完全够用。工具调用的引入必须是**业务场景驱动**的——只有当某个场景明显用 prompt 解决不好（比如跨页搜索、答案校验），才值得。