# 读书笔记：Lu et al., AAAI 2019

**标题**：Concept Extraction and Prerequisite Relation Learning from Educational Data
**作者**：Weiming Lu, Yangfan Zhou, Jiale Yu, Chenhao Jia（浙江大学）
**出处**：AAAI 2019 (EAAI-19), pp. 9678-9685

---

## 一、问题

从教材和 MOOC 中自动提取领域概念 + 学习概念间前置关系。关键挑战：(1) 细粒度概念难抽，(2) 标注前置关系费时，(3) 现有方法或只依赖特征（learning-based）或只依赖课程结构（recovery-based），没有结合两者。

## 二、方法

两步流水线：**DsCE（概念提取）→ iPRL（前置关系学习）**

### DsCE：领域概念提取

**Step 1 — 短语挖掘**：用 AutoPhrase（Shang et al., 2018）从教材中抽取高质量短语。AutoPhrase 用远程监督 + POS 标签，跨领域可用。

**Step 2 — 领域概念识别**：图传播排序算法。构建短语全连通图，边权 = 词向量的余弦相似度。设所有短语初始置信度为 1，迭代传播：高置信短语 → 语义相关的邻居短语。传播时惩罚重叠短语（如 "sort algorithm" 和 "this algorithm" 不应互推）。最终取 conf > 0.6 的短语作为领域概念。

### iPRL：迭代式前置关系学习

**核心思想**：learning-based 模型（分类器）和 recovery-based 模型（课程依赖反推）相互增强、迭代收敛。

```
A (recovery model, 基于章节依赖推导) 
  → 生成训练数据 → 
F (learning model, 基于特征分类) 
  → 更新 A → 
...迭代直至收敛
```

**特征设计**（跟我们最相关的部分）：

| 特征 | 含义 |
|------|------|
| chapter refd | 概念 a 出现在哪些章，这些章是否引用概念 b |
| Wikipedia abstract occurrence | b 的 Wikipedia 摘要里是否提到 a |
| complexity level | 复杂度差异（Wikipedia 入度/链长估算） |
| position relatedness | 两概念在教材中的平均位置距离 |
| semantic relatedness | 词向量余弦相似度 |

**约束条件**：
1. 如果学习材料依赖关系存在，必须有足够的概念对前置关系支撑
2. 非对称：A≺B ⇒ ¬(B≺A)
3. 如果概念 A 的 Wikipedia 文章里不包含 B，则无前置关系
4. 如果 A 在教材中出现在 B 之前，A 可能是 B 的前置

## 三、实验

**中文教材数据集**（跟我们最相关！）：

| 领域 | 教材数 | 概念数 | 标注前置对 |
|------|--------|--------|-----------|
| 微积分 (CAL) | 6 | 89 | 439 |
| 数据结构 (DS) | 6 | 90 | 453 |
| 物理 (PHY) | 6 | 139 | 630 |

MOOC 数据：机器学习 5 门课 / 数据结构 8 门课

**概念提取结果**：DsCE 在所有 3 个领域上优于 TextRank、THUCKE、AutoPhrase。

**前置关系结果**：iPRL 无标签模式下优于 RefD 和 CPR-Recover。值得注意的是——微积分领域精度最低（因为数学公式影响 OCR 质量）。

## 四、对我们的启示

1. **相同的两段式设计**：DsCE → iPRL = 我们的 Step 2 → Step 5。验证了这个架构在中文数学教材上是可行的。
2. **我们的 ##### 锚点 = 免费的 AutoPhrase + 图传播**。他们需要先从连续文本中挖短语（AutoPhrase）、再筛领域概念（图传播排序）——两步都有误差。我们的结构化 MD 直接给了实体边界，省了这两步。
3. **迭代互增强机制**：我们 Step 5 目前是一次性 LLM 调用，判完就完了。iPRL 的思路是可以反复做——第一轮 LLM 判完后，用传递性（A≺B ∧ B≺C ⇒ A≺C）自动补边 → 把补充数据作为第二轮输入 → LLM 再判。这个可以加到 Step 5 设计里。
4. **feature 设计直接可用**：chapter refd（锚点引用，TEACH_IN 天然就是）、position（section_id 有序）、semantic（中文词向量，需额外训练）都可以在 Step 5 实现。Wikipedia 相关特征对中文教材不可用。
5. **概念数参考**：6 本微积分教材共 89 个概念——我们的 48 锚点 → 37 规则概念 + 18 重叠≈55 独特概念，量级合理。
