"""Test: can the diagnostic detect stage 3-5 from an advanced student?"""
import sys, os, asyncio, time, sqlite3
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "learning.db")

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT id, username FROM users WHERE username='advanced_test'")
row = c.fetchone()
if row:
    uid = row[0]
    print(f"Using existing user: {row[1]}")
else:
    # Create test user
    import uuid
    uid = str(uuid.uuid4())
    c.execute("INSERT INTO users(id, username, password_hash, device_id) VALUES(?,?,?,?)", (uid, "advanced_test", "test", "test_device"))
    conn.commit()
    print(f"Created user: advanced_test ({uid[:16]}...)")

# Clean slate
c.execute("UPDATE math_profiles SET last_diagnosed_at=NULL WHERE user_id=?", (uid,))
c.execute("DELETE FROM user_knowledge_stats WHERE user_id=?", (uid,))
c.execute("DELETE FROM pending_stage_updates WHERE user_id=?", (uid,))
c.execute("DELETE FROM knowledge_stages WHERE user_id=?", (uid,))
c.execute("DELETE FROM chat_history WHERE user_id=?", (uid,))
conn.commit()
conn.close()

from app.db.math_profile_db import get_math_profile, save_math_profile
from app.db.knowledge_stats_db import update_knowledge_stats
from app.db.chat_history_db import save_chat_history
from app.db.diagnostic import trigger_diagnostic_if_needed
from app.db.knowledge_stages_db import get_stages_summary, consume_pending, get_user_avg_stage

# Simulate ADVANCED student (stage 4-5): questions show deep understanding
topic = "特征值与特征向量"
sequence_id = "V1-C02-S05"

advanced_questions = [
    "特征多项式在代数闭域上的分解和Jordan标准形的关系，如果域不是代数闭的，怎么从有理标准形入手理解？",
    "幂零矩阵的极小多项式一定是x^k形式对吧？那它的特征值全为0，但反过来特征值全为0的矩阵不一定幂零吧——能举个反例吗",
    "谱分解定理的条件是正规算子——如果矩阵不可对角化但仍然是正规的，谱分解还成立吗？我在想Schur分解和谱分解的关系",
]

advanced_answers = [
    "好问题。在非代数闭域上，有理标准形确实更基础——它通过Frobenius标准形刻画了矩阵模的结构。关键区别在于：Jordan标准形依赖于特征值的存在（需要代数闭域），而有理标准形只需要极小多项式的不可约分解。两者通过Galois理论联系：代数闭域上的Jordan形对应有理标准形中各不变因子分解为一次因式的特殊情况。",
    "对，x^k是幂零矩阵的极小多项式形式，特征多项式则是x^n（全为0）。你的反例直觉是对的：考虑矩阵[[0,1],[0,0]]是幂零的（2阶Jordan块），特征值全为0。非幂零的例子：[[0,0],[0,0]]是零矩阵（平凡幂零）。更反直觉的非幂零例子其实更好：考虑一个非零矩阵但所有特征值为0——这种矩阵确实必然幂零（Hamilton-Cayley）。所以你的'反过来不成立'其实在有限维是成立的——特征值全为0 ⇔ 特征多项式为x^n ⇔ 幂零（Hamilton-Cayley），方向是充要的。",
    "精准的区分。不可对角化但正规的矩阵确实不存在——正规性的谱定理要求矩阵可酉对角化。所以正规⇔可酉对角化是充要条件。但Schur分解就弱得多：任何复方阵都可Schur三角化，不一定需要正规性。两者的层级关系是：可对角化 ⊂ 正规 ⊂ 可Schur三角化。Schur分解是通向谱分解的阶梯——先用Schur上三角化，再验证是否为对角阵来判断正规性。",
]

# Ensure profile exists
profile = get_math_profile(uid)
if not profile:
    save_math_profile(uid)
    print("Created math_profile")

# Simulate 3 rounds
print("Simulating 3 advanced Q&A rounds:")
for i in range(3):
    r = update_knowledge_stats(uid, topic)
    print(f"  Q{i+1}: consecutive={r['consecutive_turns']} total={r['total_asks']}")
    print(f"    Q: {advanced_questions[i][:80]}...")
    save_chat_history(uid, advanced_questions[i], advanced_answers[i])

# Trigger diagnostic
print(f"\nTriggering diagnostic: {topic} ({sequence_id})")
asyncio.run(trigger_diagnostic_if_needed(uid, topic, sequence_id))

print("Waiting 15s for LLM...")
for i in range(15):
    time.sleep(1)
    print(f"  {i+1}s...", end='\r')

# Check pending
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT concept_name, override_stage, source FROM pending_stage_updates WHERE user_id=?", (uid,))
pending = c.fetchall()
print(f"\nPending: {len(pending)} rows")
for p in pending:
    print(f"  {p[0]}: stage={p[1]} src={p[2]}")
conn.close()

# Consume
consume_pending(uid)
summary = get_stages_summary(uid)

print(f"\n{'='*60}")
print(f"FINAL: {summary}")
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT concept_name, stage FROM knowledge_stages WHERE user_id=? ORDER BY stage DESC", (uid,))
for r in c.fetchall():
    tag = "✅ HIGH" if r[1] >= 3 else ("⚠️ MID" if r[1] == 2 else "  low")
    print(f"  {tag} | {r[0]:30s} stage={r[1]}")
conn.close()

print(f"\nget_user_avg_stage(): {get_user_avg_stage(uid)}")
avg = summary['avg_stage']
if avg >= 3:
    print(f">>> CAN detect advanced (avg={avg}) ✅")
elif avg >= 2:
    print(f">>> Borderline (avg={avg}) - partial detection")
else:
    print(f">>> CANNOT detect advanced (avg={avg}) ❌")
