"""Run diagnostic with cloud kz's real data."""
import sys, os, asyncio, time, sqlite3
sys.path.insert(0, "/opt/ai-math")
DB = "/opt/ai-math/data/learning.db"

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT id, username FROM users WHERE username='kz'")
row = c.fetchone()
uid = row[0]
print(f"kz: {row[1]} ({uid[:16]}...)\n")

c.execute("SELECT COUNT(*) FROM chat_history WHERE user_id=?", (uid,))
ch = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM chat_logs WHERE user_id=?", (uid,))
cl = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM knowledge_stages WHERE user_id=?", (uid,))
ksb = c.fetchone()[0]
print(f"chat_history={ch} chat_logs={cl} knowledge_stages_before={ksb}\n")

c.execute("SELECT question FROM chat_history WHERE user_id=? ORDER BY created_at ASC", (uid,))
for i, r in enumerate(c.fetchall()):
    print(f"  Q{i+1}: {str(r[0])[:80]}")

c.execute("UPDATE math_profiles SET last_diagnosed_at=NULL WHERE user_id=?", (uid,))
c.execute("DELETE FROM user_knowledge_stats WHERE user_id=?", (uid,))
conn.commit()
conn.close()

from app.db.knowledge_stats_db import update_knowledge_stats
from app.db.diagnostic import trigger_diagnostic_if_needed
from app.db.knowledge_stages_db import get_stages_summary, consume_pending, get_stage, get_user_avg_stage

for _ in range(3):
    update_knowledge_stats(uid, "行列式展开")
r = update_knowledge_stats(uid, "行列式展开")
print(f"\nconsecutive={r['consecutive_turns']}, triggering diagnostic...")

asyncio.run(trigger_diagnostic_if_needed(uid, "行列式展开", "V1-C01-S01"))
print("Waiting 15s...")
time.sleep(15)

consume_pending(uid)
summary = get_stages_summary(uid)
print(f"\nknowledge_stages after: {summary}")

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT concept_name, stage FROM knowledge_stages WHERE user_id=? ORDER BY stage DESC", (uid,))
for r in c.fetchall():
    print(f"  {r[0]}: stage={r[1]}")
conn.close()

s = get_stage(uid, "行列式展开")
a = get_user_avg_stage(uid)
print(f"\nget_stage('行列式展开'): {s}")
print(f"get_user_avg_stage(): {a}")
print(f"Final student_stage: {s or a}")
