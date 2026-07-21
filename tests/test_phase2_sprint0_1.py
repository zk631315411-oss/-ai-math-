"""Phase 2 Sprint 0-1 验证测试。

运行: python tests/test_phase2_sprint0_1.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_init_db():
    """1. 数据库表创建"""
    from app.db.connection import init_db, get_conn

    init_db()
    conn = get_conn()
    tables = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()]
    conn.close()

    assert "knowledge_stages" in tables, f"knowledge_stages missing, tables={tables}"
    assert "pending_stage_updates" in tables, f"pending_stage_updates missing"
    print("[PASS] 1. Tables created: knowledge_stages, pending_stage_updates")


def test_knowledge_stages_crud():
    """2. knowledge_stages CRUD + pending 竞态防护"""
    from app.db.knowledge_stages_db import (
        get_stage, update_stage, get_stages_batch, consume_pending
    )

    TEST_USER = "test_sprint0_user"
    TEST_CONCEPT = "矩阵的秩"

    # 新用户 stage=None（NULL）
    s = get_stage(TEST_USER, TEST_CONCEPT)
    assert s is None, f"Expected None for new user, got {s}"

    # 写入 pending delta
    update_stage(TEST_USER, TEST_CONCEPT, delta=2, source="test")
    # 应该能从 pending 读到聚合值
    s = get_stage(TEST_USER, TEST_CONCEPT)
    assert s == 2, f"Expected stage=2 from pending, got {s}"

    # 写入 override
    update_stage(TEST_USER, TEST_CONCEPT, override=4, source="test")

    # 应该读到 override=4 覆盖前面的 delta
    s = get_stage(TEST_USER, TEST_CONCEPT)
    assert s == 4, f"Expected stage=4 from override+delta, got {s}"

    # 再写一个 delta=-1
    update_stage(TEST_USER, TEST_CONCEPT, delta=-1, source="test")
    s = get_stage(TEST_USER, TEST_CONCEPT)
    assert s == 3, f"Expected stage=3 after delta=-1, got {s}"

    # 批量查询
    batch = get_stages_batch(TEST_USER, [TEST_CONCEPT, "不存在概念"])
    assert len(batch) == 2

    # Worker 消费 pending → canonical
    consume_pending(TEST_USER)
    s = get_stage(TEST_USER, TEST_CONCEPT)
    assert s == 3, f"After consume_pending expected canonical stage=3, got {s}"

    # 清理
    conn = __import__("app.db.connection", fromlist=["get_conn"]).get_conn()
    conn.execute("DELETE FROM knowledge_stages WHERE user_id=?", (TEST_USER,))
    conn.execute("DELETE FROM pending_stage_updates WHERE user_id=?", (TEST_USER,))
    conn.commit()
    conn.close()

    print("[PASS] 2. CRUD + pending merge + Worker consume")


def test_scaffolding_levels():
    """3. 四级学徒脚手架层级计算 + 子模式偏移"""
    from app.services.scaffolding_controller import (
        scaffolding_controller, ApprenticeshipLevel,
    )

    tests = [
        # (stage, submode, expected)
        (0, "unclassified", ApprenticeshipLevel.MODELING),
        (2, "unclassified", ApprenticeshipLevel.COACHING),
        (2, "preview", ApprenticeshipLevel.MODELING),       # 预习偏示范
        (3, "connected_review", ApprenticeshipLevel.FADING), # 串联偏撤除
        (None, "unclassified", ApprenticeshipLevel.MODELING),  # 未测定保守
        (5, "unclassified", ApprenticeshipLevel.FADING),
    ]
    for stage, submode, expected in tests:
        level = scaffolding_controller.determine_level(stage, submode)
        assert level == expected, \
            f"stage={stage}, submode={submode}: expected {expected}, got {level}"

    # 防抖测试
    from app.services.scaffolding_controller import SessionState
    session = SessionState(consecutive_errors=2, last_level=ApprenticeshipLevel.COACHING)
    level = scaffolding_controller.determine_level(3, "unclassified", session)
    assert level == ApprenticeshipLevel.SCAFFOLDING, \
        f"Debounce: with 2 errors and last=coaching, stage=3 should not go above scaffolding, got {level}"

    print("[PASS] 3. Scaffolding levels + submode offset + debounce")


def test_keyword_detection():
    """4. 零延迟关键词检测"""
    from app.services.scaffolding_controller import scaffolding_controller

    assert scaffolding_controller.detect_struggle("我算错了怎么办"), "struggle not detected"
    assert scaffolding_controller.detect_struggle("搞不懂这个公式"), "struggle not detected"
    assert not scaffolding_controller.detect_struggle("请讲一下特征值"), "false positive"
    print("[PASS] 4. Struggle keyword detection")


def test_prompt_assembly():
    """5. 动态 Prompt 组装"""
    from app.services.prompt_engine import build_prompt
    from app.services.scaffolding_controller import ApprenticeshipLevel, StudentLevel

    prompt = build_prompt(
        question="特征值怎么求？",
        page_context={
            "chapter_name": "特征值与特征向量",
            "content": "定义：...",
            "start_page": 100, "end_page": 120,
        },
        whitelist={"macro": "允许使用第1-5章定理", "micro": "矩阵乘法、行列式"},
        profile={"grade": "大二", "weak_points": ["矩阵运算"]},
        teaching_mode="socratic",
        socratic_submode="unclassified",
        history=[{"user": "行列式怎么算", "assistant": "...先展开..."}],
        student_stage=2,
        prereq_gaps=[{"name": "行列式", "stage": 2, "is_gap": True}],
        student_level=StudentLevel.INTERMEDIATE,
        apprenticeship_level=ApprenticeshipLevel.COACHING,
        user_message_for_struggle="",
    )

    required_segments = [
        "苏格拉底式",
        "前置知识提醒",
        "知识点放行清单",
        "学生画像",
        "教材上下文",
        "对话历史",
        "特征值怎么求",
    ]
    for seg in required_segments:
        assert seg in prompt, f"Missing segment: '{seg}'"

    print(f"[PASS] 5. Prompt assembly ({len(prompt)} chars, all {len(required_segments)} segments)")

    # 测试 struggle 注入
    prompt2 = build_prompt(
        question="我算错了吗？",
        page_context=None, whitelist=None, profile=None,
        teaching_mode="socratic", socratic_submode="unclassified",
        history=None, student_stage=3, prereq_gaps=[],
        student_level=StudentLevel.INTERMEDIATE,
        apprenticeship_level=ApprenticeshipLevel.SCAFFOLDING,
        user_message_for_struggle="我算错了吗？",
    )
    assert "遇到了困难" in prompt2, "Struggle hint not injected"
    print(f"[PASS] 5b. Struggle hint injection verified")


def test_prereq_gaps_fallback():
    """6. 前置检测 fallback（Neo4j 不可用时）"""
    from app.db.knowledge_stages_db import update_stage, get_stage

    TEST_USER = "test_prereq_fallback"

    # 写入一个 stage=2 的概念（表示前置不牢）
    update_stage(TEST_USER, "行列式", override=2, source="test")

    # 验证 get_stage 能读到
    s = get_stage(TEST_USER, "行列式")
    assert s == 2, f"Expected stage=2, got {s}"

    # 清理
    conn = __import__("app.db.connection", fromlist=["get_conn"]).get_conn()
    conn.execute("DELETE FROM knowledge_stages WHERE user_id=?", (TEST_USER,))
    conn.execute("DELETE FROM pending_stage_updates WHERE user_id=?", (TEST_USER,))
    conn.commit()
    conn.close()

    print("[PASS] 6. Prerequisite stage detection (without Neo4j)")


if __name__ == "__main__":
    test_init_db()
    test_knowledge_stages_crud()
    test_scaffolding_levels()
    test_keyword_detection()
    test_prompt_assembly()
    test_prereq_gaps_fallback()
    print("\n=== Sprint 0-1 所有测试通过 ===")
