"""Test prompt fix on cloud: verify LLM copies Neo4j concept names exactly."""
if __name__ != "__main__":
    import pytest
    pytest.skip("manual cloud diagnostic script", allow_module_level=True)

import sys, sqlite3, asyncio, time
import os
from pathlib import Path

import pytest

if os.getenv("RUN_CLOUD_TESTS", "").lower() not in {"1", "true", "yes"}:
    pytest.skip("cloud diagnostic test; set RUN_CLOUD_TESTS=1 to run", allow_module_level=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
DB = os.getenv("AI_MATH_DB_PATH", str(PROJECT_ROOT / "data" / "learning.db"))

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT id FROM users WHERE username=?", ("kz",))
uid = c.fetchone()[0]
c.execute("UPDATE math_profiles SET last_diagnosed_at=NULL WHERE user_id=?", (uid,))
c.execute("DELETE FROM user_knowledge_stats WHERE user_id=?", (uid,))
c.execute("DELETE FROM knowledge_stages WHERE user_id=?", (uid,))
c.execute("DELETE FROM pending_stage_updates WHERE user_id=?", (uid,))
conn.commit()
conn.close()

from app.db.knowledge_stats_db import update_knowledge_stats
from app.db.diagnostic import trigger_diagnostic_if_needed
from app.db.knowledge_stages_db import consume_pending, get_stages_summary

for _ in range(4):
    update_knowledge_stats(uid, "行列式展开")

print("Triggering diagnostic...")
asyncio.run(trigger_diagnostic_if_needed(uid, "行列式展开", "V1-C01-S01"))
time.sleep(15)

consume_pending(uid)
summary = get_stages_summary(uid)
print("knowledge_stages:", summary)

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT concept_name, stage FROM knowledge_stages WHERE user_id=?", (uid,))
concepts = [(r[0], r[1]) for r in c.fetchall()]
print("Concepts written by LLM:")
for name, stage in concepts:
    print("  %s: stage=%s" % (name, stage))
conn.close()

# Check if names exist in Neo4j
from neo4j import GraphDatabase
from app.config import config
driver = GraphDatabase.driver(config.NEO4J_URI, auth=(config.NEO4J_USER, config.NEO4J_PASSWORD))
with driver.session() as session:
    print("\nNeo4j exact match check:")
    for name, stage in concepts:
        r = session.run("MATCH (c:Concept {name: $n}) RETURN c.name", n=name).single()
        match = "EXACT" if r else "NO MATCH"
        # Try CONTAINS
        if not r:
            r2 = session.run("MATCH (c:Concept) WHERE c.name CONTAINS $n RETURN c.name LIMIT 1", n=name).single()
            match = "CONTAINS: " + r2[0] if r2 else "NOT FOUND"
        print("  %s: %s" % (name, match))
driver.close()

# Test knowledge graph
from app.auth.jwt_handler import create_access_token
from app.routers.auth import get_knowledge_graph
token = create_access_token({"user_id": uid, "username": "kz"})
kg = get_knowledge_graph(authorization="Bearer " + token)
wcs = kg.get("weak_concepts", [])
print("\nKnowledge Graph: %d concepts" % len(wcs))
for wc in wcs:
    pre_n = len(wc.get("prerequisites", []))
    dep_n = len(wc.get("dependents", []))
    print("  %s: pre=%d dep=%d" % (wc["name"], pre_n, dep_n))
    for p in wc.get("prerequisites", [])[:2]:
        print("    <- %s" % p["name"])
    for d in wc.get("dependents", [])[:2]:
        print("    -> %s" % d["name"])
