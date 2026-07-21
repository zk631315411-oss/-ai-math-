# 读书笔记：Ain et al., 2023

**标题**：Automatic Construction of Educational Knowledge Graphs: A Word Embedding-Based Approach
**作者**：Qurat Ul Ain 等（University of Duisburg-Essen, Germany）
**出处**：Information (MDPI), 2023, 14, 526, 18 pages

## 一、做什么

在自研 MOOC 平台 CourseMapper 上自动构建 EduKG。流水线四步：
1. SIFRank + SqueezeBERT → 从课件 PPT 中提取关键短语
2. Wikipedia 实体链接 → 确认哪些短语是真正的概念
3. Wikipedia 类别扩展 → 引入相关概念
4. SBERT 权重排序 → 给概念打重要性分数

## 二、与我们的对比

| | 他们 | 我们 |
|---|---|---|
| 数据源 | MOOC 课件 PPT | 结构化 MD 教材 |
| 概念提取 | SIFRank + Wikipedia | 正则 + LLM |
| 需外部 KB | 是（Wikipedia） | 否 |
| 实体边界 | 需要从连续文本中挖 | ##### 锚点免费给 |
| 语言 | 英语 | 中文 |

## 三、启发

- 文献综述（第 2 节）整理了 EduKG 构建的前人方法分类，可做背景参考
- 概念权重排序思路可借鉴——SBERT 相似度可作为 Step 3 去重的辅助信号
- 直接可用度：低（方法依赖 Wikipedia，不适用于中文数学教材）
