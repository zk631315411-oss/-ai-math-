# 读书笔记：Gul, PhD Thesis 2022 (Sabanci University)

**标题**：Automatic Construction of Concept Maps from Unstructured Text
**作者**：Saima Gul
**出处**：PhD Thesis, Sabancı University, 2022, 110 pages

---

## 一、金句

> "Existing algorithms for automatic prerequisite detection are too inaccurate, which reduces learners' trust in such maps."
>
> "We propose to replace prerequisite relations with less authoritative coverage relations."
>
> "Prerequisites of a given concept tend to be easier than the concept itself."

## 二、方法

### 不用 "prerequisite"，用 "coverage"

论文认为前置关系检测不够准（连 Wang 2016 也只有 F1=0.61），不可靠的前置关系会让学生不信任知识图谱。所以改成 **coverage relation**——只表示 "A 比 B 更宽泛、覆盖了 B 的部分内容"，不声称严格的先后顺序。

然后用**概念难度**做互补——前置概念通常比目标概念简单。把 coverage 关系 + 难度分数结合，间接达到和 prerequisite 类似的效果，但出错时后果更轻（学生把它当建议而非事实）。

### 概念难度预测

提出第一个无监督概念难度预测方法。不需要标注数据。

## 三、对我们的启示

1. **PREREQUISITE_OF 不可靠是学术界共识**。我们在 Step 5 给边加 confidence 分数、写 evidence 原文引用的设计，正是为了缓解这个问题——让用户看到边的依据，自己做判断。
2. **coverage 关系是个退路**。当 LLM 判不准两条概念间是否有严格前置时，可以降级为 coverage（或者我们的 APPLIES_TO），比错标 PREREQUISITE_OF 更好
3. **难度预测可以当 Step 5 的辅助特征**。如果概念 A 难度明显低于 B，且 A 出现在 B 之前 → 前置关系的概率更大
