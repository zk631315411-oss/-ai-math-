# 学习状态建模与自适应优化综述

**版本**：重建稿（2026-07-22）  
**适用对象**：数学学习系统、题目推荐、知识图谱导学与学习诊断  
**证据边界**：本稿优先使用经典论文、JEDM/EDM/NeurIPS/ACM 正式论文和教材。当前网络检索端点不稳定，因此未把无法唯一定位的 `KQGC`、`DHKT` 扩展名或论文写成既定事实。

## 摘要

知识追踪（Knowledge Tracing, KT）要解决的是：给定学生的交互序列、题目属性和知识结构，估计时刻 `t` 的知识状态，并预测下一次作答或学习行为。Bayesian Knowledge Tracing（BKT）把知识视为可解释的隐状态；Item Response Theory（IRT）把学生能力、题目难度和区分度放入测量模型；Deep Knowledge Tracing（DKT）及其记忆、注意力和图神经网络变体扩大了表示能力；组合优化、动态规划、上下文多臂老虎机和强化学习则把状态估计转化为“下一道题、提示或复习动作”的决策问题。

核心结论有三点。第一，预测准确率不等于知识测量有效：应同时报告校准、跨时间/学生泛化、可解释性和干预后的学习增益。第二，图结构不是万能的先验，错误的先修关系会被模型放大；知识图谱必须有版本、来源和不确定性。第三，对于数学系统，推荐采用“测量层 + 状态层 + 图约束 + 决策层”的分层架构，而不是直接用一个黑盒模型输出推荐。

## 1. 统一问题表述

设学生在时间 `t` 交互的题目为 `q_t`，观测结果为 `y_t`（正确、错误、部分得分、提示次数、耗时等），题目涉及知识组件集合 `K(q_t)`，上下文为 `x_t`。模型输出知识状态 `z_t` 或能力向量 `theta_t`，以及下一次表现概率：

```text
P(y_{t+1}=1 | h_t, q_{t+1}, x_{t+1})
```

其中 `h_t` 是历史交互，`z_t` 可以是离散掌握状态，也可以是连续向量。自适应系统还需要定义动作 `a_t`（题目、提示、复习、讲解或跳过），目标函数通常写成：

```text
max E[ sum_t gamma^t (learning_gain_t - lambda * effort_t) ]
```

这说明“预测”与“干预”是两个不同问题：前者评估状态，后者需要决策策略和因果证据。

## 2. BKT、HMM 与可解释状态估计

### 2.1 BKT 的基本形式

经典 BKT 使用二状态隐马尔可夫模型。对每个知识组件 `k`，学生在时刻 `t` 有 `L_t in {0,1}`；参数通常包括初始掌握 `P(L_0=1)`、学习转移 `T=P(L_{t+1}=1|L_t=0)`、猜测 `G` 和失误 `S`。观测模型为：

```text
P(y_t=1 | L_t=1)=1-S
P(y_t=1 | L_t=0)=G
```

作答后先按 Bayes 规则更新掌握后验，再施加学习转移。其优势是参数语义清楚、可与教学规则连接、数据量要求相对低；局限是每个知识组件通常独立、学习率和遗忘率过于稳定、难以表达多技能题和上下文影响。

Corbett 与 Anderson 的原始工作把知识追踪用于程序性知识习得，奠定了 BKT 的隐状态更新框架（Corbett & Anderson, 1995）。后续工作通过个性化参数、层级模型、遗忘项、表现因素和多知识组件模型缓解同质学生假设，但参数可辨识性仍依赖足够长且覆盖充分的交互序列。

### 2.2 HMM 与状态空间模型

BKT 是受限 HMM。更一般的 HMM 可以增加多个掌握等级、错误类型或教学阶段；连续状态空间模型则以 `z_t` 表示连续知识向量，并以状态转移和观测方程表达学习与遗忘。优点是可以明确区分“状态不确定性”和“观测噪声”；缺点是状态空间和转移矩阵会快速膨胀。

在实践中应保留后验不确定性，而不是只保存一个掌握分数。对学生或知识组件样本很少时，后验区间比点估计更适合触发“继续诊断”而非直接跳题。

## 3. IRT、PFA 与教育测量

### 3.1 IRT 的测量含义

一维 2PL IRT 的正确作答概率可写为：

```text
P(Y_i=1 | theta_s) = sigmoid(a_i * (theta_s - b_i))
```

`theta_s` 是学生能力，`b_i` 是题目难度，`a_i` 是区分度；3PL 还加入猜测参数。IRT 的重点是测量不变性、题目参数和能力参数的可比性，不等同于按时间更新“学会了哪些知识”。多维 IRT 可把能力分解到知识维度，但需要稳定的题目-知识映射和足够覆盖。

### 3.2 PFA 与性能因素

Performance Factors Analysis（PFA）直接使用某知识组件上的历史正确/错误次数及其系数预测下一次表现，通常比 BKT 更容易加入练习量、成功和失败因素。它不一定显式给出二元掌握状态，因此更适合当作可解释的预测基线或与 IRT 组合。

### 3.3 测量层的建议

数学系统至少应报告：题目难度漂移、学生能力校准、不同知识组件的覆盖率、组间测量公平性和置信区间。不能把 AUC 提高解释为“学生学会更多”；学习增益需要前后测、延迟测或随机/准实验设计。

## 4. DKT 及深度知识追踪家族

### 4.1 DKT

DKT 使用 RNN/LSTM 将交互序列编码为隐藏向量，直接预测下一题正确率（Piech et al., 2015）。它绕过了手工知识组件映射，能够从题目-作答序列中学习长程模式，但隐藏维度不天然对应知识概念，容易出现状态漂移、预测不一致和训练/部署分布差异。

DKT 的最低可接受基线应包括：按学生划分的时间外推评估、与 BKT/IRT/PFA 的比较、校准曲线、不同序列长度的敏感性分析，以及对隐藏状态的可解释性检查。只报告随机切分 AUC 会造成严重的信息泄漏风险。

### 4.2 记忆网络和注意力模型

- **DKVMN**：以可读写的 key-value memory 区分知识地址和掌握值，增强了局部解释性（Zhang et al., 2017）。
- **SAKT**：用自注意力从历史交互中检索与当前题目相似的行为（Pandey & Karypis, 2019）。
- **SAINT**：使用编码器-解码器式注意力，同时建模题目、作答和位置（Choi et al., 2020）。
- **AKT 及正则化变体**：加入时间距离、单调性或注意力约束，试图减少注意力模型的不稳定。

注意力权重不能直接当作因果解释。应通过遮蔽、反事实题目替换、概念级消融和跨数据集复现来检验“模型关注什么”。

### 4.3 深度 KT 的可复现性问题

Sarsa、Leinonen 与 Hellas（2022）的实证研究强调，深度 KT 对超参数、序列长度、数据切分和指标选择敏感。对于项目落地，模型卡片至少应记录：数据版本、题目编码、学生切分方式、随机种子、早停规则、校准方法和失败样本。

## 5. GKT 与图结构知识追踪

### 5.1 GKT 的共同思想

Graph-based Knowledge Tracing（GKT）类方法把知识组件或题目作为图节点，把先修、相似、共现或题目-知识关联作为边，在图卷积/消息传递后再进行时间更新。其抽象形式为：

```text
h_k^{(l+1)} = AGG({ h_j^{(l)} : j in N(k) }, e_{jk})
z_t = TemporalUpdate(z_{t-1}, h_{K(q_t)}, y_t)
```

图模型适合表达“一个题目的作答会影响相邻概念”的归纳偏置，也能把知识图谱中的先修关系接入状态估计；风险是图边质量直接决定传播方向。错误的先修边、过密的相似边或来自同一题库的共现边，都可能造成虚假的知识迁移。

### 5.2 图结构的工程约束

1. 区分边的来源：专家先修、题库共现、文本相似、学生行为推断不能混成同一种边。
2. 保存边的置信度、版本和时间戳；图谱升级后重新评估历史模型。
3. 做无图、随机图、边遮蔽和方向反转消融，确认收益来自结构而非额外参数。
4. 对跨章节迁移使用冷启动评估，防止训练集和测试集共享同一题目文本或图邻居。

## 6. KQGC 与 DHKT：缩写审计

### 6.1 当前可确认的结论

在当前项目文件、可访问的本地文献和本轮可用的学术元数据端点中，没有找到同时满足“唯一模型展开、作者、正式论文或 DOI”的 `KQGC` 或 `DHKT` 记录。它们不是像 BKT、DKT、DKVMN、SAKT 那样在知识追踪领域具有唯一公共含义的缩写。

### 6.2 不能直接采用的可能展开

- `KQGC` 可能被作者写作 *Knowledge Query Graph Convolution*、*Knowledge Graph/Question Graph Convolution* 或其他题目/知识图卷积变体；仅凭缩写不能确定输入图、卷积方式或论文。
- `DHKT` 可能被写作 *Deep Hybrid Knowledge Tracing*、*Deep Hierarchical Knowledge Tracing* 或 *Dynamic/Domain-aware Hybrid Knowledge Tracing*；这些展开对应的模型假设并不相同。

因此，本综述不把任一展开写成已验证事实。要纳入项目研究矩阵，至少需要补充：论文标题、第一作者、年份、会议/期刊、DOI 或 arXiv ID，以及该缩写在原文中的定义句。拿到唯一标识后再补充模型结构、基线、数据集和结果，避免把不同论文拼成一个“模型”。

## 7. 知识图谱与知识追踪的结合方式

知识图谱主要解决“概念如何关联、题目需要什么、先修路径是什么”；知识追踪解决“这个学生现在掌握多少、证据有多大不确定性”。两者可以按三种方式组合：

1. **输入约束**：用题目-知识映射和先修邻域生成模型输入，状态模型仍由 BKT/IRT/DKT 负责。
2. **表示传播**：用 GNN/Transformer 编码图节点，再由序列模型更新学生状态。
3. **决策约束**：把图谱路径、先修可达性和课程边界作为推荐动作的硬约束或惩罚项。

第三种方式通常最容易控制风险：即使状态估计模型更新，推荐器仍不会跳过未满足的先修条件。图谱边应保留证据来源，不能把大语言模型生成的关系直接当作事实边。

## 8. 组合优化、动态规划与强化学习

### 8.1 题目选择的组合优化

给定候选题集合 `Q`，可用整数规划选择一个长度为 `m` 的序列，目标同时考虑预期学习增益、覆盖、难度匹配、重复惩罚、内容约束和时间预算。典型形式为：

```text
max  sum_i gain_i*x_i - lambda*redundancy(x)
s.t. sum_i x_i = m
     prerequisite_constraints(x) = true
     time_budget(x) <= B
```

如果目标函数近似次模，贪心算法可作为可解释基线；如果有严格先修、章节和时间约束，可使用整数规划或束搜索。先做离线候选排序，再进行短序列优化，比直接让策略网络自由生成题目更可控。

### 8.2 动态规划

当状态可压缩为掌握向量、剩余时间和章节位置时，动态规划可以递推：

```text
V_t(s) = max_a [ r(s,a) + gamma * E[V_{t+1}(s')] ]
```

它适合小规模、规则清晰的练习路径；状态维度一大就会遭遇组合爆炸。可采用知识组件分组、近似价值函数或模型预测控制降低复杂度。

### 8.3 多臂老虎机与强化学习

上下文多臂老虎机适合“每次只选一道题、反馈较快、长期影响有限”的场景；强化学习适合提示、复习间隔和多步课程路径。奖励不应只用下一题正确率，应加入延迟后测、完成率、认知负荷和公平性约束。在线探索必须有安全策略、停止规则和对照组，不能在高风险学习任务中无界试错。

## 9. 实验设计与因果推断

### 9.1 预测实验

按学生划分训练/验证/测试，另外做时间外推和新题目冷启动。指标至少包括 AUC、准确率、对数损失、Brier 分数、ECE 校准误差和分组性能。比较 BKT、IRT/PFA、DKT、注意力模型和图模型时，保持相同数据切分和输入信息。

### 9.2 干预实验

若要声称“推荐策略提高学习效果”，应采用学生级或班级级随机试验，预注册主要结局和分析计划；无法随机时，使用差分中的差分、倾向得分、断点回归或目标试验模拟，并明确未测混杂的限制。历史日志上的离线策略评估不能单独证明因果收益。

### 9.3 消融与公平

必须分别消融：知识图谱边、时间特征、提示行为、题目文本、学生历史长度和策略探索。报告不同基础能力、学习速度、设备和课程组的校准与错误率，避免总体平均指标掩盖某一群体的系统性误诊。

## 10. 面向本项目的推荐架构

```text
交互日志/题目/图谱
        |
        v
测量层：IRT/PFA + 数据质量与题目参数
        |
        v
状态层：BKT 作为可解释基线，DKT/SAKT/GKT 作为候选模型
        |
        v
不确定性层：置信区间、校准、异常行为与冷启动标记
        |
        v
决策层：候选过滤 -> 组合优化/DP -> 安全策略或老虎机
        |
        v
教学动作：下一题、提示、复习、讲解、人工介入
```

实施顺序建议是：

1. 先建立可复现的 BKT、IRT/PFA 和规则推荐基线。
2. 再加入 DKT/注意力模型，固定数据切分和校准流程。
3. 在知识图谱版本稳定后加入 GKT，并做图边消融。
4. 最后将候选模型接入离线策略评估，再进行小规模、可停止的在线实验。

## 11. 风险、边界与验收清单

- **数据泄漏**：同一题目文本、同一学生、未来行为或图邻居不能跨训练和测试泄漏。
- **概念漂移**：课程、题库和评分规则变化后，重新校准题目参数与状态模型。
- **伪解释**：注意力权重、GNN 消息或相关性不等于因果机制。
- **过度自动化**：低置信度状态应转人工诊断或补充题，而不是强行推荐。
- **数据库恢复后**：先做 SQLite `PRAGMA quick_check`、表结构和数据量检查，再做线上接口测试。

验收最低标准：离线基线可复现；深度模型不劣于简单基线的校准；图模型在无图/随机图消融中显示结构收益；推荐策略在预先定义的学习增益和公平性指标上通过门槛。

## 参考文献与核验状态

以下条目来自项目本地文献、正式出版信息或 Crossref 可定位记录；未能唯一核验的条目不作为已证实参考文献使用。

1. Corbett, A. T., & Anderson, J. R. (1995). Knowledge tracing: Modeling the acquisition of procedural knowledge. *User Modeling and User-Adapted Interaction, 4*(4), 253–278. https://doi.org/10.1007/BF01099821
2. Piech, C., Bassen, J., Huang, J., Ganguli, S., Sahami, M., Guibas, L. J., & Sohl-Dickstein, J. (2015). Deep knowledge tracing. *Advances in Neural Information Processing Systems, 28*. https://doi.org/10.48550/arXiv.1506.05908
3. Zhang, J., Shi, X., King, I., & Yeung, D.-Y. (2017). Dynamic key-value memory networks for knowledge tracing. In *Proceedings of the 26th International Conference on World Wide Web* (pp. 765–774). ACM.
4. Pandey, S., & Karypis, G. (2019). A self-attentive model for knowledge tracing. In *Proceedings of the 12th International Conference on Educational Data Mining* (pp. 384–389).
5. Choi, Y., Lee, Y., Cho, J., Baek, J., Kim, B., Cha, Y., Shin, D., Bae, C., & Heo, J. (2020). Towards an appropriate query, key, and value computation for knowledge tracing. In *Proceedings of the 7th ACM Conference on Learning @ Scale* (pp. 341–344). ACM.
6. Pavlik, P. I., Jr., Cen, H., & Koedinger, K. R. (2009). Performance factors analysis: A new alternative to knowledge tracing. In *Proceedings of the 14th International Conference on Artificial Intelligence in Education* (pp. 531–538). IOS Press.
7. Gervet, T., Koedinger, K., Schneider, J., & Mitchell, T. (2020). When is deep learning the best approach to knowledge tracing? *Journal of Educational Data Mining, 12*(3), 31–54.
8. Sarsa, S., Leinonen, J., & Hellas, A. (2022). Empirical evaluation of deep learning models for knowledge tracing: Of hyperparameters and metrics on performance and replicability. *Journal of Educational Data Mining, 14*(2), 32–102.
9. Embretson, S. E., & Reise, S. P. (2000). *Item response theory for psychologists*. Lawrence Erlbaum Associates.
10. Hernán, M. A., & Robins, J. M. (2020). *Causal inference: What if*. Chapman & Hall/CRC.
11. Sutton, R. S., & Barto, A. G. (2018). *Reinforcement learning: An introduction* (2nd ed.). MIT Press.

**待补证据**：GKT 的具体论文版本、KQGC 的唯一展开和 DHKT 的唯一展开。补充任一模型的 DOI/arXiv ID 后，应追加作者、结构图、数据集、基线、指标和可复现实验配置，而不是沿用本节的缩写审计结论。

**AI 使用声明**：本重建稿由 AI 辅助整理；模型名称、引用和结论仍需在正式发表或生产决策前由研究者对照原始论文复核。
