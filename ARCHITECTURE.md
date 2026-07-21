# 架构规则

本文档定义项目的模块结构、依赖方向、数据契约。
所有 agent（lead/coder/reviewer）必须遵守。

历史决策记录（ADR）见 [`docs/adr/`](./docs/adr/) 目录，每个 ADR 一个独立文件。

---

## 模块结构

```
app/
├── main.py                # FastAPI 入口，注册路由
├── config.py              # 配置
├── routers/               # 薄路由：参数转换 + 转发到 services
│   ├── qa.py             # /api/qa/solve-stream
│   ├── auth.py           # 认证 + 用户画像 + KG 查询
│   ├── chat.py           # 聊天历史
│   ├── profile.py        # 用户偏好
│   ├── exercise.py       # 练习出题
│   └── feedback.py       # 反馈
├── services/              # 业务逻辑
│   ├── qa/               # QA 回答模块
│   │   ├── answer_service.py       # 主编排（文字+视觉）
│   │   ├── prompt_builder.py       # 统一 prompt 构造器
│   │   ├── contracts.py             # 数据契约
│   │   ├── turn_store.py            # QATurnRecord 持久化
│   │   ├── grounding_service.py     # KG 定位
│   │   ├── vision_context_service.py
│   │   ├── streaming_service.py
│   │   └── tutor_policy.py
│   ├── diagnosis/        # 认知诊断模块
│   │   ├── diagnosis_service.py
│   │   ├── contracts.py
│   │   ├── cognitive_evidence_service.py
│   │   ├── student_state_service.py
│   │   └── diagnostic_card_service.py
│   ├── diagnostic_worker.py  # 后台诊断 Worker
│   ├── llm_service.py
│   ├── error_analyzer.py
│   └── ...
├── db/                   # 数据访问层，不 import services
├── auth/
└── models/
    └── schemas.py        # Pydantic 请求/响应模型
```

---

## 模块依赖规则

```
┌─────────────────────────────────────────────────────────┐
│                       依赖方向图                          │
│                                                         │
│    frontend (TS)                                        │
│        │                                                │
│        │  HTTP / SSE                                    │
│        ▼                                                │
│    ┌─────────┐                                          │
│    │ routers │  薄路由，只做参数转换 + 转发               │
│    └────┬────┘                                          │
│         │                                               │
│         ▼                                               │
│    ┌──────────┐  ──── 可以 import ────►  ┌───────────┐  │
│    │ services │                          │ contracts │  │
│    │  qa/     │  ← 可以读 contracts ←──  │ (dataclass)│  │
│    │  diag/   │                          └───────────┘  │
│    └────┬────┘                                          │
│         │                                               │
│         ▼                                               │
│    ┌──────────┐                                         │
│    │   db/    │  数据访问，不能 import services           │
│    └──────────┘                                         │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### 依赖规则

| 规则 | 说明 |
|------|------|
| `routers → services` | 路由调用服务，不允许跳过 services 直接调 db |
| `services → db` | 服务调用数据访问层 |
| `db ↛ services` | db 层不能 import services（防止循环依赖） |
| `qa ↛ diagnosis service` | QA 不能 import 诊断的服务函数（不触发诊断、不更新 stage） |
| `diagnosis → qa.contracts` | 诊断可以 import QA 的数据契约（只读，消费 QATurnRecord） |
| `qa → diagnosis.contracts` | QA 可以 import 诊断的数据契约（只读 StudentStateSummary 等） |
| `模块间传 dataclass` | 不传 dict，用 contracts.py 里定义的 dataclass |

### QA 链路约束

- QA 只负责回答 + 写 QATurnRecord
- QA **不触发诊断**、**不更新 stage**、**不生成诊断结论**
- QA 可以**只读** stage（用于调整 prompt 风格）
- 诊断模块独立消费 QATurnRecord

---

## 数据契约

模块间通过 dataclass 传递数据，不传 dict。

### QA 模块契约（`app/services/qa/contracts.py`）

| 契约 | 用途 |
|------|------|
| `QATurnInput` | QA 输入（user_id, question, input_type, history...） |
| `QATurnRecord` | QA 完整记录（turn_id, question, answer, sources, messages_snapshot...） |
| `QATurnContext` | QA 上下文快照 |
| `QAAnswerResult` | QA 回答结果 |
| `QAStreamEvent` | SSE 事件 |

### 诊断模块契约（`app/services/diagnosis/contracts.py`）

| 契约 | 用途 |
|------|------|
| `StudentStateSummary` | 学生状态摘要（stage, 薄弱前置, 模式...） |
| `TutorPolicy` | 教学策略（模式, 深度, 引导式提问...） |
| `TurnGrounding` | 教材定位（textbook_id, page, chapter, KG 概念...） |
| `CognitiveEvidence` | 认知证据 |
| `DiagnosticCard` | 诊断卡片 |
| `WeakPrerequisite` | 薄弱前置概念 |
| `KGNodeRef` | KG 节点引用 |
| `KGRelationRef` | KG 一跳关系引用 |
| `KGContext` | QA 可只读使用的教材 KG 上下文 |
| `EvidenceSpan` | 证据片段 |
| `RuleCaseRef` | 规则案例引用 |

---

## 决策记录索引

完整 ADR 文件见 [`docs/adr/`](./docs/adr/) 目录。

| 编号 | 标题 | 文件 |
|------|------|------|
| ADR-001 | QA 模块与诊断模块解耦 | [docs/adr/ADR-001-qa-diagnosis-decouple.md](./docs/adr/ADR-001-qa-diagnosis-decouple.md) |
| ADR-002 | 目录结构从中文改为英文 | [docs/adr/ADR-002-chinese-to-english-dirs.md](./docs/adr/ADR-002-chinese-to-english-dirs.md) |
| ADR-003 | 视觉 prompt 合一到 prompt_builder | [docs/adr/ADR-003-vision-prompt-merge.md](./docs/adr/ADR-003-vision-prompt-merge.md) |
| ADR-004 | 删除 deprecated 非流式端点 | [docs/adr/ADR-004-delete-deprecated-endpoints.md](./docs/adr/ADR-004-delete-deprecated-endpoints.md) |
| ADR-005 | 保留 app/db/diagnostic.py 桥接文件 | [docs/adr/ADR-005-keep-diagnostic-bridge.md](./docs/adr/ADR-005-keep-diagnostic-bridge.md) |
| ADR-006 | 前端 API 调用统一收口到 api.ts | [docs/adr/ADR-006-frontend-api-unify.md](./docs/adr/ADR-006-frontend-api-unify.md) |
| ADR-007 | 前端提取 MarkdownRenderer 公共组件 | [docs/adr/ADR-007-markdown-renderer.md](./docs/adr/ADR-007-markdown-renderer.md) |
| ADR-008 | 前端 App.tsx 提取 useFeedback / useExercise | [docs/adr/ADR-008-frontend-useFeedback-useExercise.md](./docs/adr/ADR-008-frontend-useFeedback-useExercise.md) |
| ADR-009 | 前端 App.tsx 拆分 useMarkers / useChat | [docs/adr/ADR-009-frontend-useMarkers-useChat.md](./docs/adr/ADR-009-frontend-useMarkers-useChat.md) |
| ADR-010 | QA-KG 上下文适配 | [docs/adr/ADR-010-qa-kg-context-adapter.md](./docs/adr/ADR-010-qa-kg-context-adapter.md) |

---

### ADR-007: 前端提取 MarkdownRenderer 公共组件

**背景**：ChatPanel、ExercisePanel、MarkerPopover 三个组件各自配置了 ReactMarkdown + remarkMath + rehypeKatex，3 处重复，改一处漏两处。

**决策**：新建 MarkdownRenderer.tsx 公共组件，统一 Markdown + KaTeX 渲染配置（含 formatMath 和 p/code/pre 自定义渲染），三个组件改用公共组件。

**理由**：消除重复；统一渲染行为；后续改渲染逻辑只需改一处。

**后果**：三个组件删除旧 import 和内部 RichText/formatMath；MarkdownRenderer.tsx 新增；删除 44 行重复代码。

---

### ADR-008: 前端 App.tsx 提取 useFeedback / useExercise 自定义 hook

**背景**：App.tsx 581 行、23 个 useState 过度膨胀，反馈和练习生成逻辑混在主组件里。

**决策**：提取 useFeedback（3 个 useState + 提交逻辑）和 useExercise（4 个 useState + 生成逻辑）到独立 hook 文件。

**理由**：App.tsx 瘦身第一步；状态逻辑独立可测；降低主组件复杂度。

**后果**：App.tsx 删除 7 个 useState + handleStartExercise 函数；新增 2 个 hook 文件；4 个 api import 下沉到 hook。

---

### ADR-009: 前端 App.tsx 拆分 useMarkers / useChat 自定义 hook

**背景**：App.tsx 仍有 16 个 useState 集中管理聊天和标记状态，handleSendMessage 150 行同时操作两者，耦合严重。

**决策**：提取 useMarkers（标记状态 + CRUD）和 useChat（聊天状态 + handleSendMessage），useChat 接收 useMarkers 的方法作为参数（markersState）实现解耦。

**理由**：App.tsx 进一步瘦身；聊天和标记状态管理分离；handleSendMessage 逻辑完整保留但移到独立 hook。

**后果**：App.tsx 删除 16 个 useState + 6 个函数；新增 2 个 hook 文件；App.tsx 从 581 行降到约 200 行。

---

## 变更日志

每次架构相关改动，reviewer 审核通过后在此追加一条日志。

| 日期 | ADR | 改动 | 审核者 |
|------|-----|------|--------|
| 2026-07-03 | ADR-002 | 目录从中文改为英文 | reviewer |
| 2026-07-03 | ADR-003 | 视觉 prompt 合一到 prompt_builder | reviewer |
| 2026-07-03 | ADR-004 | 删除 deprecated 非流式端点 | reviewer |
| 2026-07-03 | ADR-005 | 保留 diagnostic.py 桥接文件 | reviewer |
| 2026-07-03 | ADR-006 | 前端 API 调用统一收口到 api.ts | reviewer |
| 2026-07-03 | ADR-007 | 前端提取 MarkdownRenderer 公共组件 | reviewer |
| 2026-07-03 | ADR-008 | 前端 App.tsx 提取 useFeedback / useExercise | reviewer |
| 2026-07-03 | ADR-009 | 前端 App.tsx 拆分 useMarkers / useChat | reviewer |
| 2026-07-03 | ADR-010 | QA-KG 上下文适配 | pending-review |
