# KG v2 知识图谱构建计划

> 状态：最终版 | 日期：2026-06-09

---

## 一、背景与目标

### 1.1 项目背景

"学数有道"（智学助手）基于 Neo4j 知识图谱实现**图谱约束防止 AI 超纲**，是揭榜挂帅比赛核心卖点。当前线上 Neo4j Aura 仅有高等代数上册 KG（5225 节点 / 24802 关系），存在三个问题：

| 问题 | 现状 | 影响 |
|------|------|------|
| 英文概念名 | 47.8%（Skew_Symmetric_Matrix 等） | 与中文教材不匹配，knowledge_stages 表无法关联 |
| TOC 目录噪音 | Section 节点混入目录条目 | 白名单查询返回无意义内容 |
| 缺少跨节关系 | 旧方案逐块发 LLM，每块看不到其他节 | 前置知识链断裂，"防超纲"不完整 |

### 1.2 目标

用 **规则锚点 + LLM 判关系** 的混合方案重建四本教材的知识图谱，写本地 Neo4j Desktop（不动 Aura），经验证后同步线上。

| 教材 | 状态 |
|------|------|
| 高等代数上册（丘维声） | 先导——有旧 KG 可做 A/B 对比 |
| 高等代数下册（丘维声） | 第二批 |
| 高等数学上册（黄立宏） | 第二批 |
| 高等数学下册（黄立宏） | 第二批 |
| 离散数学第六版（耿素云） | 第三批 |

---

## 二、消费端契约（前置分析）

KG 不是孤立系统。构建前必须明确四个消费端到底需要什么字段。

### 2.1 消费端一览

| # | 模块 | 入口 | 功能 |
|---|------|------|------|
| C1 | `app/routers/auth.py:352` | `GET /api/auth/knowledge-graph` | 知识图谱可视化：薄弱概念 → 前后置依赖 |
| C2 | `app/services/prerequisite_checker.py` | `get_prereq_gaps()` | 前置知识检查：学生学某节前，前置是否掌握 |
| C3 | `app/db/whitelist_db.py` | `get_whitelist()` | 白名单生成：当前章节允许使用的知识点范围 |
| C4 | `app/db/diagnostic.py` | `get_concepts_by_sequence_id()` / `get_prerequisite_chain()` | 诊断溯源：该章节涉及的概念列表 + 前置链 |

### 2.2 各消费端对 Neo4j 的依赖

#### C1: knowledge-graph（auth.py）

```
输入: JWT → user_id
      SQLite knowledge_stages 中 stage ≤ 2 的 concept_name

Neo4j 查询:
  1. MATCH (c:Concept {name: $name})                    -- 精确匹配 Concept.name
  2. MATCH (c:Concept) WHERE c.name CONTAINS $name      -- 模糊匹配（fallback）
  3. 查前置: MATCH (pre)-[:PREREQUISITE_OF]->(n)        -- ⚠️ 当前 BUG：方向反了
  4. 查后置: MATCH (n)-[:PREREQUISITE_OF]->(dep)        -- ⚠️ 当前 BUG：方向反了

依赖字段:  Concept.name（精确 + CONTAINS）
依赖关系:  PREREQUISITE_OF（Concept → Concept）

输出 JSON:
{
  "weak_concepts": [{
    "name": "行列式",
    "stage": 1, "stage_label": "入门",
    "prerequisites": [{"name": "矩阵", "stage": 3, "stage_label": "应用"}],
    "dependents": [{"name": "特征值", "stage": null, "stage_label": "未知"}]
  }]
}
```

#### C2: prerequisite_checker（prerequisite_checker.py）

```
输入: sequence_id (例: "V1-C01-S01-U00-T00"), user_id

Neo4j 查询:
  1. MATCH (s:Section)-[:TEACH_IN]-(c) WHERE s.sequence_id STARTS WITH $seq_id
  2. MATCH (pre)-[:PREREQUISITE_OF*1..2]->(c)           -- ⚠️ 当前 BUG：方向反了

依赖字段:  Section.sequence_id（STARTS WITH）
依赖关系:  TEACH_IN（双向），PREREQUISITE_OF（1~2 跳）

输出: [{name, stage, is_gap}]
```

#### C3: whitelist_db（whitelist_db.py）

```
输入: textbook_id, sequence_id (例: "V1-C01-S01")

Neo4j 查询:
  1. MATCH (n)-[:TEACH_IN]->(s:Section) WHERE s.sequence_id STARTS WITH $seq_prefix
     AND labels(n)[0] IN ['Concept','Theorem','Formula']    -- ⚠️ labels(n)[0] 不安全
     RETURN n.id, n.name, labels(n)[0]
  2. MATCH (pre:Concept)-[:PREREQUISITE_OF]->(c {id: $nid})  -- ✅ 方向正确

依赖字段:  Section.sequence_id, n.id, n.name, 标签 Concept|Theorem|Formula
依赖关系:  TEACH_IN（n→Section），PREREQUISITE_OF

输出: {macro: "允许使用第1章到第N章的...", micro: "知识点1、知识点2、..."}
```

#### C4: diagnostic.py

```
函数 A: get_concepts_by_sequence_id()
  1. MATCH (s:Section)<-[:TEACH_IN]-(c) WHERE s.sequence_id STARTS WITH $seq_prefix
     AND (c:Concept OR c:Theorem OR c:Formula)
     RETURN c.id as concept_name                           -- ⚠️ 返回 id 而非 name
  2. Fallback: MATCH (c:Concept) WHERE c.id CONTAINS $seq_prefix

函数 B: get_prerequisite_chain()
  1. MATCH (pre)-[:PREREQUISITE_OF]->(n:Concept {id: $topic})  -- ⚠️ 当前 BUG：方向反了
  2. Fallback: MATCH (n)-[:RELATED_TO]-(related)               -- ⚠️ 即将删除

依赖字段:  Section.sequence_id, c.id, c.name, Concept.id, 标签 Concept|Theorem|Formula
依赖关系:  TEACH_IN, PREREQUISITE_OF, RELATED_TO（回退）
```

### 2.3 消费端契约总结

**KG v2 必须提供的 Neo4j 数据**：

| 节点 | 必需属性 | 必需标签 |
|------|---------|---------|
| Section | `sequence_id` (String, `V1-C{02d}-S{02d}-U{02d}-T00`) | `Section` |
| KnowledgePoint | `id` (唯一标识), `name` (中文显示名) | 至少有 `Concept`；定理/公式额外保留 `Theorem`/`Formula` |

| 关系 | 方向 | 说明 |
|------|------|------|
| `TEACH_IN` | `(KnowledgePoint)-[:TEACH_IN]->(Section)` | 知识点归属哪个节 |
| `PREREQUISITE_OF` | `(前置概念)-[:PREREQUISITE_OF]->(后置概念)` | A 是 B 的前置知识 |

**关键约束**（如果违反，消费端直接失效）：

1. `knowledge_stages.concept_name` 必须能匹配 `Concept.name`（且 diagnostic 返回的也是 `name`，不能是 `id`）
2. `Section.sequence_id` 必须支持 `STARTS WITH` 前缀查询
3. 节点必须有 `Concept` 标签，且 `name` 在同一教材内无歧义
4. `PREREQUISITE_OF` 方向必须全域一致：出边 = 后置，入边 = 前置

---

## 三、消费端修复（KG 入库前完成）

### 3.1 BUG 修复

| # | 文件 | 行号 | 问题 | 修复 |
|---|------|------|------|------|
| B1 | `auth.py` | 402 | `(n)-[:PREREQUISITE_OF]->(prereq)` 查出边 = 后置 | 改为 `(prereq)-[:PREREQUISITE_OF]->(n)` |
| B2 | `auth.py` | 408 | `(n)<-[:PREREQUISITE_OF]-(dep)` 查入边 = 前置 | 改为 `(n)-[:PREREQUISITE_OF]->(dep)` |
| B3 | `prerequisite_checker.py` | 30 | `(c)-[:PREREQUISITE_OF*1..2]->(prereq)` 往后置方向走 | 改为 `(pre)-[:PREREQUISITE_OF*1..2]->(c)`，保留 `*1..2` |
| B4 | `diagnostic.py` | 79 | `(n)-[:PREREQUISITE_OF]->(prereq)` 方向反 | 改为 `(pre)-[:PREREQUISITE_OF]->(n)` |
| B5 | `whitelist_db.py` | 27 | `labels(n)[0]` 依赖标签顺序 | 改为 `any(l IN labels(n) WHERE l IN ['Concept','Theorem','Formula'])` |
| B6 | `diagnostic.py` | 44 | 返回 `c.id`，导致 knowledge_stages 存的是 ID 而非中文名 | 改为 `RETURN c.name AS concept_name` |
| B7 | `diagnostic.py` | 52-57 | fallback 用 `c.id CONTAINS $seq_prefix`，新 ID 格式不兼容 | 改为走 `Section ← TEACH_IN → Concept.name` 统一路径 |
| B8 | `diagnostic.py` | 86-93 | RELTED_TO fallback | 删除，查不到返回空 |

### 3.2 `PREREQUISITE_OF` 语义约定

全系统统一为：

```
(A)-[:PREREQUISITE_OF]->(B)  ←→  A 是 B 的前置知识（必须先学 A 才能理解 B）

查询 B 的前置: MATCH (pre)-[:PREREQUISITE_OF]->(B)
查询 A 的后置: MATCH (A)-[:PREREQUISITE_OF]->(post)
```

`whitelist_db.py:42` 方向正确（`(pre:Concept)-[:PREREQUISITE_OF]->(c {id: $nid})`），无需修改。

---

## 四、Neo4j Schema（最终版）

### 4.1 KnowledgePoint 节点

```cypher
-- 定义/概念
CREATE (:KnowledgePoint:Concept {
  id: "gaodai_shang:C01:S01:matrix",
  name: "矩阵",
  type: "Definition",
  textbook: "高等代数上册",
  kg_version: "kg_v2",
  source_span: "定义1 由 s·m 个数排成 s 行、m 列的一张表称为一个 s×m 矩阵",
  created_at: "2026-06-09T00:00:00Z"
})

-- 定理（兼容旧 :Theorem 标签）
CREATE (:KnowledgePoint:Concept:Theorem {
  id: "gaodai_shang:C01:S01:et_preserves_solution",
  name: "初等变换保持同解性",
  type: "Theorem",
  textbook: "高等代数上册",
  kg_version: "kg_v2",
  source_span: "定理1 线性方程组经过初等变换后与原方程组同解",
  created_at: "2026-06-09T00:00:00Z"
})

-- 公式（兼容旧 :Formula 标签）
CREATE (:KnowledgePoint:Concept:Formula {
  id: "gaodai_shang:C02:S01:cramer_rule",
  name: "克莱姆法则",
  type: "Formula",
  textbook: "高等代数上册",
  kg_version: "kg_v2",
  source_span: "定理2（克莱姆法则）...",
  created_at: "2026-06-09T00:00:00Z"
})
```

**类型枚举**：`Definition | Theorem | Formula | Method | Concept`

**标签策略**：
- 所有节点都打 `KnowledgePoint` 和 `Concept`
- 定理额外打 `Theorem`，公式额外打 `Formula`
- 不再创建独立的 `Problem` 节点（练习题不属于核心 KG）

**ID 格式**：`{教材缩写}:C{章}:S{节}:{概念名slug}`

**name 要求**：中文、与教材原文一致、同名教材内唯一

### 4.2 Section 节点

```cypher
CREATE (:Section {
  sequence_id: "V1-C01-S01-U00-T00",
  textbook: "高等代数上册",
  kg_version: "kg_v2",
  chapter: "第1章 线性方程组的解法",
  section: "1.1 线性方程组的消元法",
  subsection: "1.1.1 内容精华"
})
```

**多教材隔离**：不同教材使用不同 `sequence_id` 前缀：
- `V1` = 高等代数上册
- `V2` = 高等代数下册
- `M1` = 高等数学上册
- `M2` = 高等数学下册
- `D1` = 离散数学

保证 `STARTS WITH` 查询不会跨教材命中。

### 4.3 关系

```cypher
-- TEACH_IN：知识点 → 所属节
(:KnowledgePoint:Concept)-[:TEACH_IN {created_at: "..."}]->(:Section)

-- PREREQUISITE_OF：前置 → 后置
(:Concept)-[:PREREQUISITE_OF {
  evidence: "§1.1 先定义矩阵，再定义增广矩阵",
  confidence: 0.92,
  created_at: "..."
}]->(:Concept)
```

**不创建的关系**：`RELATED_TO`、`HAS_ANSWER`、`USES_CONCEPT`。

---

## 五、构建流水线

### 流水线总览

```
Step 0  正文清洗         →  clean.md
Step 1  结构解析         →  sections.jsonl
Step 2  实体抽取         →  entities.jsonl（规则 + LLM）
Step 3  实体归并         →  nodes.jsonl
Step 4  关系候选召回      →  candidate_pairs.jsonl
Step 5  LLM 判关系      →  edges.jsonl
Step 6  入库 + 验收      →  Neo4j kg_v2
```

---

### Step 0：正文清洗

**输入**：`_structured.md`

**做什么**：

原始 `_structured.md` 包含大量非正文内容：

```
┌─ 封面、版权页、作者简介、序言     ← 切掉
├─ 内容简介、CIP 数据               ← 切掉
├─ 目录（含 # 第1章、## 3.8 等标题）← 切掉
├─ ───────── 正文 ─────────
│  # 第1章 线性方程组的解法   ← 正文起点（第二次出现 # 第1章）
│  ### 1.1 ...
│  ...
│  # 习题答案与提示           ← 正文终点 ── 切掉
│  答案正文...                ← 切掉
└─ ────────────────────────
```

**实现**：
1. 找**第二次**出现 `# 第1章`（第一次在目录）→ 正文起点
2. 找 `# 习题答案与提示` → 正文终点
3. 去掉中间残留的目录行（格式为 `* [标题](#...)` 或含页码后缀的行）

**输出**：`高等代数上册_clean.md`

---

### Step 1：结构解析

**输入**：`clean.md`

**做什么**：解析 Markdown 标题层级，生成锚点索引。

教材的标题结构：

```markdown
# 第1章 线性方程组的解法                         → chapter
### 1.1 线性方程组的消元法                        → section
#### 1.1.1 内容精华                               → subsection
##### 例1                                         → anchor
例1 求解线性方程组...（正文内容）
##### 定义1                                       → anchor
定义1 由 s·m 个数排成 s 行、m 列的一张表称为...
##### 定理1                                       → anchor
定理1 初等变换保持线性方程组的同解性...
```

**关键决策**：`##### 定义1`、`##### 定理1`、`##### 例1` **只作为锚点**（定位正文块），**不作为实体名**。

**输出**：`sections.jsonl`

```jsonl
{"anchor_id":"gaodai_shang:C01:S01:D01","title":"例1","sequence_id":"V1-C01-S01-U00-T00","section_id":"C01-S01","full_text":"例1 求解线性方程组\n\n$$\n\\left\\{...\n$$"}
{"anchor_id":"gaodai_shang:C01:S01:D02","title":"定义1","sequence_id":"V1-C01-S01-U00-T00","section_id":"C01-S01","full_text":"定义1 由 s·m 个数排成 s 行、m 列的一张表称为一个 s×m 矩阵，其中的每一个数称为这个矩阵的一个元素...元素全为0的矩阵称为零矩阵...如果一个矩阵 A 的行数与列数相等，则称它为方阵..."}
{"anchor_id":"gaodai_shang:C01:S01:D03","title":"定理1","sequence_id":"V1-C01-S01-U00-T00","section_id":"C01-S01","full_text":"定理1 线性方程组经过初等变换后与原方程组同解..."}
```

**字段说明**：

| 字段 | 含义 | 示例 |
|------|------|------|
| `anchor_id` | 全局唯一锚点 ID | `gaodai_shang:C01:S01:D02` |
| `title` | 锚点标题（不作为实体名） | `定义1` |
| `sequence_id` | 消费端 STARTS WITH 的 key | `V1-C01-S01-U00-T00` |
| `section_id` | 节编号 | `C01-S01` |
| `full_text` | 锚点完整正文 | 供后续 LLM 抽取实体和判断关系 |

---

### Step 2：实体抽取

**输入**：`sections.jsonl`

**做什么**：从每个锚点的正文中抽取**真实知识点名**。两层策略：规则优先，LLM 补充。

#### 规则层（零 token）

匹配数学教材中反复出现的定义句式：

| 句式 | 正则 | 示例命中 |
|------|------|---------|
| "称为/叫做 **X**" | `称为\s*(一个\s*)?(.+?)[，。]` | "s×m 矩阵"、"零矩阵"、"方阵" |
| "称 **X** 为…" | `称\s*(.+?)\s*为` | "称它为方阵" |
| "记作 **X**" | `记作\s*(.+?)[，。]` | "记作 A_{s×m}" |
| "定义为 **X**" | `定义为\s*(.+?)[，。]` | "定义为矩阵的秩" |

#### LLM 补全

规则层覆盖不到的概念（如正文中部才出现、句式不标准），由 DeepSeek Flash 补充。

**Prompt 关键约束**：

```
1. 实体名必须是教材原文中的中文术语，不得翻译、改写、缩写
2. 类型从 Definition / Theorem / Formula / Method / Concept 中选
3. 不得输出"定义1"、"定理1"、"例1"这类编号作为实体名
4. 不确定的不输出
5. 输出严格 JSON
```

**输出**：`entities.jsonl`

```jsonl
{"anchor_id":"gaodai_shang:C01:S01:D02","entities":[
  {"name":"s×m 矩阵","type":"Definition","source":"rule","evidence":"由 s·m 个数排成 s 行、m 列的一张表称为一个 s×m 矩阵"},
  {"name":"矩阵的元素","type":"Concept","source":"rule","evidence":"每一个数称为这个矩阵的一个元素"},
  {"name":"(i,j)元","type":"Concept","source":"rule","evidence":"第 i 行与第 j 列交叉位置的元素称为矩阵的 (i,j) 元"},
  {"name":"零矩阵","type":"Definition","source":"rule","evidence":"元素全为0的矩阵称为零矩阵"},
  {"name":"方阵","type":"Definition","source":"rule","evidence":"如果一个矩阵 A 的行数与列数相等，则称它为方阵"},
  {"name":"m 级矩阵","type":"Concept","source":"rule","evidence":"m 行 m 列的方阵也称为 m 级矩阵"},
  {"name":"增广矩阵","type":"Definition","source":"llm","evidence":"§1.1 例1后：只写出系数和常数项排成的一张表称为增广矩阵"},
  {"name":"系数矩阵","type":"Definition","source":"llm","evidence":"§1.1 例1后：只列出系数的表称为系数矩阵"},
  {"name":"线性方程组的初等变换","type":"Method","source":"llm","evidence":"§1.1 例1评注[1]：倍加、互换、数乘三种变换"},
  {"name":"阶梯形方程组","type":"Concept","source":"llm","evidence":"§1.1 例1评注[2]"},
  {"name":"简化阶梯形方程组","type":"Concept","source":"llm","evidence":"§1.1 例1评注[2]"}
]}
{"anchor_id":"gaodai_shang:C01:S01:D03","entities":[
  {"name":"初等变换保持同解性","type":"Theorem","source":"llm","evidence":"定理1：线性方程组经过初等变换后与原方程组同解"}
]}
```

---

### Step 3：实体归并

**输入**：`entities.jsonl`

**做什么**：

1. **同名合并**：不同锚点抽出的同名实体（如"矩阵"在 §1.1、§1.2、§2.1 都出现）→ 合并为一个节点，记录 `first_section` 和 `all_sections`
2. **同义词归并**：LLM 判断"伴随矩阵"和"adjoint matrix"→ 保留 `name: "伴随矩阵"`
3. **伪实体过滤**：删除 name 匹配 `^定义\d*$|^定理\d*$|^例\d*$|^命题\d*$|^推论\d*$|^题\d*$|^答案\d*$` 的条目

**输出**：`nodes.jsonl`

```jsonl
{"id":"gaodai_shang:C01:S01:matrix","name":"矩阵","type":"Definition","first_section":"C01-S01","all_sections":["C01-S01","C01-S02","C02-S01","C03-S01"],"textbook":"高等代数上册"}
{"id":"gaodai_shang:C01:S01:zero_matrix","name":"零矩阵","type":"Definition","first_section":"C01-S01","all_sections":["C01-S01"],"textbook":"高等代数上册"}
{"id":"gaodai_shang:C01:S01:square_matrix","name":"方阵","type":"Definition","first_section":"C01-S01","all_sections":["C01-S01","C02-S01"],"textbook":"高等代数上册"}
{"id":"gaodai_shang:C01:S01:augmented_matrix","name":"增广矩阵","type":"Definition","first_section":"C01-S01","all_sections":["C01-S01","C01-S02"],"textbook":"高等代数上册"}
{"id":"gaodai_shang:C01:S01:coefficient_matrix","name":"系数矩阵","type":"Definition","first_section":"C01-S01","all_sections":["C01-S01"],"textbook":"高等代数上册"}
{"id":"gaodai_shang:C01:S01:elementary_transformation","name":"线性方程组的初等变换","type":"Method","first_section":"C01-S01","all_sections":["C01-S01","C01-S02","C02-S01"],"textbook":"高等代数上册"}
{"id":"gaodai_shang:C01:S01:et_preserves_solution","name":"初等变换保持同解性","type":"Theorem","first_section":"C01-S01","all_sections":["C01-S01"],"textbook":"高等代数上册"}
{"id":"gaodai_shang:C01:S01:echelon_form","name":"阶梯形方程组","type":"Concept","first_section":"C01-S01","all_sections":["C01-S01"],"textbook":"高等代数上册"}
{"id":"gaodai_shang:C01:S01:reduced_echelon_form","name":"简化阶梯形方程组","type":"Concept","first_section":"C01-S01","all_sections":["C01-S01"],"textbook":"高等代数上册"}
```

---

### Step 4：关系候选召回

**输入**：`nodes.jsonl`、`sections.jsonl`

**做什么**：不在全部实体中 O(n²) 暴力配对。用规则压缩候选空间。

| 策略 | 逻辑 | 示例 |
|------|------|------|
| **同节配对** | 同一节内的实体两两配对 | §1.1 的 15 个实体互相配对 |
| **邻节窗口** | 相邻 2 节之间的实体配对 | §1.2 实体 × §1.1 实体 |
| **正文引用** | 锚点正文中出现另一实体名 | "增广矩阵"的正文中出现"矩阵"、"系数矩阵" |
| **教材顺序** | source 的节号 ≤ target 的节号 | 滤掉逆序配对减少噪音 |
| **数量限制** | 每个实体最多保留 top 30 候选 | 避免 token 膨胀 |

**输出**：`candidate_pairs.jsonl`

```jsonl
{"source_id":"gaodai_shang:C01:S01:matrix","target_id":"gaodai_shang:C01:S01:augmented_matrix","reason":"same_section+text_ref"}
{"source_id":"gaodai_shang:C01:S01:matrix","target_id":"gaodai_shang:C01:S01:square_matrix","reason":"same_section+text_ref"}
{"source_id":"gaodai_shang:C01:S01:matrix","target_id":"gaodai_shang:C01:S01:zero_matrix","reason":"same_section+text_ref"}
{"source_id":"gaodai_shang:C01:S01:augmented_matrix","target_id":"gaodai_shang:C01:S01:coefficient_matrix","reason":"same_section+text_ref"}
{"source_id":"gaodai_shang:C01:S01:elementary_transformation","target_id":"gaodai_shang:C01:S01:et_preserves_solution","reason":"same_section"}
{"source_id":"gaodai_shang:C01:S01:echelon_form","target_id":"gaodai_shang:C01:S01:reduced_echelon_form","reason":"same_section+text_ref"}
```

---

### Step 5：LLM 判关系

**输入**：`candidate_pairs.jsonl`、`nodes.jsonl`

**做什么**：逐章发给 DeepSeek Flash，判断候选对之间是否存在以下三种关系。

| 关系 | 含义 | 方向 |
|------|------|------|
| `PREREQUISITE_OF` | 必须先学 A 才能理解 B | A → B |
| `DERIVED_FROM` | B 从 A 推导/引申/特殊化而来 | A → B |
| `APPLIES_TO` | A 的方法/工具/结论被应用到 B | A → B |

**Prompt 硬约束**：
- `source_id` 和 `target_id` 必须来自给定候选列表，不得新造实体名
- 每条边必须给出 `evidence`（原文依据或逻辑推理）
- 不确定则不输出
- 禁止 `RELATED_TO`、`HAS_ANSWER` 等旧关系类型
- 输出严格 JSON Schema

**输出**：`edges.jsonl`

```jsonl
{"source_id":"gaodai_shang:C01:S01:matrix","target_id":"gaodai_shang:C01:S01:augmented_matrix","type":"PREREQUISITE_OF","evidence":"§1.1 正文：先定义矩阵（s×m 个数的表），再在此基础上定义增广矩阵（系数+常数项排成的表），学生必须先理解矩阵概念才能理解增广矩阵","confidence":0.95}
{"source_id":"gaodai_shang:C01:S01:matrix","target_id":"gaodai_shang:C01:S01:square_matrix","type":"DERIVED_FROM","evidence":"§1.1 正文：在矩阵定义基础上，特殊化得到：行数=列数 → 方阵","confidence":0.90}
{"source_id":"gaodai_shang:C01:S01:matrix","target_id":"gaodai_shang:C01:S01:zero_matrix","type":"DERIVED_FROM","evidence":"§1.1 正文：元素全为0的矩阵称为零矩阵——矩阵的特殊情况","confidence":0.88}
{"source_id":"gaodai_shang:C01:S01:augmented_matrix","target_id":"gaodai_shang:C01:S01:coefficient_matrix","type":"DERIVED_FROM","evidence":"§1.1 正文：只列出系数的表称为系数矩阵（增广矩阵去掉常数项列）","confidence":0.92}
{"source_id":"gaodai_shang:C01:S01:elementary_transformation","target_id":"gaodai_shang:C01:S01:et_preserves_solution","type":"DERIVED_FROM","evidence":"§1.1 正文：先定义初等变换（三种操作），定理1 在此基础上论证它们保持同解性","confidence":0.88}
{"source_id":"gaodai_shang:C01:S01:echelon_form","target_id":"gaodai_shang:C01:S01:reduced_echelon_form","type":"DERIVED_FROM","evidence":"§1.1 例1评注[2]：对阶梯形方程组进一步施行初等变换变成简化阶梯形方程组","confidence":0.85}
```

**§1.1 最终图谱结构**：

```
        矩阵 (Definition)
          │
          ├── PREREQUISITE_OF ──→ 增广矩阵
          │                         │
          │                         └── DERIVED_FROM ──→ 系数矩阵
          │
          ├── DERIVED_FROM ──→ 方阵
          ├── DERIVED_FROM ──→ 零矩阵
          └── DERIVED_FROM ──→ (i,j)元

    线性方程组的初等变换 (Method)
          │
          └── DERIVED_FROM ──→ 初等变换保持同解性 (Theorem)
                                   │
                                   └── DERIVED_FROM ──→ 阶梯形方程组
                                                           │
                                                           └── DERIVED_FROM ──→ 简化阶梯形方程组
```

---

### Step 6：入库 + 验收

#### 6a. Neo4j 入库

每章一个 Cypher batch 事务，按序执行：

1. 创建 Section 节点
2. 创建 KnowledgePoint 节点（含标签 `Concept`，定理/公式额外打 `Theorem`/`Formula`）
3. 创建 TEACH_IN 关系
4. 创建 PREREQUISITE_OF、DERIVED_FROM、APPLIES_TO 关系

#### 6b. 消费端回归测试

| 接口 | 验证点 |
|------|--------|
| `GET /api/auth/knowledge-graph` | 薄弱概念能匹配到 Neo4j name；prerequisites 走**入边**（前置概念），dependents 走**出边**（后置概念）；stage 正确关联 |
| `prerequisite_checker.get_prereq_gaps()` | `STARTS WITH sequence_id` 命中本节；1~2 跳前置链方向正确；返回中文 name |
| `whitelist_db.get_whitelist()` | 返回本节知识点 + 前置名；`any(l IN labels(n)...)` 正常过滤；不跨教材污染 |
| `diagnostic.get_concepts_by_sequence_id()` | 返回中文 name；fallback 可用 |

#### 6c. 自动校验

| 检查项 | 阈值 | 方法 |
|--------|------|------|
| 空 name 节点 | = 0 | Cypher `MATCH (n:KnowledgePoint) WHERE n.name IS NULL OR n.name = ''` |
| 伪实体比例 | < 1% | name 匹配 `^定义\d*$\|^定理\d*$\|^例\d*$\|^命题\d*$\|^题\d*$` |
| 英文/拉丁字符占比 | < 2% | `name` 中 ASCII 字母数 / 总名字数 |
| 自环边 | = 0 | `MATCH (n)-[r]->(n)` |
| 悬空引用 | = 0 | 所有 edge 的 source_id/target_id 在 KnowledgePoint.id 中存在 |
| 孤立节点比例 | < 5% | 无 TEACH_IN 且无 PREREQUISITE_OF / DERIVED_FROM / APPLIES_TO 边的节点 |
| Section 覆盖率 | 100% | 每个 section 至少有 1 个 KnowledgePoint 通过 TEACH_IN 关联 |

#### 6d. 人工抽检

| 指标 | 目标 | 方法 |
|------|------|------|
| 关系准确率 | > 85% | 随机抽 30 条边，人判 evidence 是否支持该关系 |
| 实体覆盖率 | > 90% | 抽 3 节，人读正文数概念 vs KG 节点数，算召回 |

---

## 六、执行计划

### 6.1 阶段

| 阶段 | 内容 | 验收标准 |
|------|------|---------|
| **第〇轮** | 消费端修复（B1-B8）+ 本地 Neo4j 环境确认（密码、连接） | 8 处改动通过代码审查，Neo4j Desktop 可连接 |
| **第一轮** | 高代上册 **第 1 章 POC** | 验证 3 个假设：① ##### 锚点→中文名转换正常 ② PREREQUISITE_OF 方向消费端全一致 ③ TOC 过滤后噪音 < 5% |
| **第二轮** | 高代上册全本 | 与旧 KG 做 A/B 对比：英文名 < 2%、关系准确率 > 85%、消费端接口全通过 |
| **第三轮** | 高数上册 + 高数下册 | 同上标准 |
| **第四轮** | 离散数学 | 同上标准 |

### 6.2 前置条件（阻塞项）

- [ ] 本地 Neo4j Desktop 密码确认
- [ ] DeepSeek Flash API 格式确认（`api.deepseek.com/v1` 兼容 OpenAI SDK）
- [ ] `_structured.md` 文件就位（4 本教材）

### 6.3 成本估算

| 步骤 | token 来源 | 单本估算 |
|------|-----------|---------|
| 实体抽取（规则层） | 正则 | 0 |
| 实体抽取（LLM 补全） | DeepSeek Flash，每节~2K token | 60节 × 2K = 120K |
| 实体归并（同义词判断） | LLM | ~30K |
| 关系候选召回 | 规则 | 0 |
| LLM 判关系 | DeepSeek Flash，每章~5K token | 6章 × 5K = 30K |
| **合计** | | **~200K token/本（约 ¥0.04）** |

旧方案：30M token/本（¥75）。降低约 **150 倍**。

---

## 七、风险登记

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| `#####` 标题质量不足以支撑实体抽取 | 中 | 严重 | 第一轮 POC 重点验证；规则层 + LLM 补全双保险 |
| `knowledge_stages` 已有数据与新 KG 的 name 不匹配 | 高 | 中 | 修复 B6 后，后续诊断写 name 保持一致性；历史数据做一次批量迁移 |
| 多教材同图时 `sequence_id` 前缀冲突 | 低 | 严重 | 严格使用教材前缀（V1/V2/M1/M2/D1） |
| DeepSeek Flash API 不稳定 | 低 | 中 | 每步输出 jsonl 中间文件，支持断点续传 |
| 消费端修复引入回归 | 低 | 中 | 每个修复单独 commit + 跑集成测试 |

---

## 八、附录：文件索引

| 文件 | 用途 |
|------|------|
| `教材提取模块/KG_v2_构建计划.md` | 本文档 |
| `教材提取模块/build_kg.py` | 旧 KG 构建脚本（参考） |
| `教材提取模块/教材标题分级工具.py` | MD 5级标题分级工具 |
| `比赛相关文件与文件夹/揭榜挂帅/教材库/*/` | 结构化 MD 教材（新方案输入） |
| `app/routers/auth.py` | 消费端 C1：知识图谱 API |
| `app/services/prerequisite_checker.py` | 消费端 C2：前置检查 |
| `app/db/whitelist_db.py` | 消费端 C3：白名单 |
| `app/db/diagnostic.py` | 消费端 C4：诊断溯源 |
| `app/db/knowledge_stages_db.py` | 消费端共用：概念掌握度表 |
| `frontend/src/components/KnowledgeGraph.tsx` | 前端可视化（定义渲染契约） |
