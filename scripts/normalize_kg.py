"""高代 Neo4j 图谱归一化：删 TOC 噪音、修复拼写、定理名加章前缀。"""
import os, re, sys
from pathlib import Path
from neo4j import GraphDatabase

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())

URI = os.getenv("NEO4J_URI", "neo4j+s://c60acc31.databases.neo4j.io")
USER = os.getenv("NEO4J_USER", "c60acc31")
PWD = os.getenv("NEO4J_PASSWORD", "")
DB = os.getenv("NEO4J_DATABASE", "c60acc31")

driver = GraphDatabase.driver(URI, auth=(USER, PWD))

def extract_chapter_num(ch: str) -> str | None:
    m = re.search(r'第\s*(\d+)\s*章', ch)
    return m.group(1) if m else None

def clean():
    with driver.session(database=DB) as s:
        # ---- 1. 删除 TOC 噪音 Section ----
        r = s.run("MATCH (s:Section) WHERE s.chapter CONTAINS '…' DETACH DELETE s")
        n_toc = r.consume().counters.nodes_deleted
        print(f"[1/5] 删除 TOC Section: {n_toc}")

        # ---- 2. USE_CONCEPT → USES_CONCEPT ----
        r = s.run("""
            MATCH (a)-[r:USE_CONCEPT]->(b)
            MERGE (a)-[r2:USES_CONCEPT]->(b)
            SET r2 = properties(r)
            DELETE r
        """)
        n_use = r.consume().counters.relationships_created
        print(f"[2/5] USE_CONCEPT → USES_CONCEPT: {n_use} 条")

        # ---- 3. 定理/定义/推论/命题加章前缀 ----
        # 收集所有需要重命名的实体
        entities = s.run("""
            MATCH (n)
            WHERE (n:Theorem OR n:Concept OR n:Formula OR n:Problem)
              AND n.chapter IS NOT NULL
              AND n.chapter <> ''
              AND n.chapter <> '未知章'
            RETURN n.name AS name, n.chapter AS ch, labels(n) AS lbs, id(n) AS nid
        """).data()

        renamed = 0
        for e in entities:
            ch_num = extract_chapter_num(e["ch"])
            if not ch_num:
                continue
            name = e["name"]
            # 跳过已经有章前缀的、英文名的、太短的
            if name.startswith("Ch") or name.startswith("Ch"):
                continue
            if re.match(r'^[A-Za-z_]', name):  # 英文名跳过
                continue
            # 只处理数字编号的定理/定义等
            if re.match(r'^(定理|定义|推论|命题|引理|性质|例|题|答案)\s*\d', name):
                new_name = f"Ch{ch_num}-{name}"
                s.run("MATCH (n) WHERE id(n)=$nid SET n.name=$nn", nid=e["nid"], nn=new_name)
                renamed += 1

        print(f"[3/5] 定理/定义加章前缀: {renamed} 个")

        # ---- 4. 删除无意义 Section（空 snippet 或仅数字） ----
        r = s.run("""
            MATCH (s:Section)
            WHERE s.snippet IS NULL OR trim(s.snippet) = ''
            DETACH DELETE s
        """)
        n_empty = r.consume().counters.nodes_deleted
        print(f"[4/5] 删除空白 Section: {n_empty}")

        # ---- 5. 最终统计 ----
        total = s.run("MATCH (n) RETURN count(n)").single()[0]
        edges = s.run("MATCH ()-[r]->() RETURN count(r)").single()[0]
        print(f"[5/5] 清理完成: {total} 节点, {edges} 条边")

if __name__ == "__main__":
    clean()
    driver.close()
