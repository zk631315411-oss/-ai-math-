"""Run diagnostics for ALL kz topics on cloud."""
if __name__ != "__main__":
    import pytest
    pytest.skip("manual cloud diagnostic script", allow_module_level=True)

import sys, os, asyncio, time, sqlite3
sys.path.insert(0, "/opt/ai-math")
DB = "/opt/ai-math/data/learning.db"

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT id FROM users WHERE username='kz'")
uid = c.fetchone()[0]
print(f"kz: {uid[:20]}...\n")

# Show chat_logs by seq
c.execute("SELECT sequence_id, COUNT(*) FROM chat_logs WHERE user_id=? GROUP BY sequence_id", (uid,))
seq_counts = {r[0]: r[1] for r in c.fetchall()}
print("chat_logs:")
for k, v in seq_counts.items():
    print(f"  {k}: {v} records")

# Chat history
c.execute("SELECT question FROM chat_history WHERE user_id=?", (uid,))
qs = c.fetchall()
print(f"\nchat_history: {len(qs)} questions")

# knowledge_stages before
c.execute("SELECT COUNT(*), AVG(CAST(stage AS REAL)) FROM knowledge_stages WHERE user_id=? AND stage IS NOT NULL", (uid,))
ksb = c.fetchone()
print(f"knowledge_stages before: {ksb[0]} rows, avg_stage={ksb[1]}")
conn.close()

from app.db.knowledge_stats_db import update_knowledge_stats
from app.db.diagnostic import trigger_diagnostic_if_needed
from app.db.knowledge_stages_db import get_stages_summary, consume_pending, get_stage, get_user_avg_stage

# Map actual seq IDs to topics
seq_topics = {
    "V1-C01-S03": "行列式展开",
    "V1-C02-S04": "线性方程组",
    "V1-C02-S05": "矩阵特征值",
}

for seq, topic in seq_topics.items():
    count = seq_counts.get(seq, 0)
    if count < 3:
        print(f"\nSkipping {seq} ({topic}): only {count} records")
        continue

    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("DELETE FROM user_knowledge_stats WHERE user_id=? AND topic=?", (uid, topic))
    c.execute("UPDATE math_profiles SET last_diagnosed_at=NULL WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

    for _ in range(4):
        update_knowledge_stats(uid, topic)

    print(f"\nTriggering: {topic} ({seq}), {count} real records...")
    asyncio.run(trigger_diagnostic_if_needed(uid, topic, seq))
    print("  Waiting 12s...")
    time.sleep(12)

# Consume all
consume_pending(uid)
summary = get_stages_summary(uid)
print(f"\n{'='*60}")
print(f"FINAL: knowledge_stages = {summary}")

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT concept_name, stage FROM knowledge_stages WHERE user_id=? ORDER BY stage DESC", (uid,))
for r in c.fetchall():
    print(f"  {r[0]:30s} stage={r[1]}")
conn.close()

print(f"\nget_user_avg_stage(): {get_user_avg_stage(uid)}")
