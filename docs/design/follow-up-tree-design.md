# 追问历史树与学习总结树设计

> 版本：v1.0
> 日期：2026-07-27
> 状态：产品规则已确认，追问树第一阶段已实施；总结 Agent 与完整总结树界面待后续接入
> 范围：单个教材徽标内的追问分支、上下文隔离与学习总结

## 1. 背景

当前系统以教材页上的问答徽标保存一次基础问答或截图提问，并用线性聊天继续交互。数学学习中的后续交流通常不是单线展开：学生会从同一回答分别追问证明、例子、前置知识、易错点或另一种方法。线性历史会混合这些方向，难以返回旧思路，也容易把不相关分支加入模型上下文。

本设计引入两种相互独立的树：

1. **追问历史树**：忠实记录用户从哪条 AI 回答创建了哪个独立追问分支。
2. **学习总结树**：把整棵追问树中的结论、误区和待追问内容重新组织为可复习成果。

追问历史树负责可追溯性，学习总结树负责知识收束。两者不能共用同一拓扑。

## 2. 目标与非目标

### 2.1 目标

- 一个基础问答或截图提问对应一个教材徽标和一棵追问树。
- 学生只能通过显式的“追问”操作创建分支。
- 分支精确锚定到某条已经完成的 AI 回答。
- 每个分支只继承祖先上下文，不自动读取兄弟分支。
- 节点内部允许多轮苏格拉底式交流，不因普通消息轮次扩张树结构。
- 支持返回旧回答继续创建新分支、回答版本对比、归档和恢复。
- Agent 可以在授权范围内按消息编号读取压缩前的内容。
- 用户可以手动生成整棵树的学习总结，并追溯到原始消息。

### 2.2 第一版非目标

- 不做跨教材徽标的自动合并。
- 不做多人实时协作、评论或共享编辑。
- 不做移动端树交互的最终设计。
- 不让系统自动判断何时应当分叉。
- 不根据 AI 已讲解的内容直接判定学生已掌握。
- 不把学习总结树作为认知诊断的直接证据来源。

## 3. 核心概念

### 3.1 教材徽标与追问树

```text
教材页
└─ 徽标：一次基础问答或截图提问
   └─ 根节点：基础问题及其多轮对话
      ├─ 追问节点 A
      │  └─ 追问节点 A.1
      └─ 追问节点 B
```

- 一个徽标只绑定一棵树。
- 根节点在数据上也是普通树节点，同时关联原 `chat_history.id`。
- 不同徽标即使涉及相同知识点，第一版也保持独立。

### 3.2 节点

一个节点表示一次有明确起点的学习议题，可以包含多轮消息。例如：

```text
学生：为什么这里必须满秩？
AI：你先想一下，不满秩意味着什么？
学生：存在非零解。
AI：对，因此……
```

上述四条消息属于同一个节点。节点没有显式结束状态，可以持续追加普通消息。

### 3.3 消息

- 消息按节点内顺序追加，不原地覆盖。
- AI 流式回答完成后，消息状态才是 `completed`。
- 用户中止的 AI 回答保留为 `interrupted`，但不能作为分叉锚点。
- 每条已完成 AI 回答下显示“追问”按钮。

### 3.4 分叉锚点

每个子节点必须同时记录：

```text
parent_node_id   父节点
fork_message_id 触发分叉的已完成 AI 消息
```

父节点之后可以继续追加消息，但已经存在的子节点只继承到 `fork_message_id` 为止。仅保存 `parent_node_id` 不足以复原真实上下文。

### 3.5 引用关系

树节点始终只有一个主父节点。用户可以显式勾选兄弟分支作为额外上下文，但这只创建引用关系：

```text
parent_node_id       唯一主父节点
referenced_node_ids  用户授权引用的其他节点
```

引用不会把树改造成多父节点图。

## 4. 交互规则

### 4.1 普通对话

- 主输入框默认把消息追加到当前节点。
- 普通对话不产生新树节点。
- 即使学生换了话题，只要没有点击“追问”，第一版也不自动拆分或提示。

### 4.2 创建追问分支

1. AI 回答完整结束。
2. 回答下出现带分叉图标的“追问”按钮。
3. 悬停说明：“从这条回答创建独立分支”。
4. 点击后，输入区切换为分叉模式，并显示来源回答摘要。
5. 学生输入并发送后才创建子节点。
6. 取消分叉模式不创建任何数据。
7. 创建成功后自动切换到新子节点。

### 4.3 返回旧节点

- 点击树节点后切换到该节点。
- 从旧节点继续普通对话，会向该节点追加消息。
- 从旧节点的任意已完成 AI 回答点击“追问”，创建新的子分支。
- 沿子分支浏览祖先时，只展示祖先截至对应 `fork_message_id` 的消息；直接打开祖先节点时显示其全部最新消息。

### 4.4 重新生成回答

- 重新生成不会覆盖原回答。
- 新回答形成同一分叉位置下的兄弟版本。
- 用户可以标记一个“采用版本”。
- 未采用版本仍可浏览，默认不参与学习总结。

### 4.5 归档与总结排除

- 删除操作实际执行归档，不物理删除节点。
- 完整树视图提供“显示已归档分支”开关。
- 用户可以保留一个正常分支，同时标记为“不参与本次总结”。

### 4.6 分支浏览

- 桌面端默认显示折叠窄树。
- 分支超过两个时提示展开。
- 展开视图显示完整树、节点摘要和当前路径。
- 点击教材徽标时恢复用户上次停留的节点。
- 树节点悬停或点击时显示问题摘要。
- 节点默认以学生发起追问的第一句话命名，过长时压缩，支持用户重命名。

## 5. 上下文与 Agent 权限

### 5.1 默认上下文

回答 Agent 默认获得：

- 当前节点完整消息。
- 最近祖先的完整消息。
- 更早祖先的编号摘要。
- 教材 ID、页码、截图和框选区域。
- 当前教学模式。
- 最新用户画像与知识状态。

教材、截图、祖先路径和分叉位置属于冻结上下文。用户画像在每次新回答时读取最新值，但实际使用的画像必须写入当次审计快照。

### 5.2 按需读取工具

Agent 可以通过内部工具按需展开内容：

```text
read_message_range(node_id, message_ids)
read_node_summary(node_id, summary_version?)
```

回答 Agent 的授权范围仅包括：

- 当前节点及祖先路径。
- 用户明确勾选的兄弟节点。
- 用户在兄弟节点中明确选择的消息。

回答 Agent 不得自行搜索整棵树或未授权兄弟分支。

整树总结 Agent 的权限不同：它可以读取同一树内所有未归档、已采用且未被排除的分支。

### 5.3 上下文压缩

当路径超过模型上下文时：

- 当前节点保留完整消息。
- 最近祖先优先保留完整消息。
- 更早祖先使用带来源消息 ID 的结构化摘要。
- 教材证据、关键公式和用户明确引用的消息优先保留。
- 界面仍展示完整历史，只压缩实际发送给模型的上下文。

每次回答记录：

- 实际读取的消息 ID。
- 使用的节点摘要及版本。
- 引用的兄弟分支和具体消息。
- 上下文压缩策略版本。
- 实际使用的画像快照。

## 6. 学习总结树

### 6.1 生成范围

用户点击“总结学习”后，默认总结整棵追问树，并排除：

- 已归档分支。
- 未采用的重新生成版本。
- 用户标记为“不参与总结”的分支。
- 未发送成功的空分支。

局部节点摘要在用户发起总结时按需生成并缓存，不在每轮对话后自动消耗模型额度。

### 6.2 两阶段生成

```text
每个追问节点 -> 带来源 ID 的局部结构化摘要
全部局部摘要 -> 整棵树的学习总结
```

总结模型不能静默消解分支冲突。存在互斥结论时，必须生成“待追问/存在冲突”节点。

### 6.3 总结节点类型

```text
conclusion      结论
misconception   误区
open_question   待追问
```

### 6.4 学习状态

```text
explained       AI 已讲解，学生尚未验证
understood      学生已表现出理解
misconception   学生表现出误区
unresolved      未解决或存在分支冲突
```

- 只有 AI 讲解、没有学生参与的内容仍进入总结，但只能标为 `explained`。
- `understood` 必须由学生复述、推导、解释或答题等行为证据支持。
- 已解决误区不删除，改为已解决状态并关联解决证据。
- 学习总结树只用于复习展示，不直接作为诊断证据。

### 6.5 可追溯与人工编辑

- 每个总结节点保存 `source_message_ids`。
- 点击总结节点可以跳回原始追问节点和教材页。
- AI 自动节点在后续总结中允许更新。
- 用户修改过的节点锁定保留。
- 用户删除的节点进入抑制列表，不自动复活。
- 冲突节点必须经用户确认后才能消失。
- 第一版至少保留“上一次 AI 总结”和“当前人工版本”。

## 7. 数据模型草案

### 7.1 `chat_trees`

```text
id
user_id
root_chat_history_id
last_active_node_id
revision
created_at
updated_at
```

### 7.2 `chat_nodes`

```text
id
tree_id
parent_node_id
fork_message_id
title
version_group_id
is_adopted
exclude_from_summary
migration_quality
revision
archived_at
created_at
updated_at
```

### 7.3 `chat_messages`

```text
id
node_id
sequence_no
role                 user / assistant / tool / system_event
content
status               streaming / completed / interrupted / failed
token_count
created_at
completed_at
```

消息采用追加模式。已完成内容不原地改写；流式消息完成后更新状态和最终内容。

### 7.4 `chat_node_references`

```text
source_node_id
target_node_id
selected_message_ids
summary_version
created_at
```

### 7.5 `node_summaries`

```text
id
node_id
summary_version
content_json
source_message_ids
strategy_version
created_at
```

### 7.6 `summary_trees`

```text
id
chat_tree_id
version
previous_ai_version_id
created_by
created_at
```

### 7.7 `summary_nodes`

```text
id
summary_tree_id
parent_summary_node_id
node_type
learning_status
title
content
source_message_ids
edited_by_user
locked
deleted_at
revision
```

## 8. 与现有数据兼容

- 现有 `chat_history` 继续承载教材徽标及旧历史接口。
- `chat_trees.root_chat_history_id` 关联原记录。
- 现有 `follow_ups` JSON 中每一项迁移为根节点下的一级子节点。
- 旧数据没有精确分叉消息，统一设置：

```text
migration_quality = legacy_approximate
fork_message_id = 根回答末尾的 AI 消息
```

- 不伪造旧历史中不存在的多轮对话或精确分叉位置。
- 数据库迁移必须幂等，并先在正式数据库副本上验证。

## 9. API 草案

```text
GET    /api/chat/trees/by-history/{chat_history_id}
GET    /api/chat/trees/{tree_id}
PATCH  /api/chat/trees/{tree_id}/active-node

POST   /api/chat/nodes
PATCH  /api/chat/nodes/{node_id}
POST   /api/chat/nodes/{node_id}/archive
POST   /api/chat/nodes/{node_id}/restore
POST   /api/chat/nodes/{node_id}/adopt

POST   /api/chat/nodes/{node_id}/messages
GET    /api/chat/nodes/{node_id}/messages

PUT    /api/chat/nodes/{node_id}/references

POST   /api/chat/trees/{tree_id}/summaries
GET    /api/chat/trees/{tree_id}/summaries/latest
PATCH  /api/chat/summary-nodes/{summary_node_id}
```

所有写接口携带 `revision`。服务器检测版本冲突后返回明确冲突响应，不静默覆盖多窗口修改。

### 9.1 现有代码落点与兼容风险

当前实现还不是树结构，必须先按以下边界接入：

- `frontend/src/hooks/useMarkers.ts` 通过历史接口读取根徽标，并解析 `follow_ups` JSON。
- `frontend/src/hooks/useChat.ts` 将根问题、根回答和 `follow_ups` 展平成前端消息列表；普通追问目前都会回写同一个根徽标。
- `frontend/src/components/ChatPanel.tsx` 只有单输入发送，没有回答级分叉操作。
- `frontend/src/components/MarkerPopover.tsx` 只能展示线性追问历史。
- `frontend/src/services/api.ts` 已有历史读写、`chatId`/`markerId`、SSE 和工具事件传输，可作为兼容入口扩展。
- `app/routers/qa.py` 和 `app/services/qa/contracts.py` 目前只接收扁平 `history`；新的 `node_id`、`fork_message_id`、引用节点和服务端上下文版本必须加入请求契约。
- `app/services/qa/answer_service.py` 已有 Agent 工具循环，可以扩展分支授权的消息读取工具，但不能信任客户端直接提交的完整历史。
- `qa_turn_records` 已保存 `context_snapshot`/`messages_snapshot`，可作为上下文审计基础，但还需要记录 `tree_id`、`node_id`、`root_id` 和实际读取消息。
- `app/db/diagnosis_v2_db.py` 目前按 `user_id + marker_id/chat_id` 查找最近问答；树化后必须附带 `node_id`/路径并按学生证据去重，否则兄弟分支会串诊断。

### 9.2 当前实施门槛

工作区存在另一组尚未提交的认证、数据库、PDF、练习和 Playwright 修改，且与本功能预计修改的 `connection.py`、`schemas.py`、QA 服务、`App.tsx`、`useChat.ts`、`api.ts` 等文件重叠。在这些修改提交、分支隔离或明确合并策略之前，不直接编码追问树，避免覆盖他人工作。

## 10. SSE 与消息状态

- 发送普通消息时携带 `tree_id`、`node_id`。
- 创建分支后的第一条消息额外携带 `parent_node_id`、`fork_message_id`。
- 流式开始前创建 `streaming` 消息记录。
- 正常结束后更新为 `completed`，此时前端显示“追问”按钮。
- 用户中止后更新为 `interrupted`，不显示“追问”按钮。
- 工具调用和结果继续通过现有 SSE 事件传输，并关联当前消息或 turn。

## 11. 验收标准

### 11.1 分叉与隔离

- 可以从任意已完成 AI 回答创建子分支。
- 取消分叉不产生空节点。
- 父节点后续追加消息不进入已有子分支。
- 子分支不能读取未授权兄弟消息。
- 用户授权引用后，Agent 只能读取勾选摘要或消息。
- 中止回答不能成为分叉锚点。

### 11.2 导航与版本

- 教材徽标恢复上次活跃节点。
- 当前路径按照各级 `fork_message_id` 截断显示。
- 完整树能浏览全部正常、未采用和已归档版本。
- 重新生成形成兄弟版本，采用状态唯一。
- `revision` 冲突不会静默覆盖。

### 11.3 总结

- 默认总结整棵有效树，并正确应用排除规则。
- AI-only 内容标记为 `explained`，不误标 `understood`。
- 冲突分支生成 `unresolved` 节点。
- 总结节点可以跳回来源消息。
- 人工锁定和删除抑制在重新总结后保持有效。

### 11.4 兼容

- 旧教材徽标和线性历史仍可读取。
- 旧 `follow_ups` 能以近似分叉迁移。
- 迁移脚本重复执行不产生重复节点。
- 所有数据库测试在独立副本或临时库执行。

## 12. 建议实施阶段

1. **工作区隔离**：确认现有未提交修改的归属，提交或建立独立分支；追问树开发不得覆盖并行修复。
2. **设计与契约**：确认表结构、状态机、API、SSE 字段和诊断字段。
3. **持久化基础**：在数据库副本上新增树、节点、消息和引用表，完成幂等迁移与旧数据兼容读取。
4. **消息级分叉**：实现追问按钮、分叉输入状态、消息锚点和服务端上下文隔离。
5. **树导航**：实现窄树、完整树、上次活跃节点和归档/版本操作。
6. **Agent 上下文工具**：实现授权清单、编号摘要、按需读取和审计记录。
7. **诊断兼容**：将 `node_id`/路径写入 QA 记录，按学生消息证据去重，验证兄弟分支不串诊断。
8. **学习总结树**：实现局部摘要缓存、整树总结、来源跳转和人工编辑保护。
9. **验证与迁移**：完成并发、浏览器、数据库副本和旧数据迁移测试。

## 13. 延期项

- 移动端树形导航与触控交互。
- 跨徽标、跨教材页的总结合并。
- 多人协作、分享和评论。
- 自动识别应当分叉的对话主题。
- 将总结树纳入正式诊断证据。

## 14. 2026-07-27 实施记录

已完成第一阶段：

- 新增树、节点、稳定消息、显式引用、局部摘要、总结树和总结节点表。
- 新增树 CRUD、分叉锚点校验、归档/恢复、乐观并发和旧 `follow_ups` 幂等迁移。
- QA 在提供 `node_id` 时由服务端重建授权路径上下文，不读取未授权兄弟分支。
- 每条已完成 AI 回答提供独立分叉按钮；发送后才创建子节点，取消不落库。
- 桌面端提供默认折叠的窄树 rail，可悬停查看摘要、切换节点和展开较大分支树。
- 总结树已具备版本化、来源消息校验和人工编辑锁的持久化/API 基础。
- 子分支加载和切换统一读取服务端授权路径，界面恢复祖先到分叉锚点的消息。
- QA SSE 统一创建用户消息和 `streaming` AI 占位，并收口为 `completed`、`interrupted` 或 `failed`。
- 客户端回合 ID 支持幂等重放，避免请求重试产生重复消息或覆盖已完成回答。
- 对话树 API 强制校验 Bearer Token，旧徽标支持当前用户、单条记录的惰性幂等迁移。
- QA 审计快照记录实际 `tree_id`、`node_id`、分叉锚点和显式引用节点。

尚未完成：

- 总结 Agent 的两阶段生成流程和总结树专用前端视图。
- 重新生成回答的兄弟版本比较与采纳界面。
- 归档、恢复、重命名和兄弟引用的完整前端操作面板。
- 移动端树导航的最终交互。
