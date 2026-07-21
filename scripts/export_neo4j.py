"""Export local Neo4j graph to Cypher file (for Aura import)"""
import json
from neo4j import GraphDatabase

URI = "bolt://localhost:7687"
USER = "neo4j"
PASSWORD = "zhang2004"
OUTPUT = "d:/ai-math/data/graph_export.cypher"

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))

with driver.session() as session, open(OUTPUT, "w", encoding="utf-8") as f:
    # Export nodes
    result = session.run("""
        MATCH (n)
        RETURN labels(n) AS labels, properties(n) AS props
    """)
    f.write("// === NODES ===\n")
    count = 0
    for record in result:
        labels = list(record["labels"])
        props = dict(record["props"])
        # Build Cypher CREATE
        label_str = ":".join(labels)
        props_str = json.dumps(props, ensure_ascii=False)
        f.write(f"CREATE (n:{label_str} {{`_props`: {props_str}}});\n")
        count += 1
        if count % 1000 == 0:
            print(f"  Nodes: {count}")

    print(f"Exported {count} nodes")

    # Export relationships
    result = session.run("""
        MATCH (a)-[r]->(b)
        WHERE id(a) IS NOT NULL AND id(b) IS NOT NULL
        RETURN labels(a) AS a_labels, properties(a) AS a_props,
               type(r) AS rel_type, properties(r) AS rel_props,
               labels(b) AS b_labels, properties(b) AS b_props
    """)
    f.write("\n// === RELATIONSHIPS ===\n")
    count = 0
    for record in result:
        a_labels = ":".join(record["a_labels"])
        a_props = json.dumps(dict(record["a_props"]), ensure_ascii=False)
        rel_type = record["rel_type"]
        rel_props = json.dumps(dict(record["rel_props"]), ensure_ascii=False)
        b_labels = ":".join(record["b_labels"])
        b_props = json.dumps(dict(record["b_props"]), ensure_ascii=False)

        f.write(f"MATCH (a:{a_labels} {{`_props`: {a_props}}})\n")
        f.write(f"MATCH (b:{b_labels} {{`_props`: {b_props}}})\n")
        f.write(f"CREATE (a)-[:{rel_type} {rel_props}]->(b);\n")
        count += 1
        if count % 1000 == 0:
            print(f"  Rels: {count}")

    print(f"Exported {count} relationships")

driver.close()
print(f"\nSaved to: {OUTPUT}")
