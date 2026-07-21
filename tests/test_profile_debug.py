"""
学生画像系统端到端诊断脚本
检查: chat_logs → LLM诊断 → math_profiles → prompt_engine 注入
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.chat_log_db import get_unanalyzed_chat_logs, get_users_with_unanalyzed_logs
from app.db.math_profile_db import get_math_profile, get_last_diagnosed_at
from app.db.diagnostic import get_concepts_by_sequence_id
from app.db.knowledge_stages_db import get_stages_summary, get_stage
from app.services.diagnostic_worker import should_trigger_diagnostic_batch
from app.db.connection import get_conn


def check_data():
    """检查数据积累"""
    print("=" * 50)
    print("1. 数据积累检查")
    print("=" * 50)

    conn = get_conn()
    c = conn.cursor()

    c.execute("SELECT count(*) FROM chat_logs WHERE is_analyzed=0")
    unanalyzed = c.fetchone()[0]
    print(f"  chat_logs 待分析: {unanalyzed}")

    c.execute("SELECT count(*) FROM chat_logs WHERE is_analyzed=1")
    analyzed = c.fetchone()[0]
    print(f"  chat_logs 已分析: {analyzed}")

    c.execute("SELECT count(*) FROM math_profiles")
    profiles = c.fetchone()[0]
    print(f"  math_profiles 用户数: {profiles}")

    c.execute("SELECT count(*) FROM question_assessments")
    qa = c.fetchone()[0]
    print(f"  question_assessments 记录: {qa}")

    c.execute("SELECT count(*) FROM knowledge_stages WHERE stage IS NOT NULL")
    staged = c.fetchone()[0]
    print(f"  knowledge_stages 有阶段: {staged}")

    conn.close()

    # 检查哪些用户满足诊断条件
    users = get_users_with_unanalyzed_logs()
    print(f"\n  满足诊断阈值的用户数: {len(users)}")
    for uid in users:
        logs = get_unanalyzed_chat_logs(uid)
        should = should_trigger_diagnostic_batch(uid)
        last_diag = get_last_diagnosed_at(uid)
        print(f"    {uid[:12]}... logs={len(logs)} trigger={should} last_diagnosed={last_diag}")


def check_neo4j():
    """检查 Neo4j 连接和概念查询"""
    print("\n" + "=" * 50)
    print("2. Neo4j 概念查询检查")
    print("=" * 50)
    seq_ids = ["V1-C01-S03", "V1-C01-S01", "V1-C00-S00"]
    for sid in seq_ids:
        try:
            concepts = get_concepts_by_sequence_id(sid)
            print(f"  {sid}: {len(concepts)} concepts", concepts[:3] if concepts else "(空)")
        except Exception as e:
            print(f"  {sid}: FAILED - {e}")


def check_prompt_injection():
    """检查画像是否注入 Prompt"""
    print("\n" + "=" * 50)
    print("3. Prompt 注入检查")
    print("=" * 50)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM math_profiles WHERE latest_diagnostic_report != '{}' LIMIT 1")
    row = c.fetchone()
    conn.close()

    if row:
        uid = row["user_id"]
        profile = get_math_profile(uid)
        if profile:
            report = profile.get("latest_diagnostic_report", {})
            if isinstance(report, str):
                try: report = json.loads(report)
                except: pass
            weak_node = report.get("weak_node", "") if isinstance(report, dict) else ""
            suggestion = report.get("intervention_suggestion", "") if isinstance(report, dict) else ""
            dims = profile.get("dimensions", {})
            print(f"  用户 {uid[:12]}... grade={profile.get('grade','?')}")
            print(f"  维度: {json.dumps(dims, ensure_ascii=False)}")
            print(f"  薄弱节点: {weak_node}")
            print(f"  干预建议: {suggestion[:100] if suggestion else '(无)'}")
            print(f"  → 这些会注入到 prompt_engine.build_prompt 的 intervention_text 和 profile_block 中")
    else:
        print("  没有有效的诊断报告")


def check_stages():
    """检查认知阶段"""
    print("\n" + "=" * 50)
    print("4. 认知阶段检查")
    print("=" * 50)

    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT user_id FROM chat_logs LIMIT 1")
    row = c.fetchone()
    conn.close()

    if row:
        uid = row["user_id"]
        summary = get_stages_summary(uid)
        print(f"  用户 {uid[:12]}... 阶段汇总: {json.dumps(summary, ensure_ascii=False)}")

        # 测试单个概念
        stage = get_stage(uid, "数域")
        print(f"  概念'数域'阶段: {stage}")


def check_full_chain():
    """模拟诊断链路"""
    print("\n" + "=" * 50)
    print("5. 诊断链路模拟")
    print("=" * 50)

    users = get_users_with_unanalyzed_logs()
    if not users:
        print("  没有满足条件的用户（需要 ≥5 条未分析记录）")
        print("  提示: 多问几个问题，chat_logs 积累到 5 条后自动触发")
        return

    uid = users[0]
    logs = get_unanalyzed_chat_logs(uid)
    print(f"  用户 {uid[:12]}... 待分析记录: {len(logs)}")

    for log in logs[:3]:
        print(f"    id={log['id'][:12]}... seq={log.get('sequence_id','?')} q={log.get('question','')[:40]}")


if __name__ == "__main__":
    check_data()
    check_neo4j()
    check_prompt_injection()
    check_stages()
    check_full_chain()
    print("\n✅ 诊断完成")
