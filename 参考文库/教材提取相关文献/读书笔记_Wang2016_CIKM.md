# 读书笔记：Wang et al., CIKM 2016

**标题**：Using Prerequisites to Extract Concept Maps from Textbooks
**作者**：Shuting Wang, Alexander G. Ororbia II, Zhaohui Wu, Kyle Williams, Chen Liang, Bart Pursel, C. Lee Giles（Penn State）
**出处**：CIKM 2016, Indianapolis, pp. 317-326
**DOI**：10.1145/2983323.2983725

---

## 一、问题

传统概念图提取 = 两步独立：先抽关键概念，再判概念间关系。Wang 指出这二者互相耦合——概念是否为 key concept 取决于它有没有前置/后置关系，反之亦然。分开做会得到次优结果。

教材的 TOC 结构是强信号，前人没用。

## 二、方法

**联合优化框架**：同时优化概念-章节矩阵 CS 和关系矩阵 R。

### 输入输出

- 输入：教材 B = 标题列表 + 章号 + 各章内容
- 输出：概念图 G = {(c₁, c₂, r)}，r∈{0,1}，c₁ 是 c₂ 的前置

### Key Concept 五个特征

| 特征 | 定义 |
|------|------|
| Local Relatedness | 概念应与其所在章节内容强相关 |
| Global Coherence | 不同章不应重复详细讲解同一概念（去冗余） |
| Topic Relatedness | 两个有前置关系的概念须属同一主题领域 |
| Complexity Difference | 前置概念应比目标概念更基础 |
| Order Coherence | 前置概念在教材中必须先于目标概念出现 |

### 目标函数

```
Λ(CS, R) = P₁(CS) + P₂(R) + P₃(CS, R) + L1正则

P₁: Σ cs_ip × f(concept_i, subchapter_p)       局部相关
   + Σ cs_ip × cs_jq × f(concept_i, concept_j)  全局一致
P₂: Σ r_ij × f(concept_i, concept_j)            主题相关
   + Σ r_ij × (l(ci) - l(cj))                   复杂度差
P₃: Σ I(p<q) × cs_ip × cs_jq × r_ij            顺序一致
```

用 Metropolis-Hasting 迭代优化 CS 和 R。

### 外部知识

用 Wikipedia 获取：概念相似度 f(·,·)（基于 Wikipedia 链接结构）、概念复杂度 l(·)（Wikipedia 入度/出度）

## 三、实验

6 学科教材：计算机网络、宏观经济学、微积分预备、数据库、物理、几何

| 方法 | F1 |
|------|-----|
| 独立两步（TF-IDF + Wikipedia） | 0.04-0.16 |
| 监督学习基线 | ~0.40 |
| **联合优化** | **0.61** |

联合优化比独立两步好 4-15 倍。

## 四、对我们的启示

1. **Order Coherence 天然可用**——Step 1 的 section_id 给了概念出现顺序，不需要 Wikipedia
2. **联合优化思想可借鉴**——Step 5 的结果可反馈给 Step 3（频次高的概念更重要）
3. **Global Coherence**——同一概念在多章出现 = 核心概念，归一化时不应干掉
4. F1=0.61 提示我们：自动提取的准确率上界大约 60%，期望不宜过高
5. Wikipedia 这条路对中文教材不可行——我们靠 LLM + 规则替代
