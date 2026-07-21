# 读书笔记：Alzetta et al., 2020

**标题**：Digging Into Prerequisite Annotation
**作者**：Chiara Alzetta 等（PREAP 团队，University of Genoa）
**出处**：AIED 2020 Workshop, 6 pages, CC BY 4.0

---

## 一、做了什么

5 位领域专家独立标注同一本 CS 教材的一个章节。分析标注不一致的原因。

## 二、关键发现

### 标注一致性极低

845 个独特概念对中，5 人全票通过的只有 25 对（3%）。56% 的标注只有一个人标了。

### 六种错误类型（按频率排序）

| 类型 | 含义 | 对我们的启示 |
|------|------|-------------|
| **Not a Concept** | 普通词被当成领域概念 | 提取规则必须严格定义"什么算概念" |
| Background Knowledge | 凭自己知识加，教材没写 | 验证了 evidence 必须来自教材原文 |
| Too Far | 概念路径太远 | relation 候选召回应限制距离 |
| Annotation Error | 走神/手滑 | — |
| Wrong Direction | 方向反了 | Step 5 需要非对称性约束 |
| Co-Requisites | 无依赖关系 | — |

### 关系类型与一致性

- **词法型关系**（上下位、整体-部分）：一致性 >60%，LLM 判这类更可靠
- **功能型关系**（因果、时序）：一致性低，受主观解读影响大

### 评估方法

主张用**传递闭包**和**图结构相似度**替代简单的逐对匹配来评估 PR 标注质量。

## 三、对我们的指导

1. 概念定义要严格 — "Not a Concept" 是第一大错误来源
2. evidence 必须有教材依据 — "Background Knowledge" 是第二大错误
3. Step 5 可以按关系类型分置信度（词法 > 功能）
4. Step 5 评估不能只看单边准确率，要看图的整体一致性
