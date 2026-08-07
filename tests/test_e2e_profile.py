"""
E2E profile test: simulate 3+ questions on same topic, trigger LLM diagnostic, verify profile updates.
Run on server: cd /opt/ai-math && venv/bin/python3 tests/test_e2e_profile.py
"""
if __name__ != "__main__":
    import pytest
    pytest.skip("manual live diagnostic script", allow_module_level=True)

import sys, os, json, asyncio, time, sqlite3
from pathlib import Path

import pytest

if os.getenv("RUN_CLOUD_TESTS", "").lower() not in {"1", "true", "yes"}:
    pytest.skip("cloud diagnostic test; set RUN_CLOUD_TESTS=1 to run", allow_module_level=True)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

DB = os.getenv("AI_MATH_DB_PATH", str(PROJECT_ROOT / "data" / "learning.db"))

def header(s):
    sep = '=' * 50
    print(f'\n{sep}\n  {s}\n{sep}')

# ── Find test user ──
conn = sqlite3.connect(DB)
c = conn.cursor()
c.execute("SELECT id, username FROM users LIMIT 5")
users = [(r[0], r[1]) for r in c.fetchall()]
# Use first user (no prior diagnosis history)
uid, uname = users[0][0], users[0][1]
print(f'Test user: {uname} ({uid[:12]}...)')

# Clean previous state: remove diagnostic lock + clear topic stats
c.execute("UPDATE math_profiles SET last_diagnosed_at=NULL WHERE user_id=?", (uid,))
c.execute("DELETE FROM user_knowledge_stats WHERE user_id=?", (uid,))
conn.commit()
conn.close()

from app.db.math_profile_db import get_math_profile, save_math_profile
from app.db.knowledge_stats_db import update_knowledge_stats
from app.db.question_assessment_db import get_question_assessments
from app.db.chat_history_db import save_chat_history, get_chat_history
from app.db.diagnostic import trigger_diagnostic_if_needed

topic = "行列式展开定理"

# ── Step 1: initial state ──
header("Step 1: Initial state")
profile = get_math_profile(uid)
if not profile:
    print('No profile, creating...')
    save_math_profile(uid)
    profile = get_math_profile(uid)

avg = profile.get('overall_average', 'N/A')
dim_sum = sum(v for d in profile.get('dimensions', {}).values() for v in d.values())
assess_before = len(get_question_assessments(uid, 100))
print(f'overall_average: {avg}')
print(f'dimension sum: {dim_sum}')
print(f'assessments: {assess_before}')

# ── Step 2: simulate 3 questions with real-ish chat_history ──
header("Step 2: 3 consecutive questions (with chat_history for LLM context)")
questions = [
    "行列式展开定理是什么？为什么要把n阶转化为n-1阶？",
    "按第一行展开和按第一列展开有什么区别？",
    "展开定理中每一项的符号是怎么确定的？",
]
answers = [
    "行列式展开定理（Laplace展开）：n阶行列式可以按任意一行（或列）展开，等于该行各元素与其代数余子式乘积之和。转化为n-1阶是为了降阶计算，把复杂问题简化。",
    "按行展开和按列展开在公式形式上对称——按第i行展开用a_{ij}乘A_{ij}对j求和，按第j列展开用a_{ij}乘A_{ij}对i求和。本质上都是把n阶降到n-1阶。",
    "展开式中每一项的符号由(-1)^{i+j}决定，其中i是行号j是列号。这来源于排列的逆序数——行列式的定义本身就是基于排列奇偶性的交错和。",
]

for i in range(3):
    r = update_knowledge_stats(uid, topic)
    print(f'  Q{i+1}: consecutive={r["consecutive_turns"]}, total={r["total_asks"]}')
    save_chat_history(uid, questions[i], answers[i])

# ── Step 3: trigger diagnostic ──
header("Step 3: Trigger diagnostic")
asyncio.run(trigger_diagnostic_if_needed(uid, topic))
print('Waiting 12s for async LLM diagnosis...')
time.sleep(12)

# ── Step 4: verify ──
header("Step 4: Verify results")
profile = get_math_profile(uid)
avg = profile.get('overall_average', 'N/A')
dims = profile.get('dimensions', {})
assess_after = len(get_question_assessments(uid, 100))

print(f'overall_average: {avg}')
print('dimensions:')
for name, d in dims.items():
    total = d['coverage'] + d['radius'] + d['technical']
    tag = ' <--' if total > 0 else ''
    print(f'  {name}: c={d["coverage"]} r={d["radius"]} t={d["technical"]}{tag}')

report = profile.get('latest_diagnostic_report', {})
if isinstance(report, str):
    report = json.loads(report)
print(f'report weak_node: {report.get("weak_node", "?")}')
print(f'report suggestion: {str(report.get("intervention_suggestion", ""))[:120]}')
print(f'assessments: {assess_before} -> {assess_after}')

# ── Verdict ──
header("VERDICT")
has_data = any(v > 0 for d in dims.values() for v in d.values())
checks = [
    ('overall_average >= 0', (avg or 0) >= 0),
    ('dimensions have non-zero data', has_data),
    ('diagnostic report written', bool(report)),
    ('assessments increased', assess_after > assess_before),
]
all_ok = True
for name, ok in checks:
    tag = 'PASS' if ok else 'FAIL'
    print(f'  [{tag}] {name}')
    if not ok: all_ok = False
result = '>>> ALL PASSED <<<' if all_ok else '??? SOME FAILED ???'
print(f'\n  {result}')
