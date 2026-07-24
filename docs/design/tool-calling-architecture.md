# 工具调用架构设计

> 版本：v1.0  
> 状态：设计草案  
> 关联 ADR：待定（需评审后创建）

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [设计原则](#2-设计原则)
3. [核心概念](#3-核心概念)
4. [组件设计](#4-组件设计)
   - 4.1 工具定义（`ToolDef`）
   - 4.2 工具注册表（`ToolRegistry`）
   - 4.3 工具执行器（`ToolExecutor`）
   - 4.4 Agent 循环改造
5. [第一批工具清单](#5-第一批工具清单)
6. [与现有架构的集成](#6-与现有架构的集成)
7. [SSE 事件协议](#7-sse-事件协议)
8. [边界情况与异常处理](#8-边界情况与异常处理)
9. [附录](#9-附录)

---

## 1. 背景与目标

### 1.1 现状

当前 QA 回答流程是**线性编排**：

```
question → grounding → prompt_builder → LLM.stream_chat → yield tokens → done
```

LLM 只有一次"思考＋回答"的机会，遇到需要查教材、查 KG、验算的场景，所有信息必须在 prompt 里一次性塞给模型。导致：

- Prompt 越来越臃肿（一次塞入所有 KG 上下文、教材片段、验算结果）
- 模型无法在回答过程中主动发起"查一下这个概念的定义"或"验算这个表达式"
- 前端无法感知模型正在"做什么"（查教材 / 查 KG / 验算），只能看到 stage 文字

### 1.2 目标

引入 OpenAI Function Calling 风格的**工具调用（Tool Calling）**，让 LLM 在回答过程中可以：

1. **主动调用工具**获取外部信息，而非依赖 prompt 预填充
2. **多轮工具调用**：LLM 思考 → 调工具 → 拿到结果 → 继续思考 → 再调工具 → 最终回答
3. **前端可见**：工具调用和结果通过 SSE 事件推送，前端可展示"正在查教材...""正在验算..."

### 1.3 与之对比：纯 Prompt 模式

| 维度 | 纯 Prompt 模式 | 工具调用模式 |
|------|---------------|-------------|
| 信息获取 | 一次性塞入 prompt | 按需调用工具获取 |
| Prompt 长度 | 大（包含所有上下文） | 小（只包含初始指令） |
| 模型决策 | 一次性回答 | 多轮思考→工具→回答 |
| 前端可见性 | 只有 stage 文字 | 实时可见 tool_call/tool_result |
| 适用场景 | 简单问答、不需要外部信息 | 需要查教材、查 KG、验算 |

两种模式通过 `BaseAgent.get_tools()` 的返回值控制：**返回空列表 = 纯 Prompt 模式**，**返回工具列表 = 工具调用模式**。

---

## 2. 设计原则

1. **工具定义扁平化**：工具是 dataclass，不是类层次结构，不引入 Claude Code 的权限校验层和 UI 渲染层
2. **复用现有设施**：工具实现直接调用已有的 `grounding_service`、`kg_v44`、`sympy_sandbox`，不另起炉灶
3. **与纯 Prompt 模式共存**：通过 `get_tools()` 是否返回空列表控制，不破坏现有 Agent
4. **事件驱动**：工具调用/结果通过 `StreamBus` 和 SSE 推送，前端可消费
5. **执行安全**：工具执行有超时、异常捕获，不阻断主循环

---

## 3. 核心概念

### 3.1 工具调用循环

```
┌─────────────┐     tool_calls      ┌──────────────┐
│             │ ──────────────────►  │              │
│   LLM 模型  │                      │  ToolExecutor │
│             │ ◄──────────────────  │              │
└─────────────┘     tool_result     └──────┬───────┘
       │                                    │
       │  content (最终回答)                  │ 复用现有服务
       ▼                                    ▼
   yield tokens                      grounding_service
                                    kg_v44.find_node
                                    sympy_sandbox.verify_computable
```

### 3.2 消息队列结构

工具调用模式下，`messages` 列表会包含新的 role 类型：

```python
messages = [
    {"role": "system", "content": "你是一个数学助教..."},
    {"role": "user", "content": "什么是特征值？"},
    # ── LLM 决定调工具 ──
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_xxx", "type": "function",
         "function": {"name": "search_textbook", "arguments": '{"keyword": "特征值"}'}}
    ]},
    # ── 工具执行结果 ──
    {"role": "tool", "tool_call_id": "call_xxx", "content": "特征值是矩阵A满足 Av=λv 的标量λ..."},
    # ── LLM 继续回答 ──
    {"role": "assistant", "content": "特征值是指对于方阵A，存在非零向量v使得 Av=λv..."},
]
```

---

## 4. 组件设计

### 4.1 工具定义（`ToolDef`）

**文件位置**：`app/services/agents/tool_def.py`（新建）

```python
"""工具定义模型。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDef:
    """工具定义。

    使用 dataclass 而非类层次，保持扁平简单。
    input_schema 使用 JSON Schema 格式，兼容 OpenAI Function Calling 规范。
    execute 是异步函数，接收 **kwargs 并返回 dict。
    """

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    execute: Callable[..., Any] | None = None

    def to_openai_tool(self) -> dict[str, Any]:
        """转换为 OpenAI Function Calling 格式的 tool 定义。

        用于传给 LLM 的 tools 参数。
        """
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }
```

**设计说明**：

- `frozen=True`：工具定义不可变，防止运行时被篡改
- `execute` 为可选字段，允许只注册定义不注册实现（用于声明式场景）
- `to_openai_tool()` 方法将内部格式转换为 OpenAI 兼容格式，方便传给 `llm_service`
- 不引入 `validateInput`/`checkPermissions`（当前不需要权限校验层）
- 不引入 UI 渲染层（不需要 React 终端渲染）

### 4.2 工具注册表（`ToolRegistry`）

**文件位置**：`app/services/agents/tool_registry.py`（新建）

```python
"""工具注册表，管理所有工具定义。"""

from __future__ import annotations

from typing import Any

from app.services.agents.tool_def import ToolDef


class ToolRegistry:
    """工具注册表，提供注册、查询、列表功能。

    使用类级别变量，单例模式，确保全局统一。
    """

    _tools: dict[str, ToolDef] = {}

    @classmethod
    def register(cls, tool: ToolDef) -> None:
        """注册工具定义，同名时覆盖。"""
        cls._tools[tool.name] = tool

    @classmethod
    def get(cls, name: str) -> ToolDef | None:
        """按名称获取工具定义。"""
        return cls._tools.get(name)

    @classmethod
    def list_tools(cls) -> list[ToolDef]:
        """返回所有已注册的工具定义列表。"""
        return list(cls._tools.values())

    @classmethod
    def list_openai_tools(cls) -> list[dict[str, Any]]:
        """返回 OpenAI Function Calling 格式的 tools 参数。

        这是最常用的接口，直接传给 LLM 的 chat.completions.create(tools=...)。
        """
        return [tool.to_openai_tool() for tool in cls._tools.values()]

    @classmethod
    def clear(cls) -> None:
        """清空注册表，主要用于测试场景。"""
        cls._tools.clear()


# 全局单例，模块级 import 即可使用
tool_registry = ToolRegistry()
```

**为什么不用 `AGENT_REGISTRY` 而是新建注册表**：

- 职责不同：`AGENT_REGISTRY` 管理 Agent 实例，`ToolRegistry` 管理工具定义
- 生命周期不同：Agent 实例有状态（每次 run 创建），工具定义是无状态的
- 使用频率不同：工具列表在每次 LLM 调用时获取，独立的注册表查询更轻量

### 4.3 工具执行器（`ToolExecutor`）

**文件位置**：`app/services/agents/tool_executor.py`（新建）

```python
"""工具执行器：解析 LLM 返回的 tool_call，执行并返回结果。"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from app.services.agents.tool_registry import tool_registry


# 工具执行超时（秒）
TOOL_TIMEOUT_SECONDS = 15


class ToolExecutionError(Exception):
    """工具执行异常。"""
    pass


async def execute_tool_call(tool_call: Any) -> dict[str, Any]:
    """执行单个 tool_call，返回结果。

    Args:
        tool_call: OpenAI 返回的 tool_call 对象，
                   包含 id, function.name, function.arguments

    Returns:
        {"role": "tool", "tool_call_id": str, "content": str}

    Raises:
        ToolExecutionError: 工具未找到、执行超时或执行异常
    """
    tool_name = tool_call.function.name
    tool = tool_registry.get(tool_name)

    if tool is None or tool.execute is None:
        raise ToolExecutionError(f"工具 '{tool_name}' 未注册或未实现")

    # 解析参数
    try:
        arguments = json.loads(tool_call.function.arguments)
    except json.JSONDecodeError as e:
        raise ToolExecutionError(f"工具 '{tool_name}' 参数解析失败: {e}")

    # 执行工具（带超时）
    try:
        result = await asyncio.wait_for(
            tool.execute(**arguments),
            timeout=TOOL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise ToolExecutionError(f"工具 '{tool_name}' 执行超时（{TOOL_TIMEOUT_SECONDS}s）")
    except Exception as e:
        raise ToolExecutionError(f"工具 '{tool_name}' 执行异常: {e}")

    # 返回格式兼容 OpenAI tool message
    return {
        "role": "tool",
        "tool_call_id": tool_call.id,
        "content": json.dumps(result, ensure_ascii=False),
    }


async def execute_tool_calls(tool_calls: list[Any]) -> list[dict[str, Any]]:
    """并发执行多个 tool_call，返回结果列表。

    Args:
        tool_calls: OpenAI 返回的 tool_calls 列表

    Returns:
        [{"role": "tool", "tool_call_id": str, "content": str}, ...]
    """
    tasks = [execute_tool_call(tc) for tc in tool_calls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

**设计说明**：

- 使用 `asyncio.wait_for` 实现工具执行超时控制，防止单个工具卡死整个循环
- 工具间并发执行（`asyncio.gather`），LLM 一次请求多个工具时并行处理
- 异常不会抛出，而是转为 `ToolExecutionError`，由上层循环处理
- 工具返回值统一序列化为 JSON 字符串，保持与 OpenAI 的 `tool` message 格式一致

### 4.4 Agent 循环改造

核心改造在 `answer_turn()` 层面：从线性 yield 改造为 `while` 循环 + 工具调用模式。

**改造后的 `answer_turn()` 伪代码**：

```python
async def answer_turn_with_tools(
    turn_input: QATurnInput,
    *,
    tools: list[dict] | None = None,
    max_tool_rounds: int = 5,
) -> AsyncIterator[dict]:
    """支持工具调用的 QA 入口。

    Args:
        turn_input: QA 输入
        tools: OpenAI Function Calling 格式的 tools 参数
        max_tool_rounds: 最大工具调用轮数，防止无限循环

    Yields:
        SSE 事件流
    """
    # 1. 构造初始 messages（与现有流程一致）
    grounding = ground_text_turn(...)
    policy = decide_tutor_policy(...)
    prompt = build_tutor_prompt(...)
    messages = [{"role": "user", "content": prompt}]

    # 2. 工具调用循环
    tool_rounds = 0
    while tool_rounds < max_tool_rounds:
        # 2a. 调用 LLM（非流式，带 tools 参数）
        response = llm_service.chat(
            messages=messages,
            tools=tools,          # 传入工具列表
        )

        finish_reason = response.choices[0].finish_reason

        # 2b. 判断 LLM 是否请求工具调用
        if finish_reason == "tool_calls":
            tool_calls = response.choices[0].message.tool_calls

            # 记录 assistant 消息（含 tool_calls）
            assistant_msg = {
                "role": "assistant",
                "content": response.choices[0].message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
            messages.append(assistant_msg)

            # 推送 tool_call 事件
            for tc in tool_calls:
                yield sse_event("tool_call", {
                    "tool_call_id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })

            # 执行工具
            tool_results = await execute_tool_calls(tool_calls)

            # 处理结果并推送 tool_result 事件
            for tc, result in zip(tool_calls, tool_results):
                if isinstance(result, Exception):
                    # 工具执行异常，返回错误信息
                    error_msg = str(result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps({"error": error_msg}, ensure_ascii=False),
                    })
                    yield sse_event("tool_result", {
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "error": error_msg,
                    })
                else:
                    messages.append(result)
                    yield sse_event("tool_result", {
                        "tool_call_id": tc.id,
                        "name": tc.function.name,
                        "status": "success",
                    })

            tool_rounds += 1
            continue  # 回到循环，LLM 继续思考

        # 2c. LLM 直接返回文本（无工具调用），进入流式输出
        elif finish_reason == "stop":
            # 已经有完整内容，直接流式输出
            content = response.choices[0].message.content or ""
            # 逐字 yield（或者直接用流式重新调用）
            yield sse_text(content)
            break

        else:
            # 其他 finish_reason（length, content_filter 等）作为错误处理
            yield sse_error(f"LLM 返回异常 finish_reason: {finish_reason}")
            return

    # 3. 超过最大轮数时截断
    if tool_rounds >= max_tool_rounds:
        yield sse_error("工具调用超过最大轮数限制，已截断")

    # 4. 持久化、诊断等后续逻辑（与现有流程一致）
    yield sse_done(...)
```

**关键设计决策**：

1. **非流式调用 vs 流式调用**：工具调用阶段使用非流式 `chat()`（需要获取 `finish_reason` 和 `tool_calls`），最终回答阶段使用流式 `stream_chat()`。两阶段切换：
   - 第一阶段：`while` 循环，非流式，处理工具调用
   - 第二阶段：LLM 返回 `stop` 后，若有完整内容则直接 yield，或使用流式重新调用

2. **最大轮数限制**：`max_tool_rounds=5` 防止无限循环。实际场景中 1-2 轮工具调用足够。

3. **异常工具调用不阻断循环**：单个工具执行失败后，将错误信息以 `tool` role 放回消息队列，让 LLM 决定如何处理（重试、换工具、或直接回答）。

### 4.5 与 `llm_service` 的兼容

当前 `llm_service.chat()` 不支持 `tools` 参数，需要扩展：

```python
# 在 app/services/llm_service.py 中扩展

def chat(self, messages: list, model: str = None, use_profile: bool = False,
         response_format: dict = None, temperature: float = 0.3,
         tools: list[dict] = None) -> dict:
    """非流式调用，支持 tools 参数。"""
    client = self.profile_client if use_profile else self.qa_client
    if not client:
        raise RuntimeError("LLM 服务未初始化")

    model_name = config.PROFILE_LLM_MODEL if use_profile else config.QA_LLM_MODEL

    kwargs = {
        "model": model or model_name,
        "messages": messages,
        "stream": False,
        "temperature": temperature,
    }
    if response_format:
        kwargs["response_format"] = response_format
    if tools:
        kwargs["tools"] = tools

    return client.chat.completions.create(**kwargs)
```

---

## 5. 第一批工具清单

### 5.1 `search_textbook`

在教材中搜索指定概念或关键词的原文段落。

```python
from app.services.agents.tool_def import ToolDef
from app.services.agents.tool_registry import tool_registry
from app.services.qa.grounding_service import ground_text_turn

async def _search_textbook_impl(
    keyword: str,
    textbook_id: str | None = None,
    page: int | None = None,
) -> dict:
    """在教材中搜索关键词，返回原文段落和定位信息。"""
    # 复用 grounding_service 的查询逻辑
    grounding = ground_text_turn(
        textbook_id=textbook_id or "",
        page_number=page,
        question=keyword,
    )
    return {
        "textbook_id": grounding.textbook_id,
        "page_number": grounding.page_number,
        "chapter_name": grounding.chapter_name,
        "content_excerpt": grounding.content_excerpt[:2000],
        "related_concepts": [
            {"name": node.name, "type": node.type}
            for node in grounding.related_concepts[:10]
        ],
        "confidence": grounding.confidence,
    }


search_textbook_tool = ToolDef(
    name="search_textbook",
    description="在教材中搜索指定概念或关键词的原文段落，返回教材名称、页码、章节名和原文内容",
    input_schema={
        "type": "object",
        "properties": {
            "keyword": {
                "type": "string",
                "description": "搜索关键词，可以是概念名、术语或数学表达式",
            },
            "textbook_id": {
                "type": "string",
                "description": "教材ID，可选，不传时自动检测",
            },
            "page": {
                "type": "integer",
                "description": "页码，可选，指定后返回该页相关内容",
            },
        },
        "required": ["keyword"],
    },
    execute=_search_textbook_impl,
)

# 注册
tool_registry.register(search_textbook_tool)
```

### 5.2 `lookup_kg_node`

查询知识图谱中某个概念的定义、证据原文、前后置关系。

```python
from app.db.kg_v44 import find_node, related_nodes, search_nodes_in_book

async def _lookup_kg_node_impl(
    concept_name: str,
    book_id: str | None = None,
) -> dict:
    """查询知识图谱节点信息。"""
    # 精确查找节点
    node = find_node(concept_name)
    if not node:
        # 模糊搜索
        if book_id:
            results = search_nodes_in_book(book_id, concept_name, limit=5)
        else:
            return {"found": False, "message": f"未找到概念 '{concept_name}'"}
        return {
            "found": True,
            "candidates": [
                {"name": r["name"], "type": r.get("type"), "source_code": r.get("source_code")}
                for r in results[:5]
            ],
        }

    # 查询关联节点
    support_nodes, lookahead_nodes = related_nodes(node["name"], limit=10)

    return {
        "found": True,
        "node": {
            "name": node["name"],
            "type": node.get("type"),
            "chapter": node.get("chapter"),
            "section": node.get("section"),
            "source_code": node.get("source_code"),
            "evidence_span": node.get("evidence_span"),
        },
        "support_nodes": [
            {"name": n["name"], "type": n.get("type"), "rel_type": n.get("rel_type")}
            for n in support_nodes
        ],
        "lookahead_nodes": [
            {"name": n["name"], "type": n.get("type"), "rel_type": n.get("rel_type")}
            for n in lookahead_nodes
        ],
    }


lookup_kg_node_tool = ToolDef(
    name="lookup_kg_node",
    description="查询知识图谱中某个概念的定义、证据原文、前后置关系，返回概念详情和关联节点",
    input_schema={
        "type": "object",
        "properties": {
            "concept_name": {
                "type": "string",
                "description": "概念名称，如'特征值'、'线性无关'、'行列式'",
            },
            "book_id": {
                "type": "string",
                "description": "教材ID，可选，用于限定搜索范围",
            },
        },
        "required": ["concept_name"],
    },
    execute=_lookup_kg_node_impl,
)

tool_registry.register(lookup_kg_node_tool)
```

### 5.3 `verify_math`

用 SymPy 验算数学表达式是否正确。

```python
from app.services.sympy_sandbox import verify_computable, WHITELIST

async def _verify_math_impl(
    expression: str,
    comp_type: str,
    expected: str | list | float | int,
    **kwargs,
) -> dict:
    """用 SymPy 验算数学表达式。"""
    # 构建 data 参数
    data = {"expression": expression}
    if comp_type.startswith("matrix_") or comp_type == "system_solve":
        if "matrix" in kwargs:
            data["matrix"] = kwargs["matrix"]
        if "vector" in kwargs:
            data["vector"] = kwargs["vector"]
    if comp_type in ("polynomial_roots", "polynomial_factor"):
        data["degree"] = kwargs.get("degree", 5)

    # 调用 SymPy 沙箱
    result = verify_computable(comp_type, data, expected)

    return {
        "success": result.get("success", False),
        "sympy_result": result.get("sympy_result"),
        "error": result.get("error"),
        "expected": expected,
        "comp_type": comp_type,
        "supported_types": list(WHITELIST.keys()),
    }


verify_math_tool = ToolDef(
    name="verify_math",
    description="用 SymPy 验算数学表达式是否正确，支持矩阵运算、多项式求根、因式分解、线性方程组求解等",
    input_schema={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 'x**2 - 5*x + 6'",
            },
            "comp_type": {
                "type": "string",
                "enum": list(WHITELIST.keys()),
                "description": "计算类型：matrix_eigenvalues, matrix_determinant, matrix_inverse, matrix_rank, system_solve, polynomial_roots, polynomial_factor",
            },
            "expected": {
                "description": "预期结果，类型由 comp_type 决定：列表（特征值/根）、浮点数（行列式）、整数（秩）、字符串（因式分解）",
            },
            "matrix": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "number"}},
                "description": "矩阵数据，仅 matrix_* 和 system_solve 类型需要",
            },
            "vector": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "number"}},
                "description": "向量数据，仅 system_solve 类型需要",
            },
            "degree": {
                "type": "integer",
                "description": "多项式次数上限，可选，默认 5",
            },
        },
        "required": ["expression", "comp_type", "expected"],
    },
    execute=_verify_math_impl,
)

tool_registry.register(verify_math_tool)
```

### 5.4 注册入口

在 `app/services/agents/__init__.py` 中统一注册：

```python
"""Agent 模块初始化，注册所有 Agent 和工具定义。"""

from app.services.agents.tool_registry import tool_registry

# 注册工具定义（延迟 import 避免循环依赖）
def _register_tools() -> None:
    from app.services.agents.tools.search_textbook import search_textbook_tool
    from app.services.agents.tools.lookup_kg_node import lookup_kg_node_tool
    from app.services.agents.tools.verify_math import verify_math_tool

    tool_registry.register(search_textbook_tool)
    tool_registry.register(lookup_kg_node_tool)
    tool_registry.register(verify_math_tool)


_register_tools()
```

**文件目录建议**：

```
app/services/agents/
├── __init__.py            # 初始化，注册 Agent 和工具
├── base.py                # BaseAgent 抽象基类
├── registry.py            # AGENT_REGISTRY
├── tool_def.py            # ToolDef dataclass
├── tool_registry.py       # ToolRegistry 注册表
├── tool_executor.py       # ToolExecutor 执行器
├── qa_agent.py            # QAAgent
├── exercise_agent.py      # ExerciseAgent
└── tools/                 # 工具实现目录
    ├── __init__.py
    ├── search_textbook.py
    ├── lookup_kg_node.py
    └── verify_math.py
```

---

## 6. 与现有架构的集成

### 6.1 `BaseAgent.get_tools()` 扩展

```python
# app/services/agents/base.py

class BaseAgent(abc.ABC):
    """Agent 抽象基类，定义统一接口和预留扩展点。"""

    name: str = ""
    description: str = ""

    @abc.abstractmethod
    async def run(self, input: Any, stream: bool = True) -> AsyncIterator[dict]:
        """统一入口，返回 SSE 事件流。"""
        ...

    def get_tools(self) -> list[dict]:
        """返回 OpenAI Function Calling 格式的 tools 列表。

        默认返回空列表（纯 Prompt 模式），
        子类覆盖后启用工具调用模式。
        """
        return []
```

### 6.2 `QAAgent` 启用工具调用

```python
# app/services/agents/qa_agent.py

class QAAgent(BaseAgent):
    name = "qa"
    description = "数学问答：教材定位 + KG 对齐 + 流式回答"

    def get_tools(self) -> list[dict]:
        """启用工具调用模式。"""
        from app.services.agents.tool_registry import tool_registry
        return tool_registry.list_openai_tools()

    async def run(self, input: Any, stream: bool = True) -> AsyncIterator[dict]:
        if input is None:
            yield sse_error("QAAgent 收到空输入")
            return
        if not isinstance(input, QATurnInput):
            yield sse_error(f"QAAgent 期望 QATurnInput，收到 {type(input).__name__}")
            return

        tools = self.get_tools()
        if tools:
            # 工具调用模式
            async for event in answer_turn_with_tools(input, tools=tools):
                yield event
        else:
            # 纯 Prompt 模式（兜底）
            async for event in answer_turn(input):
                yield event
```

### 6.3 集成流程图

```
用户请求
    │
    ▼
qa_router (routers/qa.py)
    │
    ▼
QAAgent.run(input)
    │
    ├── get_tools() 返回空？───► answer_turn() [纯 Prompt 模式]
    │
    └── get_tools() 返回工具列表
        │
        ▼
    answer_turn_with_tools()
        │
        ├── grounding (前置定位，与现有一致)
        ├── prompt_builder (构造初始 prompt)
        │
        ├── while 循环 ──► LLM.chat(tools=...)
        │   │                  │
        │   │            finish_reason="tool_calls"
        │   │                  │
        │   │            execute_tool_calls()
        │   │                  │
        │   │            yield tool_call/tool_result
        │   │                  │
        │   └──────────────────┘ (继续循环)
        │
        ├── finish_reason="stop" ──► yield 最终回答
        │
        ├── 持久化 QATurnRecord (与现有一致)
        ├── 异步诊断消费 (与现有一致)
        └── yield sse_done (与现有一致)
```

### 6.4 与 `StreamBus` 的集成

工具调用事件通过 `StreamBus` 推送，与现有 `"done"` 事件共享同一总线：

```python
# 在 answer_turn_with_tools 中
bus = StreamBus()  # 与现有持久化/诊断共用

# 工具调用事件
bus.emit({
    "type": "tool_call",
    "tool_call_id": tc.id,
    "name": tc.function.name,
    "arguments": tc.function.arguments,
})

# 工具结果事件
bus.emit({
    "type": "tool_result",
    "tool_call_id": tc.id,
    "name": tc.function.name,
    "status": "success" if not error else "error",
})
```

### 6.5 与 `QAStreamEvent` 的集成

`QAStreamEvent` 已预留 `tool_call`/`tool_result` 事件类型（见 `contracts.py` 第 83 行）：

```python
@dataclass(frozen=True)
class QAStreamEvent:
    event: Literal[
        "stage", "content", "thinking", "thinking_chunk",
        "done", "error", "heartbeat",
        "wait_for_input", "progress",
        "tool_call", "tool_result",   # ← 已预留
    ]
    data: dict[str, Any] = field(default_factory=dict)
```

工具调用事件将使用 `event="tool_call"` 和 `event="tool_result"`。

### 6.6 `llm_service` 扩展

需要给 `llm_service` 增加 `chat_with_tools` 方法（或扩展现有 `chat` 方法）：

```python
# 在 app/services/llm_service.py 中追加

def chat_with_tools(
    self,
    messages: list,
    tools: list[dict],
    model: str = None,
    temperature: float = 0.3,
) -> Any:
    """非流式调用，支持 Function Calling tools 参数。

    返回 OpenAI 响应对象，包含 choices[0].finish_reason
    和 choices[0].message.tool_calls。
    """
    if not self.qa_client:
        raise RuntimeError("QA LLM 服务未初始化")

    return self.qa_client.chat.completions.create(
        model=model or config.QA_LLM_MODEL,
        messages=messages,
        tools=tools,
        tool_choice="auto",  # LLM 自主决定是否调工具
        stream=False,
        temperature=temperature,
    )
```

---

## 7. SSE 事件协议

### 7.1 `tool_call` 事件

当 LLM 决定调用工具时推送。

```json
{
    "event": "tool_call",
    "data": {
        "tool_call_id": "call_abc123",
        "name": "search_textbook",
        "arguments": "{\"keyword\": \"特征值\", \"textbook_id\": \"高代上-丘维声\"}"
    }
}
```

前端展示：显示"正在调用工具：查教材（特征值）..."

### 7.2 `tool_result` 事件

工具执行完成后推送。

```json
{
    "event": "tool_result",
    "data": {
        "tool_call_id": "call_abc123",
        "name": "search_textbook",
        "status": "success",
        "error": null
    }
}
```

前端展示：显示"教材查询完成"，或"教材查询失败：xxx"

### 7.3 前端消费示例

```typescript
// 前端事件处理
switch (event.event) {
    case "tool_call":
        setToolStatus(`正在${getToolLabel(event.data.name)}...`);
        break;
    case "tool_result":
        if (event.data.error) {
            setToolStatus(`${getToolLabel(event.data.name)} 失败`);
        } else {
            setToolStatus(`${getToolLabel(event.data.name)} 完成`);
        }
        break;
}
```

---

## 8. 边界情况与异常处理

### 8.1 LLM 不支持工具调用

某些模型（如视觉模型）可能不支持 `tools` 参数。

**处理**：`QAAgent.get_tools()` 中根据模型能力动态返回：

```python
def get_tools(self) -> list[dict]:
    from app.config import config
    # 视觉模型暂不支持工具调用
    if config.QA_VL_MODEL in self._vision_models:
        return []
    return tool_registry.list_openai_tools()
```

### 8.2 工具执行超时

工具执行超过 `TOOL_TIMEOUT_SECONDS`（默认 15s）时，返回错误信息给 LLM，让 LLM 决定如何处理。

```python
# 错误信息格式
{"error": "工具 'search_textbook' 执行超时（15s）"}
```

### 8.3 工具返回数据过大

工具返回的数据可能超过 LLM 上下文窗口。

**处理**：在工具实现中加截断逻辑，限制返回内容大小（如 `content_excerpt[:2000]`）。

### 8.4 工具调用死循环

`max_tool_rounds=5` 硬限制，超过后截断并返回错误。

### 8.5 工具未注册

LLM 可能请求调用未注册的工具（幻觉）。

**处理**：`ToolExecutionError` 返回错误信息，LLM 收到后通常会重试或放弃。

### 8.6 多工具并发执行

LLM 可能一次请求多个工具调用（如同时查教材和查 KG）。

**处理**：`execute_tool_calls` 使用 `asyncio.gather` 并发执行，返回结果后按原始顺序 append 到 messages。

---

## 9. 附录

### 9.1 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/services/agents/tool_def.py` | 新建 | `ToolDef` dataclass |
| `app/services/agents/tool_registry.py` | 新建 | `ToolRegistry` 注册表 |
| `app/services/agents/tool_executor.py` | 新建 | `execute_tool_call` 执行器 |
| `app/services/agents/tools/__init__.py` | 新建 | 工具实现目录 |
| `app/services/agents/tools/search_textbook.py` | 新建 | `search_textbook` 工具实现 |
| `app/services/agents/tools/lookup_kg_node.py` | 新建 | `lookup_kg_node` 工具实现 |
| `app/services/agents/tools/verify_math.py` | 新建 | `verify_math` 工具实现 |
| `app/services/agents/__init__.py` | 修改 | 注册工具定义 |
| `app/services/agents/qa_agent.py` | 修改 | 覆盖 `get_tools()`，启用工具调用 |
| `app/services/llm_service.py` | 修改 | 增加 `chat_with_tools()` 方法 |
| `app/services/qa/answer_service.py` | 修改 | 增加 `answer_turn_with_tools()` 函数 |

### 9.2 实施路线

| 阶段 | 任务 | 预计改动量 |
|------|------|-----------|
| P0 | 新建 `ToolDef`、`ToolRegistry`、`ToolExecutor` | 3 个新文件，~150 行 |
| P0 | 实现 3 个工具并注册 | 3 个新文件，~150 行 |
| P1 | 扩展 `llm_service.chat_with_tools()` | 1 个文件修改，~20 行 |
| P1 | 实现 `answer_turn_with_tools()` | 1 个文件修改，~150 行 |
| P2 | 改造 `QAAgent.get_tools()` 和 `run()` | 1 个文件修改，~30 行 |
| P2 | 前端支持 `tool_call`/`tool_result` 事件 | 前端改动 |

### 9.3 参考文档

- [OpenAI Function Calling 官方文档](https://platform.openai.com/docs/guides/function-calling)
- `app/services/agents/base.py` — BaseAgent 抽象基类
- `app/services/agents/registry.py` — AGENT_REGISTRY 注册表
- `app/services/qa/event_bus.py` — StreamBus 事件总线
- `app/services/qa/contracts.py` — QAStreamEvent 事件类型
- `app/services/qa/answer_service.py` — 现有线性编排流程
- `app/services/qa/grounding_service.py` — 教材定位服务
- `app/services/sympy_sandbox.py` — SymPy 沙箱
- `app/services/llm_service.py` — LLM 调用服务
- `docs/notes/agent-design-lesson.md` — Agent 设计思路笔记