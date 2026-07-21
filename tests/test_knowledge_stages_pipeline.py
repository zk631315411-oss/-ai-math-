"""
E2E test: knowledge_stages 数据链路打通
模拟 3+ 次同一章节提问 → 触发诊断 → 验证 knowledge_stages 落库

本地运行: cd d:\ai-math && python tests/test_knowledge_stages_pipeline.py
"""
import sys, os, json, asyncio, time, sqlite3

# Ensure we're in project root and it's on path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)
sys.path.insert(0, PROJECT_ROOT)

DB = os.path.join('data', 'learning.db')


def header(s):
    sep = '=' * 60
    print(f'\n{sep}\n  {s}\n{sep}')


# ── Find test user ──
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT id, username FROM users LIMIT 5")
users = [(r[0], r[1]) for r in c.fetchall()]
if not users:
    print('ERROR: No users found in DB. Register a test user first.')
    sys.exit(1)

uid, uname = users[0][0], users[0][1]
print(f'Test user: {uname} ({uid[:12]}...)')

# Clean previous state for clean test
c.execute("UPDATE math_profiles SET last_diagnosed_at=NULL WHERE user_id=?", (uid,))
c.execute("DELETE FROM user_knowledge_stats WHERE user_id=?", (uid,))
c.execute("DELETE FROM pending_stage_updates WHERE user_id=?", (uid,))
c.execute("DELETE FROM knowledge_stages WHERE user_id=?", (uid,))
conn.commit()
conn.close()

# Imports after path setup
from app.db.math_profile_db import get_math_profile, save_math_profile
from app.db.knowledge_stats_db import update_knowledge_stats
from app.db.chat_history_db import save_chat_history
from app.db.diagnostic import trigger_diagnostic_if_needed

topic = "行列式展开定理"
# Use a real sequence_id that exists in Neo4j (V1-C01-S01 = 行列式相关)
sequence_id = "V1-C01-S01"

# ── Step 1: Initial state ──
header("Step 1: Initial knowledge_stages state")

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM knowledge_stages WHERE user_id=?", (uid,))
ks_before = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM pending_stage_updates WHERE user_id=?", (uid,))
pending_before = c.fetchone()[0]
conn.close()

print(f'knowledge_stages rows: {ks_before}')
print(f'pending_stage_updates rows: {pending_before}')

# ── Step 2: Ensure profile exists ──
header("Step 2: Ensure profile + simulate 3 Q&A rounds")

profile = get_math_profile(uid)
if not profile:
    print('No profile, creating...')
    save_math_profile(uid)
    profile = get_math_profile(uid)

avg = profile.get('overall_average', 'N/A')
print(f'overall_average: {avg}')

# Simulate 3 Q&A rounds with realistic chat_history (diagnostic LLM reads this)
questions = [
    "行列式展开定理是什么？为什么要把n阶转化为n-1阶？",
    "按第一行展开和按第一列展开有什么区别？",
    "展开定理中每一项的符号是怎么确定的？",
]
answers = [
    "行列式展开定理（Laplace展开）：n阶行列式可以按任意一行（或列）展开，等于该行各元素与其代数余子式乘积之和。降阶计算的目的是把复杂问题简化——n阶直接算太复杂，转化为多个n-1阶逐步递归。",
    "按行展开和按列展开在公式形式上对称——按第i行展开用a_{ij}乘A_{ij}对j求和，按第j列展开用a_{ij}乘A_{ij}对i求和。本质都是把n阶降到n-1阶来计算。",
    "展开式中每一项的符号由(-1)^{i+j}决定，其中i是行号j是列号。这个规律来源于排列的逆序数——行列式的定义本身就是基于排列奇偶性的交错和。",
]

for i in range(3):
    r = update_knowledge_stats(uid, topic)
    print(f'  Q{i+1}: consecutive={r["consecutive_turns"]}, total={r["total_asks"]}')
    save_chat_history(uid, questions[i], answers[i])

# ── Step 3: Trigger diagnostic (with sequence_id!) ──
header("Step 3: Trigger diagnostic with sequence_id")

print(f'topic: {topic}')
print(f'sequence_id: {sequence_id}')
asyncio.run(trigger_diagnostic_if_needed(uid, topic, sequence_id))

# Wait for async LLM diagnosis to complete (background task)
print('Waiting 15s for async LLM diagnosis...')
for i in range(15):
    time.sleep(1)
    print(f'  {i+1}s...', end='\r')

# ── Step 4: Check pending_stage_updates ──
header("Step 4: Check pending_stage_updates")

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute(
    "SELECT concept_name, delta_value, override_stage, source FROM pending_stage_updates WHERE user_id=? ORDER BY created_at ASC",
    (uid,),
)
pending_rows = c.fetchall()
print(f'pending_stage_updates rows: {len(pending_rows)}')
for row in pending_rows:
    print(f'  concept={row[0]}, delta={row[1]}, override={row[2]}, source={row[3]}')
conn.close()

# ── Step 5: Consume pending directly (no need to wait for Worker) ──
header("Step 5: Consume pending → knowledge_stages")

from app.db.knowledge_stages_db import consume_pending

consume_pending(uid)
print('consume_pending() called')

conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute(
    "SELECT concept_name, stage, confidence FROM knowledge_stages WHERE user_id=? ORDER BY concept_name",
    (uid,),
)
ks_rows = c.fetchall()
c.execute("SELECT COUNT(*) FROM pending_stage_updates WHERE user_id=?", (uid,))
pending_after = c.fetchone()[0]
conn.close()

print(f'\nknowledge_stages rows: {len(ks_rows)}')
for row in ks_rows:
    print(f'  concept={row[0]}, stage={row[1]}, confidence={row[2]}')
print(f'pending_stage_updates remaining: {pending_after} (should be 0)')

# ── Step 6: Verify scaffolding reads non-null stage ──
header("Step 6: Verify downstream consumers work")

from app.db.knowledge_stages_db import get_stage

# Get a stage for one of the concepts
if ks_rows:
    test_concept = ks_rows[0][0]
    stage = get_stage(uid, test_concept)
    print(f'get_stage(\"{test_concept}\") = {stage}')
else:
    print('(no knowledge_stages rows to test)')
    # Try with chapter name for the topic
    stage = get_stage(uid, topic)
    print(f'get_stage(\"{topic}\") = {stage}')

# ── Verdict ──
header("VERDICT")

checks = [
    ('knowledge_stages has rows (was empty before)', len(ks_rows) > 0),
    ('pending_stage_updates consumed', pending_after == 0),
    ('all stages are 0-5 integers', all(isinstance(r[1], int) and 0 <= r[1] <= 5 for r in ks_rows) if ks_rows else False),
]

all_ok = True
for name, ok in checks:
    tag = 'PASS' if ok else 'FAIL'
    print(f'  [{tag}] {name}')
    if not ok:
        all_ok = False
        # Additional debug if failed
        if 'consumed' in name and not ok:
            print(f'    -> pending still has {pending_after} rows (worker may not have run yet)')

result = '>>> ALL PASSED <<<' if all_ok else '??? SOME FAILED ???'
print(f'\n  {result}')
