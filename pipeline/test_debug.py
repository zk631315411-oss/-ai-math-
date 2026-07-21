import os
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# ZHIPU_API_KEY must be set in environment or .env file
llm = ChatOpenAI(
    api_key=os.getenv("ZHIPU_API_KEY", ""),
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    model="glm-4-plus",
    temperature=0
)

# 2. 我们自己写一个坚不可摧的系统指令，绝对不给大模型发挥废话的空间
prompt = PromptTemplate.from_template("""
你是一个极其严谨的知识图谱提取专家。请从以下文本中提取数学概念(Concept)和定理(Theorem)，以及它们之间的关系。

【绝对指令】
你必须且只能输出一个标准的 JSON 对象，绝不允许包含任何额外的解释文字、问候语或前缀（绝不允许出现类似“Node 1”这样的字眼）。
必须完全符合以下 JSON 结构：
{{
  "nodes": [
    {{"id": "节点名称", "type": "Concept 或 Theorem"}}
  ],
  "edges": [
    {{"source": "起点名称", "target": "终点名称", "type": "PREREQUISITE_OF 或 RELATED_TO"}}
  ]
}}

要提取的文本：
{text}
""")

# 3. 将 Prompt、大模型和 JSON解析器 串联成一条最基础、最稳定的核心管线
chain = prompt | llm | JsonOutputParser()

# 4. 测试文本
dummy_text = """
##### 矩阵初等变换
矩阵的初等变换是高等代数中的基础概念。
##### 克莱姆法则定理
定理说明：克莱姆法则依赖于矩阵初等变换来进行推导，用于求解线性方程组。
"""

print("🚀 绕过脆弱的官方模块，使用底层核心管线开始强制抽取...")
result = chain.invoke({"text": dummy_text})

print("\n✅ 抽取彻底成功！干净的结构化数据如下：")
print("节点数:", len(result.get("nodes", [])))
print("边数:", len(result.get("edges", [])))
print("\n详细数据字典:", result)