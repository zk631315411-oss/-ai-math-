# 读书笔记：Miaschi et al., 2019

**标题**：Linguistically-Driven Strategy for Concept Prerequisites Learning on Italian
**作者**：Alessio Miaschi, Chiara Alzetta 等（PREAP 团队）
**出处**：ACL 2019 Workshop on Innovative Use of NLP for Building Educational Applications, pp. 285-295

## 一、要点

- 只用语言学特征（词汇、句法、可读性、TF-IDF）做前置关系分类，不依赖 Wikipedia 图结构
- 构建了 ITA-PREREQ——第一个意大利语前置关系数据集
- 用神经网络（MLP）分类器，跨语言实验（英→意）

## 二、与我们的关系

- 验证了"纯文本特征可行"这个前提——我们的 Step 5 也是只靠教材文本
- 但前提条件不同：他们把概念=Wikipedia 页面，我们是从教材句子中抽概念。我们的粒度更细
- 语言学特征（句法复杂度≈概念难度）可作为 Step 5 辅助特征
- 直接可用度：中低（意大利语 NLP 工具链中文没有；方法需要标注数据训练）

## 三、启发

纯文本已经包含足够信号来判前置关系——不需要 Wikipedia。这是对我们 LLM 判关系方案的理论支撑。
