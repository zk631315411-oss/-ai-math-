"""检查 Neo4j 图谱中知识节点的孤立情况"""
import os
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
from langchain_community.graphs import Neo4jGraph

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "")

graph = Neo4jGraph(url=NEO4J_URI, username=NEO4J_USERNAME, password=NEO4J_PASSWORD)

# 1. 各类节点总数
nodes_by_label = graph.query("""
    MATCH (n) WHERE n:Concept OR n:Theorem OR n:Formula OR n:Problem
    RETURN labels(n)[0] AS label, count(n) AS cnt
    ORDER BY cnt DESC
""")
print("=== 节点总数 ===")
for r in nodes_by_label:
    print(f"  {r['label']}: {r['cnt']}")

# 2. 有入边或出边的节点数（非孤立）
connected = graph.query("""
    MATCH (n)-[r]-() WHERE n:Concept OR n:Theorem OR n:Formula
    RETURN labels(n)[0] AS label, count(DISTINCT n) AS connected
""")
print("\n=== 有边的节点 ===")
for r in connected:
    print(f"  {r['label']}: {r['connected']}")

# 3. 完全孤立的节点（没有任何边）
isolated = graph.query("""
    MATCH (n)
    WHERE (n:Concept OR n:Theorem OR n:Formula)
      AND NOT (n)--()
    RETURN count(n) AS isolated
""")
print(f"\n=== 完全孤立节点: {isolated[0]['isolated']} ===")

# 4. 平均度数
degree_stats = graph.query("""
    MATCH (n)
    WHERE n:Concept OR n:Theorem OR n:Formula
    WITH n, size((n)--()) AS deg
    RETURN avg(deg) AS avg_degree, count(n) AS total
""")
print(f"\n=== 平均度: {degree_stats[0]['avg_degree']:.2f} (共{degree_stats[0]['total']}个知识节点) ===")

# 5. 出度分布
dist = graph.query("""
    MATCH (n) WHERE n:Concept OR n:Theorem OR n:Formula
    WITH n, size((n)-->()) AS out_deg
    RETURN out_deg, count(n) AS cnt
    ORDER BY out_deg
""")
print("\n=== 出度分布 ===")
for r in dist:
    bar = "#" * min(int(r['cnt']), 60)
    print(f"  out={r['out_deg']}: {r['cnt']:5d} {bar}")

# 6. 按 section 分组，看每个 section 内节点数量和边数量
section_stats = graph.query("""
    MATCH (s:Section)<-[:TEACH_IN]-(n)
    WHERE n:Concept OR n:Theorem OR n:Formula
    WITH s, count(n) AS node_cnt
    OPTIONAL MATCH (s)<-[:TEACH_IN]-(n1)-[r]->(n2)-[:TEACH_IN]->(s)
    WHERE n1:Concept OR n1:Theorem OR n1:Formula
    WITH s, node_cnt, count(DISTINCT r) AS edge_cnt
    RETURN s.sequence_id AS sid, node_cnt, edge_cnt,
           CASE WHEN node_cnt > 0 THEN toFloat(edge_cnt) / node_cnt ELSE 0 END AS edge_per_node
    ORDER BY node_cnt DESC
    LIMIT 15
""")
print("\n=== 节点最多的15个Section ===")
print(f"  {'sequence_id':20s} | nodes | edges | edges/node")
print(f"  {'-'*20}|-------|-------|----------")
for r in section_stats:
    print(f"  {r['sid']:20s} | {r['node_cnt']:5d} | {r['edge_cnt']:5d} | {r['edge_per_node']:.2f}")

# 7. 孤立节点样例（前10个）
isolated_samples = graph.query("""
    MATCH (n)
    WHERE (n:Concept OR n:Theorem OR n:Formula)
      AND NOT (n)--()
    RETURN n.id AS id, labels(n)[0] AS type, n.chapter AS chapter
    LIMIT 10
""")
print("\n=== 孤立节点样例 ===")
for r in isolated_samples:
    print(f"  [{r['type']:10s}] {r['id'][:60]}  (chapter={r['chapter']})")

print("\nDone.")
