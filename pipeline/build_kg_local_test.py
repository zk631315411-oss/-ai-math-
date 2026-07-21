# build_kg 本地测试版 - 不写入 Neo4j，只输出实体和关系
# 用途：测试本地 LLM 的抽取效果，不影响线上数据库

import os
import json
import re
import hashlib
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from tqdm import tqdm


class TolerantJsonOutputParser(BaseOutputParser):
    r"""
    容错 JSON 解析器，兼容两类常见脏数据：
    1. Markdown 包围（```json ... ```）
    2. LaTeX 命令中的无效 JSON 转义（如 \mid、\sum、\alpha 等）
       LaTeX 里单反斜杠如 \\mid 是合法的，但 json.loads() 会把它当非法转义报 Invalid \\escape
       修复策略：把所有不在有效 JSON 转义序列（\\ \/ \b \f \n \r \t \u）中的 \X 替换为 \\\\X
    """

    def parse(self, text: str) -> dict:
        # 步骤1：去掉 markdown 代码块包围
        text = re.sub(r'^```json\s*', '', text.strip(), flags=re.IGNORECASE)
        text = re.sub(r'^```\s*', '', text.strip())
        text = re.sub(r'\s*```$', '', text.strip())

        # 步骤2：找到 JSON 对象边界
        start = text.find('{')
        if start == -1:
            raise ValueError(f"No JSON object found. Text: {text[:200]}")

        json_str = text[start:]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            if "Invalid \\escape" in str(e):
                # 遇到 LaTeX 转义错误，修复后重试
                fixed = self._fix_latex_escapes(json_str)
                try:
                    return json.loads(fixed)
                except json.JSONDecodeError:
                    pass  # 仍然失败，用原始错误信息
            raise ValueError(f"JSON 解析失败: {e}\nText: {text[:300]}")

    def _fix_latex_escapes(self, s: str) -> str:
        """把 LaTeX 命令里的单反斜杠 \X 替换为 \\\\X，使 json.loads() 能通过"""
        result = []
        i = 0
        while i < len(s):
            c = s[i]
            if c == '\\' and i + 1 < len(s):
                n = s[i + 1]
                # 已经是合法的 JSON 转义序列，保留原样
                if n in ['\\', '/', 'b', 'f', 'n', 'r', 't', 'u']:
                    result.append(s[i:i + 2])
                    i += 2
                    continue
                # LaTeX 命令（如 \mid \sum \alpha），替换为 \\\\X
                result.append('\\\\' + n)
                i += 2
                continue
            result.append(c)
            i += 1
        return ''.join(result)

    @property
    def _type(self) -> str:
        return "tolerant_json"

# ==========================================
# 1. 本地 LLM 配置（替换远程 API）
# ==========================================
# 使用本地 Ollama 服务
llm = ChatOpenAI(
    model="qwen2.5:7b",           # 替换为你的本地模型名
    base_url="http://localhost:11434/v1",
    api_key="ollama",              # OLLAMA 不需要真实 key，随便填
    temperature=0
)

# ==========================================
# 2. 提示词（与 build_kg.py 完全一致）
# ==========================================
prompt = PromptTemplate.from_template("""
你是一个极其严谨的知识图谱提取专家。请从以下文本中提取关键实体，以及它们之间的逻辑关系。

【允许提取的实体类型 (type)】
1. Concept (数学概念、定义)
2. Theorem (定理、引理、推论、性质)
3. Formula (重要的数学公式名称)
4. Problem (例题、习题、答案)

【允许提取的关系类型 (type)】
- PREREQUISITE_OF (前置知识，A是B的前提)
- DERIVED_FROM (推导自，A推导出了B)
- USES_CONCEPT (题目使用了某个概念，A使用了B)
- HAS_ANSWER (题目拥有答案，A的答案是B)
- RELATED_TO (其他相关)

【绝对指令】
1. 你必须且只能输出一个标准的 JSON 对象，绝不允许包含任何额外的解释文字或 Markdown 标记。
2. edges 列表中的 source 和 target 必须【一字不差】地等于 nodes 里的 id。
3. 尽可能多地挖掘节点间的隐含逻辑关系，不要让节点孤立。

必须完全符合以下 JSON 结构：
{{
  "nodes": [
    {{"id": "实体名称", "type": "上述4种类型之一"}}
  ],
  "edges": [
    {{"source": "起点id", "target": "终点id", "type": "上述5种关系之一"}}
  ]
}}

要提取的文本：
{text}
""")
chain = prompt | llm | TolerantJsonOutputParser()


def generate_sequence_id(metadata: dict) -> str:
    """无状态解析 MD 标题，生成补零定长字符串，如 V1-C01-S01-U01-T00"""
    c, s, u = 0, 0, 0

    m_c = re.search(r'第(\d+)章', metadata.get("Chapter", ""))
    if m_c: c = int(m_c.group(1))

    m_s = re.search(r'^\s*\d+\.(\d+)', metadata.get("Section", ""))
    if m_s: s = int(m_s.group(1))

    m_u = re.search(r'^\s*\d+\.\d+\.(\d+)', metadata.get("Subsection", ""))
    if m_u: u = int(m_u.group(1))

    return f"V1-C{c:02d}-S{s:02d}-U{u:02d}-T00"


# ==========================================
# 3. 读取并切分文档
# ==========================================
MD_FILE = "structured_高代下.md"
MAX_CHUNKS = 20   # 测试时限制块数，设为 None 则处理全部

print(f"读取 {MD_FILE} ...")

if not os.path.exists(MD_FILE):
    print(f"[ERROR] 文件不存在: {MD_FILE}")
    exit()

with open(MD_FILE, "r", encoding="utf-8") as f:
    content = f.read()

headers_to_split_on = [
    ("#", "Chapter"),
    ("##", "Section"),
    ("###", "Subsection"),
    ("####", "Topic"),
    ("#####", "Entity")
]
markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
splits = markdown_splitter.split_text(content)

# 过滤目录区和答案区
splits = [c for c in splits if '…' not in c.page_content[:80] and '习题答案' not in c.page_content]

if MAX_CHUNKS:
    splits = splits[:MAX_CHUNKS]

print(f"共 {len(splits)} 个文本块，开始测试...\n")

# ==========================================
# 4. 逐块调用 LLM，只打印输出，不写 Neo4j
# ==========================================
for i, chunk in enumerate(splits):
    chunk_text = chunk.page_content
    metadata = chunk.metadata
    seq_id = generate_sequence_id(metadata)

    print(f"{'='*60}")
    print(f"[块 {i+1}/{len(splits)}]")
    print(f"sequence_id : {seq_id}")
    print(f"Chapter     : {metadata.get('Chapter', '')}")
    print(f"Section     : {metadata.get('Section', '')}")
    print(f"Subsection  : {metadata.get('Subsection', '')}")
    print(f"Entity      : {metadata.get('Entity', '')}")
    print(f"-" * 40)
    print(f"文本预览(前200字):\n{chunk_text[:200]}")
    print()

    try:
        result = chain.invoke({"text": chunk_text})

        nodes = result.get("nodes", [])
        edges = result.get("edges", [])

        chapter = metadata.get("Chapter", "未知章")
        subsection = metadata.get("Subsection", "未知节")

        def generate_unique_id(entity_name):
            name_str = str(entity_name).strip()
            if not name_str:
                return ""
            if "例" in name_str or "题" in name_str or "习题" in name_str:
                return f"{chapter}_{subsection}_{name_str}"
            return name_str

        print(f"--- 抽取结果 ---")
        print(f"节点数: {len(nodes)}")
        for node in nodes:
            label = node.get("type", "")
            name = node.get("id", "")
            uid = generate_unique_id(name)
            if label in ["Concept", "Theorem", "Formula", "Problem"]:
                print(f"  [{label:10s}] {name}  (id={uid})")

        print(f"关系数: {len(edges)}")
        for edge in edges:
            src = generate_unique_id(str(edge.get("source", "")).strip())
            tgt = generate_unique_id(str(edge.get("target", "")).strip())
            rel = edge.get("type", "RELATED_TO")
            print(f"  [{rel:20s}] {src} -> {tgt}")

        print(f"\n[块 {i+1}] LLM 输出:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    except Exception as e:
        print(f"[ERROR] 块 {i+1} 失败: {e}")

    print()

print(f"\n{'='*60}")
print("测试完成（未写入 Neo4j）")
