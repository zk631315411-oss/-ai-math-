# 读书笔记：Dang et al., JCST 2021

**标题**：Constructing an Educational Knowledge Graph with Concepts Linked to Wikipedia
**作者**：党芙蓉 等（国防科技大学）
**出处**：JCST 2021, 36(5): 1200-1211

## 一、规模

跨 Coursera/edX/XuetangX/ICourse 四平台的 MOOC 知识图谱：52,779 实体、30 万三元组、24,188 概念链接到 Wikipedia。

## 二、方法

- 自上而下：Protégé 建本体 → 从 MOOC 平台爬实例 → Wikipedia 链接概念 → Neo4j 存储
- 概念提取：从课程属性（标题/摘要）中提取，Wikipedia 精确匹配或词嵌入语义匹配
- 前置关系：基于 Wikipedia 页面内容和结构推断

## 三、与我们的关系

- 面向 MOOC 资源组织，不面向教材概念提取
- 方法依赖 Wikipedia，中文场景受限
- 直接可用度：极低
