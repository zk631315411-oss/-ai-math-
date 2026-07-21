# 读书笔记：Liu et al., JAIR 2016

**标题**：Learning Concept Graphs from Online Educational Data
**作者**：Hanxiao Liu, Wanli Ma, Yiming Yang, Jaime Carbonell（CMU）
**出处**：Journal of AI Research (JAIR), 55, pp. 1059-1090, 2016

---

## 一、问题

不同大学、不同 MOOC 平台的课程没有统一的课程 ID 和概念体系。如何自动检测课程间的前置关系，支持学生选课和课程规划？

## 二、方法

**两层图框架：**

```
课程层（上层）：Course A --[前置]--> Course B    ← 不同大学的课程不重合
              ↕ 映射                     ↕ 映射
概念层（下层）：[eigenvectors, Markov] --[前置]--> [PageRank, HITS]
              ↑ 通用概念空间（如 Wikipedia topics）
```

**核心机制**：把课程层观测到的前置关系 **向下投影** 到通用概念层 → 在概念层学习概念间前置 → **向上推理** 未知课程间前置。概念层充当 **interlingua（中介语）**，实现跨大学迁移学习。

## 三、概念表示方式

尝试了四种：英文词袋、稀疏编码、词嵌入（word2vec）、Wikipedia 类别。**Wikipedia 类别效果最好。**

## 四、与我们相关的

- 两层图思路可类比我们的 **Section ↔ Concept** 两层结构（节锚定概念，概念间前置关系连接不同节）
- Wikipedia 作为通用概念空间对中文教材不适用——我们的概念空间天然是中文的，不需要外部映射
- 这篇聚焦**课程级**前置（粗粒度），和我们的**教材章节内**概念级前置（细粒度）目标不同

**直接可用度：低。** 思路有参考价值但方法不直接适用。
