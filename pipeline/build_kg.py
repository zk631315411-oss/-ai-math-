#把已分级的md文件导入neo4j图数据库#
import os
import json
import re
import hashlib
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_community.graphs import Neo4jGraph
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from tqdm import tqdm
# ==========================================
# 1. 数据库与模型配置区 (请填入你的真实信息)
# ==========================================
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

# 连接本地图数据库
graph = Neo4jGraph(
    url=NEO4J_URI,
    username=NEO4J_USERNAME,
    password=NEO4J_PASSWORD
)

# 接入云端千亿级大模型 API (DeepSeek V3)
# ==========================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")

llm = ChatOpenAI(
    api_key=os.getenv("ZHIPU_API_KEY", ""),
    base_url="https://open.bigmodel.cn/api/paas/v4/",
    model="GLM-4.5-Air",
    temperature=0
)

# ==========================================
# 2. 坚不可摧的底层指令管线 (已升级"紧箍咒")
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
chain = prompt | llm | JsonOutputParser()


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
# 3. 读取并切分文档 (text.md)
# ==========================================
print("📖 正在读取并切分 structured_高代上.md...")

if not os.path.exists("structured_高代上.md"):
    print("❌ 错误：当前目录下未找到 structured_高代上.md 文件！")
    exit()

with open("structured_高代上.md", "r", encoding="utf-8") as f:
    content = f.read()

# 使用 Markdown 标题进行结构化切分，这样能保留章节上下文
headers_to_split_on = [
    ("#", "Chapter"),       # 1级帽子：章 (第1章)
    ("##", "Section"),      # 2级帽子：节 (1.1)
    ("###", "Subsection"),  # 3级帽子：小节 (1.1.1)
    ("####", "Topic"),      # 4级帽子：宏观主题分组 (一、二、)
    ("#####", "Entity")     # 5级帽子：具体的实体 (定理1/定义1/题1)
]
markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
splits = markdown_splitter.split_text(content)

# 过滤掉目录区（含 "… (数字)" 后缀）和答案区（含 "习题答案"）
splits = [c for c in splits if '…' not in c.page_content[:80] and '习题答案' not in c.page_content]

print(f"✅ 切分完成，共生成 {len(splits)} 个文本块（过滤目录+答案区后）。")

# ==========================================
# 4. 执行抽取与入库 (工业级强化版)
# ==========================================
from tqdm import tqdm

print("\n🚀 开始自动化构建知识图谱...")

# 📁 1. 初始化状态文件路径
CACHE_FILE = "processed_chunks_cache.json"
ERROR_LOG_FILE = "failed_chunks.log"

# 📁 2. 加载已处理的哈希缓存 (用于增量更新和断点续传)
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        processed_hashes = set(json.load(f))
else:
    processed_hashes = set()

# 获取当前运行的批次时间戳
batch_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for chunk in tqdm(splits, desc="处理进度"):
    chunk_text = chunk.page_content
    chunk_hash = hashlib.md5(chunk_text.encode("utf-8")).hexdigest()

    # ====== 【Step 0：无论是否缓存，先保证物理骨架 100% 健壮】 ======
    seq_id = generate_sequence_id(chunk.metadata)

    graph.query("""
        MERGE (s:Section {sequence_id: $seq_id})
        ON CREATE SET
            s.chapter = $chapter,
            s.section = $section,
            s.subsection = $subsection,
            s.snippet = $snippet
    """, params={
        "seq_id": seq_id,
        "chapter": chunk.metadata.get("Chapter", ""),
        "section": chunk.metadata.get("Section", ""),
        "subsection": chunk.metadata.get("Subsection", ""),
        "snippet": chunk_text[:50]
    })
    # ================================================================

    # 【缓存拦截器：保护昂贵的 LLM 调用】
    if chunk_hash in processed_hashes:
        continue

    try:
        # 1. 调用大模型提取数据
        result = chain.invoke({"text": chunk_text})

        nodes = result.get("nodes", [])
        edges = result.get("edges", [])

        chapter = chunk.metadata.get("Chapter", "未知章")
        subsection = chunk.metadata.get("Subsection", "未知节")

        def generate_unique_id(entity_name):
            name_str = str(entity_name).strip()
            if not name_str:
                return ""
            if "例" in name_str or "题" in name_str or "习题" in name_str:
                return f"{chapter}_{subsection}_{name_str}"
            return name_str

        # 2. 写入知识点节点 (Nodes)
        for node in nodes:
            original_name = str(node["id"]).strip()
            label = str(node["type"]).strip()
            if not original_name:
                continue

            unique_id = generate_unique_id(original_name)

            if label in ["Concept", "Theorem", "Formula", "Problem"]:
                graph.query(f"""
                MERGE (n:{label} {{id: $id}})
                ON CREATE SET n.name = $original_name, n.chapter = $chapter, n.created_at = $time
                ON MATCH SET n.last_updated = $time
                """, params={
                    "id": unique_id,
                    "original_name": original_name,
                    "chapter": chapter,
                    "time": batch_time
                })

                # 【TEACH_IN 双层锚定】
                if label in ["Concept", "Theorem", "Formula"]:
                    graph.query("""
                    MATCH (k {id: $kid})
                    MATCH (s:Section {sequence_id: $sid})
                    MERGE (k)-[r:TEACH_IN]->(s)
                    ON CREATE SET r.created_at = $time
                    """, params={"kid": unique_id, "sid": seq_id, "time": batch_time})

        # 3. 写入逻辑关系 (Edges) - 彻底封杀悬空引用！
        for edge in edges:
            orig_source = str(edge["source"]).strip()
            orig_target = str(edge["target"]).strip()
            raw_type = str(edge.get("type", "RELATED_TO")).strip()
            if not raw_type:
                raw_type = "RELATED_TO"
            rel_type = raw_type.replace(" ", "_").upper()

            source_id = generate_unique_id(orig_source)
            target_id = generate_unique_id(orig_target)

            if source_id and target_id:
                graph.query(f"""
                MATCH (s {{id: $source}})
                MATCH (t {{id: $target}})
                MERGE (s)-[r:{rel_type}]->(t)
                ON CREATE SET r.created_at = $time
                """, params={"source": source_id, "target": target_id, "time": batch_time})

        # 成功后，将哈希加入内存并实时保存到本地文件
        processed_hashes.add(chunk_hash)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_hashes), f)

    except Exception as e:
        error_msg = f"[{datetime.now()}] Error: {str(e)}\nMetadata: {chunk.metadata}\nText: {chunk_text[:100]}...\n{'-'*50}\n"
        print(f"\n⚠️ 发现错误，已记录至黑匣子: {str(e)}")
        with open(ERROR_LOG_FILE, "a", encoding="utf-8") as err_file:
            err_file.write(error_msg)
        continue

print("\n✨ 任务圆满完成！")
print("现在你可以去 Neo4j Browser 执行 'MATCH (n) RETURN n' 查看结果了。")