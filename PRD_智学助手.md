# 智学助手 PRD — 高等代数智能问答系统

> **注意**：本文档为 v0.7 版本的历史设计文档（最后更新 2026-05-06）。
> 当前项目已演进到 v2.4，最新架构和模块说明请查阅 [项目详细说明/](项目详细说明/) 目录。
> 本文档保留作为设计过程的原始记录。

| 版本 | 日期 | 作者 |
|------|------|------|
| v0.7 | 2026-05-06 | 全面同步代码：新增练习题系统（exercise router）、页面标记系统（PageMarker）、动态Prompt引擎、四级学徒脚手架、前置知识检测、六阶段认知追踪、教材偏好持久化；DB层重构（16模块拆分）；双后台Worker |
| v0.6 | 2026-04-29 | Phase 1 平板竖屏适配完成（AiBall + 移动端截图 + IIFE Worker）；文档全面更新 |
| v0.5 | 2026-04-24 | 技术栈移除ChromaDB；新增教材页码持久化功能（已完成）；更新第12章下册数据状态 |
| v0.4 | 2026-04-20 | 新增第12章项目成果（textbook_sections入库 + Neo4j图谱导入上册）；get_whitelist升级为查询Neo4j；移除forbidden字段；斩断ChromaDB链路 |

## 0. 2026 揭榜挂帅版本更新

### 0.1 最新项目定位

面向 XH-202620“面向一流学科建设的学科垂类大模型与创新应用开发”赛题，项目建议由“高等代数智能问答系统”升级为：

> **学数有道：基于学科知识图谱的大学数学认知诊断与个性化导学智能体**

新的定位不再强调“AI 更会讲题”，而是强调：

> **根据学生真实学习过程，判断他为什么不会，并持续形成可解释的学习画像与个性化干预。**

项目要避免被评委理解为豆包、Kimi、通义等通用 AI 的数学问答版本。核心差异不是记住聊天记录，而是将学生的对话、截图提问、错题、提示使用、练习表现结构化为：

- 知识点掌握状态；
- 认知断点；
- 错因类型；
- 提示依赖程度；
- 后续学习路径。

### 0.2 核心用户场景

不把产品假设为“学生每天主动打开的数学学习 App”，而是优先绑定三个高频痛点场景：

| 场景 | 学生痛点 | 系统价值 |
|---|---|---|
| 卡题时 | 不知道下一步怎么走，又不想直接抄答案 | 通过追问判断卡点，给分层提示 |
| 错题后 | 看懂答案但不知道自己为什么错 | 生成错因诊断、关联知识点和后续练习 |
| 考前复盘 | 不知道自己薄弱点在哪里 | 根据历史对话、错题和练习生成薄弱点清单 |

这三个场景的共同点是：学生天然会暴露学习痕迹，系统可以顺势采集数据，而不是要求学生额外填写画像。

### 0.3 与通用 AI 的区别

| 对比项 | 通用 AI 问答 | 学数有道 |
|---|---|---|
| 记忆方式 | 主要保存聊天上下文或长期记忆摘要 | 将学习痕迹映射到知识点、错因、阶段和干预策略 |
| 任务目标 | 回答当前问题 | 判断当前不会的原因，并持续更新学习画像 |
| 数学知识结构 | 依赖模型隐式知识 | 依托课程知识图谱定位前置知识、相关知识和后续路径 |
| 输出结果 | 解答、讲解、例子 | 解答过程 + 诊断卡片 + 后续练习/复盘建议 |
| 效果验证 | 通常难以证明 | 可用人工标注一致率、提示后修正率等指标验证 |

一句话表达：

> 豆包解决单次问题，学数有道解决长期认知诊断。

### 0.4 认知诊断闭环

系统应形成以下闭环：

```
学生提问/提交答案/请求提示
        ↓
定位教材页、题目和知识图谱节点
        ↓
结合历史画像判断知识掌握状态
        ↓
生成分层提示或苏格拉底式追问
        ↓
记录学生反应与提示依赖
        ↓
更新认知画像与学习路径
        ↓
生成诊断卡片和复盘任务
```

诊断卡片建议作为比赛演示中的核心界面：

```text
本次卡点：不会将线性无关定义转化为证明步骤
相关知识点：线性组合、齐次方程组、线性无关判定
学生表现：能复述定义，但无法建立证明起点
判断依据：学生第 2 轮回答缺少“任意系数均为 0”的条件
建议干预：先追问定义，再提示设 a1v1+a2v2+...=0
后续练习：定义展开型证明题 2 道
```

### 0.5 知识图谱的不可替代作用

知识图谱不能只作为“检索增强”的装饰，而要服务认知诊断：

- 将学生问题定位到课程知识节点；
- 识别当前节点的前置知识；
- 判断错误是否来自当前知识点，还是来自前置节点缺口；
- 支持从“自然语言评价”变成“可追踪的知识状态更新”；
- 为后续练习和学习路径提供结构化依据。

示例：

| 学生表现 | 普通 AI 可能判断 | 学数有道应输出 |
|---|---|---|
| 会背线性无关定义，但不会证明 | 你对定义理解不够 | 卡在“线性无关判定”节点；前置涉及“线性组合”“齐次方程组”；当前断点是“不会把定义展开为任意系数均为 0 的证明目标” |

### 0.6 效果验证优先级

当前不优先微调模型。原因是：没有稳定标注体系和标注数据时，微调容易变成技术噱头，且难以解释提升来源。

优先路线：

1. 建立认知诊断标签体系：知识点、错因类型、认知阶段、提示依赖。
2. 收集 20-50 条真实学生对话/错题/提示记录。
3. 邀请教师或高水平学生进行人工标注。
4. 用现有大模型 + 知识图谱 + 结构化 Prompt 生成诊断。
5. 比较系统诊断与人工诊断的一致率。

建议指标：

| 指标 | 含义 |
|---|---|
| 诊断一致率 | 系统判断的知识点/错因与人工标注是否一致 |
| 提示后修正率 | 学生获得分层提示后能否完成下一步 |
| 提示依赖度 | 学生需要几级提示才能继续 |
| 卡点解决时间 | 从卡住到完成关键步骤的时间 |
| 错因认可度 | 学生是否认可系统给出的错因诊断 |

若上述指标表现不足，再考虑小规模微调或训练专门的诊断分类模型。

### 0.7 借鉴 Socratopia 的学习乐趣设计

Socratopia 的启发不在于简单“游戏化”，而在于把苏格拉底式追问、人格化陪伴、教材对话、学习记录和沉浸式情境组合起来，让学生更愿意持续学习。其公开介绍强调：上传 PDF/ePub 后进入角色化学习世界，通过 AI 伙伴进行追问式学习，并保留进度、自动生成学习日记和闪卡。

学数有道可以借鉴，但不能照搬。大学数学学习的核心仍然是严谨推理、证明训练和错因诊断，故事化设计只能服务于学习动机，不能盖过数学本身。

#### 可借鉴设计

| Socratopia 思路 | 学数有道改造方式 |
|---|---|
| AI 伙伴/导师人格 | 提供“严谨助教”“温和陪练”“挑战型导师”等教学风格 |
| 沉浸式学习世界 | 设计轻量场景，如“证明工坊”“错因复盘室”“知识图谱探索” |
| 苏格拉底式追问 | 保留为主教学策略，但与认知阶段和提示级别绑定 |
| 自动学习日记 | 每次学习后生成“今日卡点、已修正点、待复盘点” |
| 闪卡/复习卡 | 将诊断结果转成概念卡、错因卡、证明套路卡 |
| 进度记忆 | 与知识阶段、错因历史、提示依赖度结合 |

#### 不建议照搬的部分

- 不做重剧情世界观，避免评委觉得不严肃；
- 不用积分、宠物、徽章作为核心卖点，避免弱化认知诊断；
- 不让角色人格影响数学严谨性；
- 不把学习乐趣理解成“更花哨的界面”，而是降低卡题挫败感，让学生愿意继续问、继续改、继续复盘。

#### MVP 功能建议

第一阶段只做轻量“乐趣层”，不大改底层架构：

| 功能 | 说明 | 优先级 |
|---|---|---|
| 导师风格切换 | 严谨型、温和型、挑战型，影响追问方式和反馈语气 | P0 |
| 诊断卡片美化 | 把冷冰冰的错因分析变成可读的学习反馈 | P0 |
| 学习日记 | 每次会话结束自动总结“今天卡在哪里、怎么突破、下次练什么” | P1 |
| 复盘卡片 | 根据错因生成概念卡、错因卡、证明模板卡 | P1 |
| 知识地图进度 | 在图谱上显示已掌握、薄弱、待复盘节点 | P1 |
| 轻量任务线 | 围绕章节生成“3 个卡点任务 + 1 次复盘” | P2 |

最终原则：

> 学习乐趣不是把数学包装成游戏，而是让学生在卡住时不那么孤独，在想通时有明确反馈，在复盘时看得见自己的进步。

---

## 1. 产品概述

### 1.1 产品定位

**智学助手**是一款面向高等代数学习的AI助教产品，基于 DashScope qwen3-vl-235b-a22b-thinking 模型，为学习者提供：

- 截图提问与文字提问
- 苏格拉底式引导（Socratic）与直接讲解（Direct）两种教学模式
- 流式思考过程与回答输出
- 全知识库检索问答

### 1.2 核心用户

- 高等代数课程在校学生
- 自学高等代数的社会学习者
- 数学教师备课参考

### 1.3 技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端框架 | React + TypeScript + Vite |
| UI 组件 | TailwindCSS + react-pdf + react-markdown |
| 后端框架 | FastAPI + Uvicorn（lifespan 模式） |
| LLM 模型 | qwen3-vl-235b-a22b-thinking / DeepSeek-V4-Pro |
| 知识图谱 | Neo4j（GraphDatabase + PREREQUISITE_OF + TEACH_IN） |
| 关系数据库 | SQLite（WAL 模式，16 模块拆分） |
| 数学验证 | SymPy（sandbox 沙箱） |
| 流式输出 | SSE（Server-Sent Events） |

**服务层核心模块**：

| 模块 | 功能 |
|------|------|
| `prompt_engine` | 动态 Prompt 组装（10 路信号） |
| `scaffolding_controller` | 四级认知学徒脚手架（Modeling/Coaching/Scaffolding/Fading） |
| `prerequisite_checker` | Neo4j 前置知识缺口检测 |
| `exercise_generator` | LLM 出题 + Markdown 解析 |
| `error_analyzer` | 错因诊断分析 |
| `sympy_sandbox` | SymPy 验算沙箱 |
| `insight_generator` | 学习洞察报告生成 |
| `diagnostic_worker` | 后台诊断 Worker（每 5min） |
| `pending_worker` | 知识阶段更新队列消费者（每 60s） |

---

## 2. 产品功能

### 2.1 问答系统（已上线）

#### 功能列表

| 功能 | 描述 | 状态 |
|------|------|------|
| 截图提问 | 框选PDF区域，截取图片+文字提问 | ✅ 已上线 |
| 文字提问 | 直接输入文字问题 | ✅ 已上线 |
| 流式思考过程 | AI推理过程实时流式显示 | ✅ 已上线 |
| 流式回答 | AI回答内容实时流式显示 | ✅ 已上线 |
| 教学模式切换 | 苏格拉底式提问 / 直接讲解 | ✅ 已上线 |
| 截图页码锚定 | 根据截图页码查 textbook_sections 获取教材上下文 | ✅ 已上线 |
| 知识点白名单 | 从 Neo4j 图谱查询当前节概念 + 直接前置约束 AI | ✅ 已上线 |
| 并发上下文拉取 | get_page_context + get_whitelist + get_user_profile 并发执行 | ✅ 已上线 |
| 历史对话传递 | 追问时AI可见上下文对话历史 | ✅ 已上线 |
| 页面提问标记 | PDF 页面上红蓝圆点标记提问位置，点击查看问答，支持删除 | ✅ 已上线 |
| 教学脚手架 | 四级认知学徒（Modeling/Coaching/Scaffolding/Fading）自动调节 | ✅ 已上线 |
| 前置知识检测 | Neo4j 查询 PREREQUISITE_OF 链，检测学生对当前概念的前置掌握 | ✅ 已上线 |
| 动态 Prompt 组装 | 10 路信号（角色/规则/认知/画像/白名单/前置/上下文/历史）拼接 | ✅ 已上线 |
| 教材页码持久化 | 刷新浏览器后保持教材和页码选择（localStorage + 云端双源） | ✅ 已上线 |

---

#### 页面提问标记系统（徽标系统）

当用户在 PDF 某页提问时，系统自动在页面垂直位置创建标记点：

| 特性 | 说明 |
|------|------|
| 红色标记（右侧） | 截图提问 |
| 蓝色标记（左侧） | 文字提问 |
| 数字编号 | ① ② ③ ... 按时间排序 |
| 点击弹窗 | `MarkerPopover` 展示该位置的问题 + AI 回答（可展开/删除） |
| 持久化 | `chat_history` 表存储 `page_number`、`marker_y_ratio`、`marker_type` |
| 跨页独立 | 每页的标记互不干扰 |
| 匿名迁移 | 匿名用户登录后，标记随 `chat_history` 迁移到登录账号 |

**相关文件**：
- `frontend/src/components/PageMarker.tsx` — 标记点渲染
- `frontend/src/components/MarkerPopover.tsx` — 标记弹窗
- `app/db/chat_history_db.py` — 持久化（含 migrate_user_id）

---

#### 已下线功能

| 功能 | 说明 |
|------|------|
| 全知识库检索（/api/chat/ask） | ChromaDB 向量库链路已斩断，暂停使用 |

---

#### 思考过程与回答渲染

**已实现**（2026-04-11）：

- 思考过程区域使用 `ReactMarkdown` + `remarkMath` + `rehypeKatex` 渲染，支持 LaTeX 公式
- 渲染顺序：思考过程（上方）→ 回答内容（下方）
- `useEffect` 增加 `!isLoading` 条件，仅在非流式状态触发自动滚动

**修改文件**：`d:\ai-math\frontend\src\components\ChatPanel.tsx`

---

### 2.2 学习者画像系统

#### 2.2.1 核心价值

通过分析用户历史问答行为，构建个人学习画像：

- 追踪知识点掌握情况（六阶段认知追踪）
- 推断学习风格偏好
- 识别薄弱环节
- 提供个性化学习建议

#### 2.2.2 功能列表

| 功能 | 描述 | 状态 |
|------|------|------|
| 用户注册/登录 | 用户名+密码注册，JWT认证 | ✅ 已上线 |
| 持久化 user_id | localStorage 生成 UUID，跨会话保持 | ✅ 已上线 |
| 匿名访问 | device_id 匿名模式，不注册也能使用 | ✅ 已上线 |
| 用户画像编辑 | 年级 + 薄弱知识点录入 | ✅ 已上线 |
| 知识点提问统计 | 每次提问记录 topic，追踪 consecutive_turns + total_asks | ✅ 已上线 |
| 诊断 Pipeline | 达到诊断触发条件时异步调用 LLM 生成诊断报告 | ✅ 已上线 |
| 诊断报告注入 Prompt | latest_diagnostic_report 嵌入 build_prompt 供 AI 读取 | ✅ 已上线 |
| 15 维度素养画像 | math_profiles 表含 5 维度 × 3 指标（coverage/radius/technical） | ✅ 已上线 |
| 六阶段认知追踪 | knowledge_stages 表追踪每个概念的认知阶段（0-5） | ✅ 已上线 |
| 四级学徒脚手架 | Modeling→Coaching→Scaffolding→Fading 自动调节教学深度 | ✅ 已上线 |
| 前置知识检测 | Neo4j PREREQUISITE_OF 链检测学生对当前概念的前置掌握缺口 | ✅ 已上线 |
| pending 队列消费 | pending_worker 每 60s 消费 stage 更新入 canonical 表 | ✅ 已上线 |
| 知识点标准化大纲 | 预定义高等代数知识点树结构 | ⏳ 规划中 |
| 追问意图分类 | 识别 Clarification/Elaboration 两类追问 | ⏳ 规划中 |
| 学习风格推断 | 基于行为数据推断 socratic 偏好、追问深度等 | ⏳ 规划中 |
| 画像洞察生成 | LLM 分析生成 strengths/weaknesses/summary | ✅ 已实现（API 待暴露） |

---

### 2.3 智能练习题系统（已上线）

#### 2.3.1 核心价值

- LLM 根据用户认知阶段自动出题，难度适配
- SymPy 沙箱验算保证题目正确性
- 渐进式提示避免直接给答案
- 错因诊断反馈薄弱环节

#### 2.3.2 功能列表

| 功能 | 描述 | 状态 |
|------|------|------|
| 流式出题 | POST /api/exercise/generate — SSE 流式返回 Markdown 题目 | ✅ 已上线 |
| SymPy 验算 | 自动验证计算型题目，验证失败标记 quality=-1 | ✅ 已上线 |
| 答案批改 | POST /api/exercise/{id}/submit — LLM 同步批改 + 异步错因分析 | ✅ 已上线 |
| 渐进提示 | POST /api/exercise/{id}/hint — 3 级提示逐步递进 | ✅ 已上线 |
| 用户纠错 | POST /api/exercise/{id}/report-error — 标记题目质量分 -1 | ✅ 已上线 |
| 错因分析 | error_analyzer 分析错误类型，定位相关概念，写入 pending_stage 更新 | ✅ 已上线 |
| 题目入库 | LLM 出题自动解析入库，含 hints/computable/verification 字段 | ✅ 已上线 |

#### 2.3.3 调用链路

```
POST /api/exercise/generate
  → knowledge_stages_db.get_stage() 获取当前认知阶段
  → whitelist_db.get_whitelist() Neo4j 知识边界
  → exercise_generator.build_exercise_prompt() 组装出题 Prompt
  → llm_service.stream_chat() 流式出题
  → exercise_generator.parse_markdown_sections() 解析题目/答案/提示
  → sympy_sandbox.verify_computable() SymPy 验算
  → exercise_bank_db.save_exercise() 入库
```

---

### 2.4 教材偏好持久化（已上线）

| 功能 | 描述 | 状态 |
|------|------|------|
| 教材/页码持久化 | 刷新后自动恢复到上次选择的教材和页码 | ✅ 已上线 |
| 双源存储 | 登录用户存云端（math_profiles），匿名用户存 localStorage | ✅ 已上线 |
| 本地进度上云 | 匿名用户登录后，自动将 localStorage 进度同步到云端 | ✅ 已上线 |
| 即时保存 | 切换教材/页码后立即写入（无防抖），确保刷新前必已持久化 | ✅ 已上线 |

**API**：`GET/POST /api/profile/textbook-preference`

---

## 3. 数据结构设计

### 3.1 现有数据库表

#### chat_history（已存在）

```sql
CREATE TABLE chat_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    sources TEXT,           -- JSON array
    knowledge_points TEXT,  -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### textbooks（已存在）

> ⚠️ 历史遗留：ChromaDB 斩断后，textbooks 表的向量库关联已断开。当前仅作为 `textbook_sections` 的外键引用来源，实际查询直接用字符串 textbook_id（如"高代上-丘维声"）查 textbook_sections，不再依赖本表。

```sql
CREATE TABLE textbooks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    subject TEXT NOT NULL,
    grade TEXT NOT NULL,
    chapters TEXT NOT NULL,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3.2 新增数据库表

#### profiles / topic_mastery / learning_style（规划中，已废弃）

> ⚠️ 历史遗留：本节描述的 profiles/topic_mastery/learning_style 三表为旧版画像设计，已被 math_profiles（15维度）+ user_knowledge_stats（知识点统计）+ question_assessments（提问评分）替代，不再使用。

```sql
CREATE TABLE profiles (
    id TEXT PRIMARY KEY,
    device_id TEXT UNIQUE,        -- 设备ID（匿名UUID）
    email TEXT UNIQUE,            -- 绑定邮箱（可选）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP,
    settings JSON                 -- 偏好设置
);

CREATE TABLE topic_mastery (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    topic_id TEXT NOT NULL,       -- 标准化知识点ID
    topic_name TEXT NOT NULL,     -- 标准化知识点名称
    asked_count INTEGER DEFAULT 0,
    correct_on_first INTEGER DEFAULT 0,
    need_hint INTEGER DEFAULT 0,
    last_asked TIMESTAMP,
    mastery_level TEXT DEFAULT '初学',  -- 初学/掌握/薄弱
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);

CREATE TABLE learning_style (
    id TEXT PRIMARY KEY,
    profile_id TEXT UNIQUE,
    prefer_socratic REAL DEFAULT 0.5,      -- 0.0~1.0
    avg_question_depth REAL DEFAULT 0.0,   -- 平均追问轮次
    image_question_ratio REAL DEFAULT 0.0, -- 图片提问占比
    total_questions INTEGER DEFAULT 0,
    total_followups INTEGER DEFAULT 0,
    FOREIGN KEY (profile_id) REFERENCES profiles(id)
);
```

#### knowledge_taxonomy（规划中，已废弃）

> ⚠️ 历史遗留：ChromaDB 斩断后，本 collection 不再使用。知识点概念管理已迁移至 Neo4j 图谱（Concept/Theorem/Formula + TEACH_IN + PREREQUISITE_OF 关系）。

ChromaDB collection，用于知识点标准化向量匹配：

```json
{
  "id": "topic_2_1_3",
  "text": "行列式的按行（列）展开",
  "metadata": {
    "chapter": "二、行列式",
    "section": "2.1 n阶行列式定义",
    "topic": "2.1.3 行列式的按行（列）展开",
    "standard_names": ["按行展开", "余子式", "代数余子式", "拉普拉斯展开"]
  }
}
```

---

## 4. 功能详细设计

### 4.1 知识点标准化大纲

#### 4.1.1 大纲结构

基于丘维声《高等代数》构建知识点树：

```json
{
  "subject": "高等代数",
  "textbooks": ["高等代数（上册）丘维声", "高等代数（下册）丘维声"],
  "taxonomy": [
    {
      "id": "1",
      "name": "一、多项式",
      "sections": [
        {
          "id": "1-1",
          "name": "1.1 多项式运算",
          "topics": [
            { "id": "1-1-1", "name": "多项式的定义与表示" },
            { "id": "1-1-2", "name": "多项式加法与乘法" }
          ]
        },
        {
          "id": "1-2",
          "name": "1.2 最大公因式",
          "topics": [
            { "id": "1-2-1", "name": "辗转相除法" },
            { "id": "1-2-2", "name": "最大公因式的性质" }
          ]
        }
      ]
    },
    {
      "id": "2",
      "name": "二、行列式",
      "sections": [
        {
          "id": "2-1",
          "name": "2.1 n阶行列式定义",
          "topics": [
            { "id": "2-1-1", "name": "排列与逆序数" },
            { "id": "2-1-2", "name": "n阶行列式定义" },
            { "id": "2-1-3", "name": "行列式的按行（列）展开" }
          ]
        }
      ]
    }
  ]
}
```

#### 4.1.2 向量化与归一流程

```
LLM返回knowledge_points
        │
        ▼
   原文向量化 → embedding_service.embed([point])
        │
        ▼
   ChromaDB知识树检索 → top-1结果
        │
        ▼
   similarity > 0.85 ──→ 归一到标准节点
        │
       ≤0.85 ──→ 新增提议（待人工确认）
```

**关键代码**：

```python
def normalize_topic(raw_topic: str, taxonomy_collection) -> str:
    """
    将LLM返回的知识点归一化到标准节点
    返回: 标准知识点ID
    """
    embedding = embedding_service.embed([raw_topic])[0]
    results = taxonomy_collection.query(
        query_embeddings=[embedding],
        n_results=1
    )
    if results['distances'][0][0] < 0.15:  # cosine distance < threshold
        return results['ids'][0][0]
    return None  # 未匹配到标准节点
```

### 4.2 追问意图分类

#### 4.2.1 分类定义

| 意图类型 | 描述 | 典型句式 | 画像影响 |
|---------|------|---------|---------|
| Clarification | 没听懂，需要更基础解释 | "为什么"、"什么意思"、"能详细点吗" | 标记为"薄弱" |
| Elaboration | 听懂了，想深入探究 | "还有呢"、"举个例子"、"再深入一点" | 标记为"求知欲强" |

#### 4.2.2 分类策略

**快速路径（规则匹配）**：

```python
clarification_signals = [
    "为什么", "不懂", "什么意思", "能详细", "还是不懂",
    "不太理解", "解释一下", "说清楚", "怎么来的", "为什么这样"
]
elaboration_signals = [
    "还有呢", "那", "除了", "再", "比如", "进一步",
    "然后呢", "接下来", "除此之外", "再举一例"
]

if any(s in question for s in clarification_signals):
    return "clarification"
if any(s in question for s in elaboration_signals):
    return "elaboration"
```

**精确路径（LLM分类）**：

```python
def classify_followup_intent(
    current_question: str,
    previous_qa: dict
) -> str:
    prompt = f"""用户刚才问："{previous_qa['question']}"
    AI回答了："{previous_qa['answer'][:100]}..."

    用户现在追问："{current_question}"

    判断用户追问的意图：
    - 如果用户是没听懂、要求更简单解释 → Clarification
    - 如果用户是听懂了想深入探究 → Elaboration

    只回答一个词："Clarification" 或 "Elaboration"
    """
    response = llm_service.client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return response.choices[0].message.content.strip()
```

### 4.3 持久化用户ID

#### 4.3.1 前端实现

```typescript
// App.tsx
const [userId] = useState(() => {
  const stored = localStorage.getItem('math_user_id');
  if (stored) return stored;
  const newId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  localStorage.setItem('math_user_id', newId);
  return newId;
});
```

#### 4.3.2 可选账号绑定（未来）

- 用户可选择绑定邮箱
- 绑定后 device_id 与 账号体系关联
- 支持跨设备同步画像数据

### 4.4 学习者画像更新流程

```
用户提问
    │
    ▼
┌─────────────────────────────────┐
│ 1. 保存chat_history             │
│ 2. 提取knowledge_points         │
│ 3. 调用classify_followup_intent │
│    判断clarification/elaboration │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 4. 知识点归一                    │
│    normalize_topic → taxonomy   │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 5. 更新topic_mastery表           │
│    asked_count++                │
│    correct_on_first++ (首次答对) │
│    need_hint++ (clarification)  │
│    mastery_level重新计算         │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ 6. 更新learning_style表          │
│    统计prefer_socratic等指标    │
└─────────────────────────────────┘
```

### 4.5 画像洞察生成

```python
def generate_insight(profile: LearnerProfile) -> Insight:
    prompt = f"""分析以下学习者的画像数据，生成简短洞察：

    知识点掌握情况：
    {json.dumps(topic_mastery, ensure_ascii=False)}

    学习风格：
    - 苏格拉底偏好度：{prefer_socratic:.0%}
    - 平均追问深度：{avg_question_depth:.1f}轮
    - 图片提问占比：{image_question_ratio:.0%}

    薄弱知识点：{weak_topics}
    强项知识点：{strong_topics}

    请给出：
    1. 3个主要优势
    2. 3个需加强的领域
    3. 推荐的下一个学习主题
    4. 一段50字以内的总体评价

    回答格式：JSON
    """
```

---

## 5. 技术架构图

```
┌──────────────────────────────────────────────────────────────────────┐
│                          前端  React + Vite                           │
│  ┌─────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ChatPanel │ │PDFViewer │ │PageMarker│ │Exercise  │ │Profile    │  │
│  │          │ │          │ │MarkerPop │ │Panel     │ │Panel      │  │
│  └─────────┘ └──────────┘ └──────────┘ └──────────┘ └───────────┘  │
│        ↕              ↕          ↕           ↕                          │
│  localStorage ← 教材偏好/userId生成                                  │
└──────────────────────────────────────────────────────────────────────┘
                              │
                              ▼ HTTP/SSE
┌──────────────────────────────────────────────────────────────────────┐
│                     后端  FastAPI (lifespan)                          │
│                                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌───────┐ │
│  │qa      │ │auth    │ │exercise│ │textbook│ │chat    │ │profile│ │
│  │router  │ │router  │ │router  │ │router  │ │router  │ │router │ │
│  └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬───┘ │
│      │           │          │          │          │          │      │
│  ┌───┴───────────┴──────────┴──────────┴──────────┴──────────┴──┐  │
│  │                      services 层 (10 模块)                     │  │
│  │  prompt_engine ← scaffolding_controller ← prerequisite_checker │  │
│  │  llm_service  │  exercise_generator  │  error_analyzer        │  │
│  │  sympy_sandbox│  insight_generator   │  ocr                   │  │
│  │  diagnostic_worker (5min)  │  pending_worker (60s)            │  │
│  └───────────────────────────────────────────────────────────────┘  │
│      │                    │                │                         │
│  ┌───┴────────┐   ┌──────┴──────┐   ┌────┴──────────┐              │
│  │ Neo4j      │   │ SQLite       │   │ LLM API       │              │
│  │ knowledge  │   │ (12 张表)    │   │ DeepSeek/     │              │
│  │ graph      │   │ WAL 模式     │   │ DashScope     │              │
│  └────────────┘   └─────────────┘   └───────────────┘              │
└──────────────────────────────────────────────────────────────────────┘

**调用链路**：
用户提问 → qa_router → prompt_engine(10路信号) → llm_service → SSE流式返回
                             ↑
     scaffolding_controller ← knowledge_stages_db
     prerequisite_checker   ← whitelist_db(Neo4j)
     math_profile_db        ← diagnostic_report
     textbook_section_db     ← page_context
```

**数据存储说明**：

| 存储 | 用途 | 状态 |
|------|------|------|
| SQLite | 用户认证、对话历史（含 marker）、用户画像、知识点统计、认知阶段、教材章节、题库 | ✅ 线上 |
| Neo4j | 知识图谱（Concept/Theorem/Formula + TEACH_IN + PREREQUISITE_OF） | ✅ 上册已导入 |
| LLM API | DeepSeek V4 Pro（QA 问答）/ DashScope qwen3-vl（截图） | ✅ 线上 |
| ChromaDB | 向量检索（已斩断，不再调用） | ❌ 已下线 |

---

## 6. 部署方案

### 6.1 当前部署（阿里云）

| 组件 | 位置 | 存储 |
|------|------|------|
| 前端 | Nginx 静态文件 (8.134.195.113) | `/opt/ai-math/frontend/dist/` |
| 后端 | FastAPI + systemd (ai-math.service) | `/opt/ai-math/` |
| Neo4j | Neo4j Aura 云端实例 | 5,225 节点 / 24,802 关系 |
| SQLite | 服务器本地文件 | `/opt/ai-math/data/learning.db` |

### 6.2 未来扩展路径

| 阶段 | 方案 | 适用场景 |
|------|------|---------|
| 当前 | SQLite + Neo4j Aura | 竞赛 Demo 阶段 |
| 阶段一 | SQLite 迁移至 PostgreSQL | 用户量增长 |
| 阶段二 | HTTPS 证书 + 域名绑定 | 正式上线 |
| 阶段三 | 引入 Redis 缓存 | 高并发场景

---

## 7. 接口设计

### 7.1 现有接口

**问答系统**：

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/qa/solve | 题目答疑（非流式，保留兼容） |
| POST | /api/qa/solve-stream | 流式问答 SSE（截图+文字，思考过程+回答） |

**教材管理**：

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/textbook/list | 获取教材列表 |
| GET | /api/textbook/{id} | 获取教材详情 |
| POST | /api/textbook/upload | 上传教材 |

**用户认证**：

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/auth/register | 用户注册 |
| POST | /api/auth/login | 用户登录 |
| POST | /api/auth/anonymous | 匿名访问 |
| GET | /api/auth/me | 获取当前用户信息（JWT） |
| PUT | /api/auth/profile | 更新基础画像 |
| GET | /api/auth/math-profile | 获取 15 维数学素养画像 |
| PUT | /api/auth/math-profile | 更新数学素养画像 |
| GET | /api/auth/knowledge-stats | 获取知识点统计 |
| GET | /api/auth/diagnostic-history | 获取诊断历史 |

**用户偏好**：

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/profile/textbook-preference | 获取教材+页码偏好 |
| POST | /api/profile/textbook-preference | 保存教材+页码偏好 |

**对话历史**：

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/chat/history/{user_id} | 获取问答历史（含 page_number/marker） |
| POST | /api/chat/migrate | 匿名用户登录后迁移问答历史 |

**练习题系统**：

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/exercise/generate | 流式出题 SSE（LLM + SymPy 验算） |
| GET | /api/exercise/list | 获取用户历史题目 |
| POST | /api/exercise/{id}/submit | 提交答案（LLM 同步批改 + 异步错因分析） |
| POST | /api/exercise/{id}/hint | 获取渐进提示（3 级） |
| POST | /api/exercise/{id}/report-error | 用户纠错（标记质量分 -1） |

### 7.2 规划中接口

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/profile/{user_id}/insight | 获取 AI 生成的画像洞察 |
| GET | /api/report/{user_id} | 学习报告生成 |

---

## 8. 文件结构

```
d:\ai-math\
├── app/
│   ├── main.py                 # FastAPI 入口 + lifespan（双 Worker 启动）
│   ├── config.py               # .env 配置管理（QA/PROFILE LLM 两套 + Neo4j）
│   ├── auth/
│   │   └── jwt_handler.py      # JWT 签发/验证
│   ├── routers/                # 6 个路由
│   │   ├── qa.py               # 问答 SSE + page_context + whitelist + 认知闭环
│   │   ├── auth.py              # 注册/登录/匿名 + 画像 + 诊断历史
│   │   ├── exercise.py          # 练习题系统（出题/批改/提示/纠错）
│   │   ├── textbook.py          # 教材管理
│   │   ├── profile.py           # 教材偏好持久化
│   │   └── chat.py              # 问答历史 + marker 迁移
│   ├── services/               # 10 个服务模块
│   │   ├── prompt_engine.py     # 动态 Prompt 组装（10 路信号）
│   │   ├── scaffolding_controller.py # 四级学徒脚手架
│   │   ├── prerequisite_checker.py   # Neo4j 前置知识缺口检测
│   │   ├── llm_service.py       # LLM 调用（QA + Profile 双客户端）
│   │   ├── exercise_generator.py # 出题 Prompt + Markdown 解析
│   │   ├── error_analyzer.py    # 错因诊断
│   │   ├── sympy_sandbox.py     # SymPy 验算沙箱
│   │   ├── insight_generator.py # 学习洞察报告
│   │   ├── diagnostic_worker.py # 后台诊断轮询（每 5min）
│   │   ├── pending_worker.py    # pending 队列消费（每 60s）
│   │   └── ocr.py               # OCR
│   ├── db/                      # 16 个领域模块（v2.1 拆分）
│   │   ├── connection.py        # 建表 DDL（12 张表）+ 连接管理
│   │   ├── auth_db.py           # 用户认证
│   │   ├── user_profile_db.py   # 基础画像（旧）
│   │   ├── math_profile_db.py   # 15 维数学素养画像 + 教材偏好
│   │   ├── math_profile_standard.py # LLM 评分 rubric
│   │   ├── textbook_db.py       # 教材 CRUD
│   │   ├── textbook_section_db.py   # 章节页码映射 + 上下文查询
│   │   ├── chat_history_db.py   # 问答历史（含 marker 字段）
│   │   ├── chat_log_db.py       # 诊断日志队列
│   │   ├── knowledge_stages_db.py   # 六阶段认知追踪 + pending 消费
│   │   ├── knowledge_stats_db.py    # 知识点统计
│   │   ├── question_assessment_db.py # 诊断快照存储
│   │   ├── exercise_bank_db.py  # 题库
│   │   ├── whitelist_db.py      # Neo4j 白名单查询
│   │   ├── diagnostic.py        # 实时诊断触发 + pipeline
│   │   └── __init__.py          # 导出 get_conn, init_db
│   └── models/
│       └── schemas.py           # Pydantic 模型
├── frontend/src/
│   ├── App.tsx                  # 主组件（状态中枢 + 偏好持久化）
│   ├── components/              # 19 个组件
│   │   ├── ChatPanel.tsx        # 聊天面板（SSE + LaTeX 渲染）
│   │   ├── PDFViewer.tsx        # PDF 阅读器
│   │   ├── PageMarker.tsx       # 页面提问标记点（红蓝圆点）
│   │   ├── MarkerPopover.tsx    # 标记弹窗（问答查看/删除）
│   │   ├── ExercisePanel.tsx    # 练习题面板
│   │   ├── LatexInput.tsx       # LaTeX 输入
│   │   ├── MatrixEditor.tsx     # 矩阵编辑器
│   │   ├── AiBall.tsx           # 移动端浮动 AI 球
│   │   ├── ScreenCapture.tsx    # 截图
│   │   ├── ImageCropper.tsx     # 移动端截图裁剪
│   │   ├── ProfilePanel.tsx     # 画像面板（雷达图/轨迹/薄弱点）
│   │   ├── RadarChart.tsx       # 五维雷达图
│   │   ├── WeakPointGraph.tsx   # 薄弱点柱状图
│   │   ├── LearningTrajectory.tsx # 诊断历史轨迹
│   │   ├── BasicInfoEditor.tsx  # 基本信息编辑
│   │   ├── AuthModal.tsx        # 登录/注册弹窗
│   │   ├── ErrorBoundary.tsx    # 错误边界
│   │   └── TextbookViewer.tsx   # 教材 Markdown 浏览器
│   ├── hooks/
│   │   ├── useAuth.ts           # 认证状态管理
│   │   └── useTextbookPreference.ts # 教材偏好持久化
│   ├── services/
│   │   └── api.ts               # API 调用 + SSE 流式解析
│   └── types/
│       └── index.ts             # TypeScript 类型定义
├── pipeline/                    # 知识图谱构建管道
│   ├── build_kg.py              # 核心图谱构建脚本
│   └── 教材标题分级工具.py       # Markdown 标题结构化
├── scripts/
│   └── build_page_map.py        # PDF → textbook_sections 映射构建（上下册）
├── tests/                       # 测试文件
├── data/learning.db             # SQLite 数据库
└── import_textbook.py           # 教材导入工具（⚠️ 历史遗留，ChromaDB 已斩断）
```

---

## 9. 里程碑

| 阶段 | 内容 | 状态 |
|------|------|--------|
| M1 | 修复LaTeX渲染、流式滚动、渲染顺序 | ✅ 已上线 |
| M2 | 建立 users + math_profiles + user_knowledge_stats + question_assessments + chat_logs 表 | ✅ 已上线 |
| M3 | ~~实现知识点标准化大纲 + 向量归一~~ 已用 Neo4j 图谱替代 ChromaDB 向量方案 | ✅ 已上线 |
| M4 | 实现追问意图分类（Clarification/Elaboration） | ⏳ 规划中 |
| M5 | 持久 userId + 画像更新流程 + 诊断 Pipeline | ✅ 已上线 |
| M6 | ProfilePanel 前端展示（雷达图+轨迹+薄弱点） | ✅ 已上线 |
| M7 | 画像洞察生成（LLM 分析） | ⏳ 规划中 |
| Phase 1 | 平板竖屏全屏PDF + AiBall + 移动端截图裁剪 + IIFE Worker兼容 | ✅ 已上线 |
| Phase 2 | 动态 Prompt 引擎 + 前置检测 + 智能出题 + 错因分析 | ⏳ 规划中 |
| Phase 3 | 学习报告 + Demo 模式 + 竞赛材料 | ⏳ 规划中 |

---

## 10. 验收标准

### M1 验收

- [x] 思考过程区域LaTeX公式正确渲染
- [x] 回答内容LaTeX公式正确渲染
- [x] 思考过程显示在回答上方
- [x] 流式输出时右侧面板不自动下滑

### M3 验收

- [x] 知识树大纲覆盖高等代数主要章节（已通过 Neo4j 图谱实现，替代 ChromaDB 向量方案）
- [x] 知识点通过 Neo4j PREREQUISITE_OF 关系链进行教学边界控制

### M4 验收

- [ ] "为什么这个公式是这样" → Clarification
- [ ] "还有其他的例子吗" → Elaboration
- [ ] 分类准确率 > 80%（抽样人工评估）

### M5 验收

- [x] 刷新页面后 userId 保持不变
- [x] 历史问答记录正确关联到同一profile

### M6 验收

- [x] 五维雷达图正确展示 15 维分数均值
- [x] 学习轨迹展示最近诊断历史
- [x] 薄弱点分析柱状图展示高低频知识点

---

---

---

## 13. 三阶段架构升级（v0.3 新增）

### 13.1 背景问题

| 问题 | 现状 | 影响 |
|------|------|------|
| 截图跨页 | 题目在A页末尾与A+1页开头被截断 | AI看不到完整题目 |
| 向量检索不准 | "这题怎么做" 匹配到无关内容 | 回答不相关 |
| 超纲讲解 | AI不知道学生学到哪了 | 讲解太深奥 |
| 响应慢 | 多跳串行调用 | TTFT高 |

### 13.2 三阶段概述

| 阶段 | 目标 | 核心改动 |
|------|------|---------|
| 第一阶段 | 基础设施建设 | 页码映射 + 图谱双层架构 |
| 第二阶段 | 在线业务优化 | 并发拉取 + 白名单过滤 |
| 第三阶段 | 工程性能优化 | 内存预热 + 斩断OCR |

---

### 🛠️ 第一阶段：基础设施建设（离线数据管道）

**目标**：建立确定性的知识边界与页码锚点。

#### 1.1 页码映射词典

**问题**：前端PDFViewer显示物理页码，后端Markdown无页码对应。

**方案**：
```
PDF文件 → PyMuPDF逐页读取 → textbook_pages表
存储：(textbook_id, page_number, content, sequence_id)
```

**数据库**：
```sql
CREATE TABLE textbook_pages (
    id TEXT PRIMARY KEY,
    textbook_id TEXT NOT NULL,
    page_number INTEGER NOT NULL,     -- 物理页码
    content TEXT NOT NULL,
    sequence_id TEXT,                 -- 章节拓扑ID
    FOREIGN KEY (textbook_id) REFERENCES textbooks(id)
);
```

#### 1.2 图谱双层架构

**问题**：现有Neo4j只有概念节点，无法知道概念属于哪个章节。

**方案**：
1. **物理层编号**：生成 `sequence_id`（如 `V1-C03-S02-U00-T00`）
2. **逻辑层清洗**：LLM离线提取纯数学概念
3. **双层锚定**：建立 `TEACH_IN` 关系

**sequence_id格式**：
```
V1-C03-S02-U00-T00
└─┘└──┘└──┘└──┘└──┘
版本  章节  小节  单元  主题
```

**离线脚本**：
```python
# scripts/build_graph_topology.py
def process_textbook(textbook_id: str, pdf_path: str):
    # 1. 读取PDF，生成page_number → sequence_id映射
    # 2. 解析Markdown章节结构
    # 3. 调用LLM提取概念
    # 4. 写入Neo4j：概念节点 + TEACH_IN关系
```

---

### 🚀 第二阶段：在线业务逻辑优化

**目标**：并发获取所有约束条件，组装神级Prompt。

#### 2.1 前端参数补全

```typescript
interface QARequest {
  user_id: string;
  question: string;
  image_data: string;      // 截图base64
  textbook_id: string;
  page_number: number;      // PDF物理页码（新增）
}
```

#### 2.2 后端并发拉取

**严禁串行！必须并发执行三大任务：**

```python
async def solve_with_vision_stream(request: QARequest):
    # 三大任务并发执行
    task_a = asyncio.create_task(get_page_context(textbook_id, page_number))
    task_b = asyncio.create_task(get_whitelist(textbook_id, page_number))
    task_c = asyncio.create_task(get_user_profile(user_id))

    context, whitelist, profile = await asyncio.gather(task_a, task_b, task_c)

    # 组装Prompt
    prompt = build_ultimate_prompt(context, whitelist, profile)
```

#### 2.3 动态知识白名单

**宏观放行**（基于章级）：
```
允许使用第1章到第3章的所有常规代数定理
```

**微观限制**（Top 10-15个紧邻前置）：
```
只能使用以下核心概念：行列式, 矩阵乘法, 逆矩阵, 矩阵的秩, ...
```

---

### ⚠️ 第三阶段：工程优化

#### 3.1 图谱内存预热

**问题**：实时Neo4j查询有50-200ms延迟。

**方案**：服务启动时全量加载到内存。

```python
@app.on_event("startup")
async def preload_knowledge_graph():
    KNOWLEDGE_WHITELIST_CACHE = {}
    for seq_id in get_all_sequence_ids():
        KNOWLEDGE_WHITELIST_CACHE[seq_id] = get_prerequisites(seq_id)
```

**性能对比**：
| 方案 | 延迟 | QPS |
|------|------|-----|
| 实时Neo4j | 50-200ms | ~100 |
| 内存缓存 | 0ms | ~10000+ |

#### 3.2 斩断OCR直出

**改进前**（串行多跳）：
```
截图 → OCR → 向量检索 → LLM回答 (5-8秒)
```

**改进后**（单次直出）：
```
截图 + page_number → 直接上下文 → Qwen-VL (3-5秒)
```

---

### 13.3 预估工作量

| 阶段 | 时间 |
|------|------|
| 第一阶段 | 8-10小时 |
| 第二阶段 | 6-8小时 |
| 第三阶段 | 3-4小时 |
| **总计** | 17-22小时 |

---

### 13.4 待建文件清单

| 阶段 | 文件 | 说明 |
|------|------|------|
| 第一阶段 | `scripts/build_graph_topology.py` | 离线图谱构建脚本 |
| 第一阶段 | `app/db/sqlite.py` (修改) | 新增textbook_pages表 |
| 第二阶段 | `app/routers/qa.py` (修改) | 并发拉取重构 |
| 第三阶段 | `app/main.py` (修改) | 内存预热 |
| 第三阶段 | `app/db/knowledge_cache.py` | 内存缓存模块 |

---

## 11. 自定义工具脚本

### 11.1 工具清单

| 工具名称 | 文件 | 用途 |
|---------|------|------|
| 教材标题分级 | `教材标题分级.py` | 将MinerU输出的原始Markdown转换为5级标题结构 |
| 知识图谱构建 | `build_kg.py` | 从结构化Markdown提取概念节点和关系，入库Neo4j |
| 教材导入 | `import_textbook.py` | 将Markdown向量化存入ChromaDB和SQLite |

---

### 11.2 教材标题分级 `教材标题分级.py`

**用途**：MinerU转换后的Markdown只有基础的 `#` 标题，需要转换为5级层级结构用于知识图谱构建。

**输入**：MinerU输出的原始Markdown
```
# 第X章
## X.X 节名
### X.X.X 小节名
...
```

**输出**：5级结构化Markdown
```
# 第X章                    (Level 1 - Chapter)
## X.X 节名                (Level 2 - Section)
### X.X.X 小节名           (Level 3 - Subsection)
#### 一、二、宏观概念        (Level 4 - Topic)
##### 定理1/定义1/例1      (Level 5 - Entity)
```

**核心规则**：
| 原格式 | 转换规则 |
|--------|---------|
| `# 第X章` | → `#` (Level 1) |
| `## X.X` | → `##` (Level 2) |
| `### X.X.X` | → `###` (Level 3) |
| `#### 一、二、` | → `####` (Level 4) |
| `##### 定理/定义/例题` | → `#####` (Level 5) |

**附加处理**：
- 识别并标记"习题"区域，分离题目和答案
- 提取纯数学实体（定理、定义、引理、推论、性质）
- 清理不规范的多余井号干扰

---

### 11.3 知识图谱构建 `build_kg.py`

**用途**：从结构化Markdown中提取数学实体和关系，建立Neo4j知识图谱。

**依赖**：
- LangChain
- Neo4j Graph Database
- GLM-4-plus 大模型API

**核心流程**：
```
1. 读取5级结构化Markdown
         ↓
2. 按标题层级切分文本块（MarkdownHeaderTextSplitter），保留章节metadata
         ↓
3. 对每个文本块调用LLM提取4类实体和5类关系
         ↓
4. 实体消歧：局部节点（例/题）自动加章节前缀，全局概念保持原名
         ↓
5. 增量写入Neo4j（MD5缓存拦截已处理块）
```

**实体类型（4类）**：
| 类型 | 说明 |
|------|------|
| Concept | 数学概念、定义 |
| Theorem | 定理、引理、推论、性质 |
| Formula | 重要数学公式名称 |
| Problem | 例题、习题、答案 |

**关系类型（5类）**：
| 类型 | 说明 |
|------|------|
| PREREQUISITE_OF | 前置知识，A是B的前提 |
| DERIVED_FROM | 推导自，A推导出了B |
| USES_CONCEPT | 题目使用了某个概念 |
| HAS_ANSWER | 题目拥有答案 |
| RELATED_TO | 其他相关 |

**实体消歧规则**：
- 名字含"例"、"题"、"习题"的节点 → 视为局部节点，ID拼接章节前缀
  - 例如：`第1章_1.1.1_例2`
- 其他实体（概念、定理、公式）→ 视为全局概念，保持原名，可跨章节合并

**增量处理机制**：
- 首次运行生成 `processed_chunks_cache.json`，记录每个chunk的MD5指纹
- 再次运行时，已处理的chunk直接跳过，不消耗API额度
- 失败块记录到 `failed_chunks.log`，供人工重试

**输出格式**：
```json
{
  "nodes": [
    {"id": "行列式", "type": "Concept"},
    {"id": "第1章_1.1.1_例2", "type": "Problem"}
  ],
  "edges": [
    {"source": "第1章_1.1.1_例2", "target": "行列式", "type": "USES_CONCEPT"}
  ]
}
```

**节点元数据**：
- `id`：全局唯一标识（局部节点含章节前缀）
- `name`：原始名称（用于前端展示）
- `chapter`：所属章节
- `created_at`/`last_updated`：时间戳

---

### 11.4 教材导入 `import_textbook.py`

**用途**：将Markdown教材向量化并存入ChromaDB和SQLite。

**核心流程**：
```
1. 解析Markdown结构（Chapter → Section）
         ↓
2. 语义分块（按习题/例题/定义等边界）
         ↓
3. 批量向量化（Embedding API）
         ↓
4. 存入ChromaDB + SQLite
```

**语义分块规则**：
```python
SEMANTIC_PATTERNS = [
    (r'习题\d+', 'exercise'),        # 习题5.7
    (r'典型例题', 'example'),         # 典型例题
    (r'定义', 'definition'),          # 定义
    (r'定理', 'theorem'),            # 定理
    (r'证明', 'proof'),              # 证明
    ...
]
```

---

### 11.5 数据管道完整流程

```
PDF教材 (丘维声《高等代数》上册/下册)
         │
         ▼ MinerU转换
Markdown (基础#标题) + 教材标题分级.py
         │
         ▼ 5级结构化Markdown
structured_algebra_*.md
         │
         ├─→ build_kg.py ─→ Neo4j图数据库
         │
         └─→ import_textbook.py ─→ ChromaDB + SQLite
```

---

## 12. 项目成果（v0.4 新增）

### 12.1 数据管道成果

上册（高等代数创新教材 上 丘维声）数据导入完成，以下为执行步骤：

**步骤 1：入库 `textbook_sections` 表（页码映射）**

```bash
cd d:\ai-math
python scripts/build_page_map.py --volume 1
```

- **脚本**: `scripts/build_page_map.py`
- **数据来源**: PDF书签 + Markdown正文缝合
  - PDF: `d:/ai math/高等代数创新教材 上 丘维声_outlined.pdf`
  - MD: `d:/ai math/structured_高代上.md`
- **入库结果**: 35条记录（34章节 + 1答案区）
- **表结构**: `textbook_sections` (id, textbook_id, sequence_id, chapter_num, chapter_name, content, start_page, end_page)
- **查询验证**: `get_section_by_page("高代上-丘维声", 50)` → `V1-C01-S03`（1.3 数域）

**步骤 2：导入 Neo4j 图谱（概念节点 + TEACH_IN 关系）**

```bash
cd d:\ai-math
python build_kg.py --volume 1 --clear
```

- **脚本**: `build_kg.py`（位于项目根目录）
- **数据来源**: `d:/ai math/structured_高代上.md`（5级结构化Markdown）
- **Neo4j 连接**: `bolt://localhost:7687`，用户 `neo4j`
- **节点类型**: Concept, Theorem, Formula, Problem
- **关系类型**: PREREQUISITE_OF, TEACH_IN, RELATED_TO, USES_CONCEPT, DERIVED_FROM, HAS_ANSWER
- **sequence_id 格式**: `V1-C{章号:02d}-S{节号:02d}`（如 `V1-C01-S03`）
- **Section 节点**: 每个教材节对应一个 Section 节点，sequence_id 作为唯一标识
- **TEACH_IN 关系**: Concept/Theorem/Formula → Section（通过 sequence_id 锚定）

**步骤 3：启动后端服务**

```bash
cd d:\ai-math
python -m uvicorn app.main:app --reload --port 8000
```

---

### 12.2 核心模块改动（Phase 1 + Phase 2 累计）

**Phase 1 — 基础设施建设**：

| 文件 | 改动 |
|------|------|
| `app/db/connection.py` + 15 子模块 | 原 sqlite.py 拆分为 16 模块，新增 12 张表的建表 DDL 和 CRUD |
| `app/db/textbook_section_db.py` | 新增 `get_page_context`（页码→章节）、`save_textbook_section` |
| `app/db/whitelist_db.py` | Neo4j 白名单查询（TEACH_IN + PREREQUISITE_OF） |
| `app/routers/qa.py` | `prompt_engine.build_prompt` 组装 10 路信号 Prompt；并发 page_context + whitelist |
| `scripts/build_page_map.py` | 支持上下册双册配置；`verify_volume()` 验证入库结果 |
| `app/routers/chat.py` | `ask_question` 已注释（ChromaDB 链已斩断） |
| `frontend/src/App.tsx` | `PRESET_PDFS` 同步上册/下册 textbookId |

**Phase 2 — 在线业务 + 掌握学习闭环**：

| 文件 | 改动 |
|------|------|
| `app/services/prompt_engine.py` | **新建** — 动态 Prompt 组装（角色/规则/认知/画像/白名单/前置/上下文/历史） |
| `app/services/scaffolding_controller.py` | **新建** — 四级学徒脚手架 + 子模式偏移 + 防抖 |
| `app/services/prerequisite_checker.py` | **新建** — Neo4j PREREQUISITE_OF 链前置知识缺口检测 |
| `app/routers/exercise.py` | **新建** — /api/exercise/*（出题·批改·提示·纠错 5 端点） |
| `app/services/exercise_generator.py` | **新建** — 出题 Prompt + Markdown 解析 + 阶段配置 |
| `app/services/sympy_sandbox.py` | **新建** — SymPy 验算沙箱（限制危险操作） |
| `app/services/error_analyzer.py` | **新建** — 错因诊断 + stage_delta 写入 |
| `app/db/exercise_bank_db.py` | **新建** — 题库 CRUD |
| `app/db/knowledge_stages_db.py` | **新建** — 六阶段认知追踪 + pending 队列消费 |
| `app/services/pending_worker.py` | **新建** — 后台 Worker 每 60s 消费 pending_stage_updates |
| `app/routers/profile.py` | **新建** — 教材偏好持久化（localStorage + 云端双源） |
| `frontend/src/components/PageMarker.tsx` | **新建** — PDF 页面提问标记点（红蓝圆点） |
| `frontend/src/components/MarkerPopover.tsx` | **新建** — 标记弹窗（问答查看/删除） |
| `frontend/src/components/ExercisePanel.tsx` | **新建** — 练习题面板 |
| `frontend/src/hooks/useTextbookPreference.ts` | **新建** — 教材偏好 Hook |

---

### 12.3 验证命令

```bash
# 验证 textbook_sections 入库
python -c "
from app.db.sqlite import get_section_by_page, get_sections_by_textbook
s = get_section_by_page('高代上-丘维声', 50)
print(f'sequence_id: {s[\"sequence_id\"]}, 章节: {s[\"chapter_name\"]}, 内容长度: {len(s[\"content\"])}')
sections = get_sections_by_textbook('高代上-丘维声')
print(f'上册共 {len(sections)} 条记录')
"

# 验证 get_whitelist 查询 Neo4j
python -c "
from app.db.sqlite import get_whitelist
w = get_whitelist('高代上-丘维声', 'V1-C01-S03')
print(f'macro: {w["macro"]}')
print(f'micro: {w["micro"]}')
"
```

---

### 12.4 可选改进项：导入高代下册

**定位**：未来可选改进项，当前仅上册可用，下册导入因成本原因暂停。

**已完成的部分**：
- `scripts/build_page_map.py` 已支持 `--volume 2` 参数
- `textbook_sections` 表已有下册记录（`高代下-丘维声`，V2 前缀）
- `get_page_context` 和 `get_whitelist` 已支持 V1/V2 前缀

**待完成项**（成本优先，暂缓）：
1. `scripts/build_page_map.py --volume 2` — MD 解析缺损，章节 7.11、9.9、10.6、10.7 在 `structured_高代下.md` 中缺失，需修复 MD 或调整解析逻辑
2. `build_kg.py --volume 2` — Neo4j 下册图谱导入（约 30 个 Section 节点 + 对应 Concept/Theorem/Formula 节点）
3. 下册前端 PDF 映射确认（`高等代数下册_丘维声.pdf` 与 `高代下-丘维声` 的 page_number 对应关系）

**下册当前数据状态**：

| 项目 | 状态 |
|------|------|
| textbook_sections 入库 | ✅ 已入库（~30条，有缺损） |
| Neo4j 图谱导入 | ❌ 未执行 |
| 前端 PDF 映射 | ✅ 已配置（App.tsx PRESET_PDFS） |

---

*文档版本：v0.7，最后更新 2026-05-06*
