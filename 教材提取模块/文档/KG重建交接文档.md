# KG 知识图谱重建 — 交接文档

## 背景

项目"学数有道"（智学助手）正在准备揭榜挂帅 XH-202620 比赛。系统基于 Neo4j 知识图谱实现"图谱约束防止 AI 超纲"，这是比赛答辩的核心卖点。

当前线上 Neo4j Aura 只有高等代数上册的 KG（5225 节点 / 24802 关系），存在三个问题：
1. **47.8% 英文概念名**（Skew_Symmetric_Matrix 等），与中文教材不一致
2. **TOC 目录噪音混入** Section 节点（已部分清理，造成了 20% TEACH_IN 边损失）
3. **缺少跨节前置关系**——旧方案逐块发 LLM，每块只看一小段文本，无法发现跨章节的前置依赖

## 已完成

### 教材 MD 准备（4 本教材就位）

位于 `D:\ai-math\比赛相关文件与文件夹\揭榜挂帅\教材库\`：

```
高等代数/         ← 丘维声，已有旧 KG
  高等代数上册_structured.md
  高等代数下册_structured.md
  高等代数创新教材_上_丘维声.不删减.md（原始）
  高等代数创新教材_下_丘维声.不删减.md（原始）

高等数学上册/     ← 黄立宏，新教材
  MinerU_markdown_*.md ×2（原始分片）
  _merged.md（合并版）
  _structured.md（5级分级版）

高等数学下册/     ← 黄立宏，新教材
  （同上结构）

离散数学（第六版）/  ← 耿素云，新教材
  （同上结构）
```

每本教材经历三级流水线：**MinerU 原始 MD → 合并分片 → 5级标题分级**

### 旧 KG 管线分析

`build_kg.py`（位于 `教材提取模块\`）：
- LLM：智谱 GLM-4.5-Air
- 策略：MarkdownHeaderTextSplitter 按标题切块 → 每块独立发 LLM → 同时抽实体+分类+判关系
- 关系类型：PREREQUISITE_OF / DERIVED_FROM / USES_CONCEPT / HAS_ANSWER / RELATED_TO
- 问题：30M token/本（¥75），英文名 47.8%，RELATED_TO 噪音 15%，跨节关系缺失

## 下一步：高质量重建

### 目标

用 DeepSeek Flash 重建**高代上册**和**高数上册**的 KG，写到本地 Neo4j Desktop（不影响 Aura 线上数据）。

### 新方案

**正则抽实体名 + 逐节 LLM 判关系**（旧方案是 LLM 每块全包）

| | 旧方案 | 新方案 |
|---|---|---|
| 实体抽取 | LLM 从每块文本猜 | 正则从 `#####` 标题直接取（零 token） |
| 关系判断 | 逐块独立，无上下文 | 逐节发 LLM，附带整章实体目录 |
| 跨节关系 | 不可能 | 每节都能看到前面各节的实体列表 |
| 成本 | 30M token/本 | ~300K token/本（¥0.06） |
| 模型 | 智谱 GLM-4.5-Air | DeepSeek Flash |

### 待定

1. **关系类型精简**：建议只保留 PREREQUISITE_OF / DERIVED_FROM / APPLIES_TO，砍掉 RELATED_TO 和 HAS_ANSWER
2. **本地 Neo4j 密码**：之前试过 `Zhangkai@2004` 等均失败，需在 Neo4j Desktop 确认
3. **DS Flash API 接口**：是否为 OpenAI 兼容格式（`api.deepseek.com/v1`）？

## 关键文件索引

| 文件 | 用途 |
|------|------|
| `教材提取模块/build_kg.py` | 旧 KG 构建脚本（参考） |
| `教材提取模块/教材标题分级工具.py` | MD 5级标题分级工具 |
| `教材提取模块/failed_chunks.log` | 旧方案失败日志（7293 行，多为 API 欠费） |
| `比赛相关文件与文件夹/揭榜挂帅/教材库/*/_structured.md` | 4 本教材的结构化 MD（新方案的输入） |
| `app/db/whitelist_db.py` | KG 消费者：白名单查询 |
| `app/services/prerequisite_checker.py` | KG 消费者：前置知识检查 |
| `app/routers/auth.py:352` | KG 消费者：知识图谱可视化 API |
