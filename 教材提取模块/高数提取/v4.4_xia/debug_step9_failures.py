from __future__ import annotations

from neo4j import GraphDatabase


BATCH = "gaoshu_xia_c07_c10_rerun_20260626"


def main() -> None:
    driver = GraphDatabase.driver("neo4j://127.0.0.1:7687", auth=("neo4j", "zhang2004"))
    queries = [
        (
            "sufficient",
            """
            MATCH (n:KGNode)
            WHERE n.import_batch=$batch
              AND (n.name CONTAINS '充分条件'
                   OR n.name CONTAINS '二阶偏导数'
                   OR n.name CONTAINS '极值点')
            RETURN n.name AS name,n.type AS type,n.chapter AS chapter,n.section AS section
            LIMIT 30
            """,
        ),
        (
            "double_iterated",
            """
            MATCH (n:KGNode)
            WHERE n.import_batch=$batch
              AND (n.name CONTAINS '二重积分'
                   OR n.name CONTAINS '二次积分'
                   OR n.name CONTAINS '累次积分')
            RETURN n.name AS name,n.type AS type,n.chapter AS chapter,n.section AS section
            LIMIT 50
            """,
        ),
        (
            "paths",
            """
            MATCH (a:KGNode),(b:KGNode)
            WHERE a.import_batch=$batch
              AND b.import_batch=$batch
              AND a.name='二重积分'
              AND b.name CONTAINS '二次积分'
            MATCH p=shortestPath((a)-[*..5]-(b))
            RETURN b.name AS target,[x IN nodes(p)|x.name] AS nodes,[r IN relationships(p)|type(r)] AS rels
            LIMIT 10
            """,
        ),
    ]
    with driver.session() as session:
        for title, query in queries:
            print("---", title)
            for record in session.run(query, batch=BATCH):
                print(dict(record))
    driver.close()


if __name__ == "__main__":
    main()
