"""Phase 2 全量集成测试（Sprint 0-3）"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_sprint0_knowledge_stages():
    """Sprint 0: knowledge_stages CRUD + pending + Worker"""
    from app.db.connection import init_db, get_conn
    from app.db.knowledge_stages_db import (
        get_stage, update_stage, get_stages_batch, consume_pending
    )
    init_db()

    U, C = "test_ks_user", "test_concept"
    assert get_stage(U, C) is None, "New user should be NULL"

    update_stage(U, C, delta=2, source="test")
    assert get_stage(U, C) == 2

    update_stage(U, C, override=4, source="test")
    assert get_stage(U, C) == 4

    update_stage(U, C, delta=-1, source="test")
    assert get_stage(U, C) == 3

    consume_pending(U)
    assert get_stage(U, C) == 3

    batch = get_stages_batch(U, [C, "nonexistent"])
    assert len(batch) == 2 and batch[0]["stage"] == 3

    conn = get_conn()
    conn.execute("DELETE FROM knowledge_stages WHERE user_id=?", (U,))
    conn.execute("DELETE FROM pending_stage_updates WHERE user_id=?", (U,))
    conn.commit(); conn.close()

    return True


def test_sprint0_scaffolding():
    """Sprint 0: scaffolding levels + submode offset + debounce"""
    from app.services.scaffolding_controller import (
        scaffolding_controller, ApprenticeshipLevel, SessionState
    )
    cases = [
        (0, "unclassified", ApprenticeshipLevel.MODELING),
        (2, "unclassified", ApprenticeshipLevel.COACHING),
        (2, "preview", ApprenticeshipLevel.MODELING),
        (3, "connected_review", ApprenticeshipLevel.FADING),
        (None, "unclassified", ApprenticeshipLevel.MODELING),
        (5, "unclassified", ApprenticeshipLevel.FADING),
    ]
    for stage, submode, expected in cases:
        level = scaffolding_controller.determine_level(stage, submode)
        assert level == expected, f"stage={stage} submode={submode}: {level} != {expected}"

    # debounce: 2 errors + stage=3 should not go past scaffolding
    s = SessionState(consecutive_errors=2, last_level=ApprenticeshipLevel.COACHING)
    level = scaffolding_controller.determine_level(3, "unclassified", s)
    assert level == ApprenticeshipLevel.SCAFFOLDING, f"Debounce failed: {level}"

    # keyword detection
    assert scaffolding_controller.detect_struggle("我算错了")
    assert not scaffolding_controller.detect_struggle("请讲特征值")

    return True


def test_sprint0_socratic_schema():
    """Sprint 0: socratic_submode in QARequest"""
    from app.models.schemas import QARequest
    req = QARequest(question="test", teaching_mode="socratic", socratic_submode="preview")
    assert req.socratic_submode == "preview"
    assert QARequest(question="q").socratic_submode == "unclassified"  # default
    return True


def test_sprint1_prompt_engine():
    """Sprint 1: dynamic prompt assembly"""
    from app.services.prompt_engine import build_prompt
    from app.services.scaffolding_controller import ApprenticeshipLevel, StudentLevel

    prompt = build_prompt(
        question="test question?",
        page_context={"chapter_name": "Ch1", "content": "...", "start_page": 1, "end_page": 10},
        whitelist={"macro": "macro text", "micro": "concepts"},
        profile={"grade": "2", "weak_points": ["weak1"]},
        teaching_mode="socratic", socratic_submode="unclassified",
        history=[{"user": "prev q", "assistant": "prev a"}],
        student_stage=2, prereq_gaps=[{"name": "conceptX", "stage": 1, "is_gap": True}],
        student_level=StudentLevel.INTERMEDIATE,
        apprenticeship_level=ApprenticeshipLevel.COACHING,
        user_message_for_struggle="",
    )

    segments = ["苏格拉底式", "前置知识提醒", "知识点放行清单", "学生画像",
                "教材上下文", "对话历史", "test question?"]
    for seg in segments:
        assert seg in prompt, f"Missing: {seg}"

    # struggle injection
    prompt2 = build_prompt(
        question="我算错了吗", page_context=None, whitelist=None, profile=None,
        teaching_mode="socratic", socratic_submode="unclassified", history=None,
        student_stage=3, prereq_gaps=[],
        student_level=StudentLevel.INTERMEDIATE,
        apprenticeship_level=ApprenticeshipLevel.SCAFFOLDING,
        user_message_for_struggle="我算错了吗",
    )
    assert "遇到了困难" in prompt2
    return True


def test_sprint2_exercise_crud():
    """Sprint 2: exercise CRUD + CAS + hint chain"""
    from app.db.exercise_bank_db import (
        save_exercise, get_exercise, list_exercises,
        submit_answer, record_result, update_hint_level, report_error,
    )
    from app.db.connection import get_conn

    U = "test_ex_crud"
    eid = save_exercise(U, "matrix", "basic", 3, "q?", "ans", "verification ok",
                        ["h1", "h2", "h3"], {"type": "matrix_rank", "matrix": [[1,0],[0,1]]})
    assert eid

    ex = get_exercise(eid)
    assert ex["topic"] == "matrix" and ex["hints"] == ["h1", "h2", "h3"]

    assert submit_answer(eid, "student answer") == 1
    assert submit_answer(eid, "duplicate") == 0  # CAS

    record_result(eid, True)
    ex = get_exercise(eid)
    assert ex["is_answered"] == 1 and ex["is_correct"] == 1

    # hint chain
    for i in range(1, 4):
        assert update_hint_level(eid) == i
    assert update_hint_level(eid) == 3  # capped at 3

    report_error(eid)
    assert get_exercise(eid)["quality_score"] == -1

    assert len(list_exercises(U)) >= 1

    conn = get_conn()
    conn.execute("DELETE FROM exercise_bank WHERE user_id=?", (U,))
    conn.commit(); conn.close()
    return True


def test_sprint2_markdown_parser():
    """Sprint 2: streaming markdown parsing + chunk buffer"""
    from app.services.exercise_generator import parse_markdown_sections

    md = "## title\nQuestion text\n## answer\nAnswer text\n## hints\n1. h1\n2. h2\n3. h3\n## verification\nVerified\n## computable\n```json\n{\"type\":\"matrix_rank\",\"expected\":[2]}\n```"

    p = parse_markdown_sections(md)
    assert "Question text" in p["question"]
    assert "Answer text" in p["answer"]
    assert len(p["hints"]) == 3
    assert "Verified" in p["verification"]
    assert p["computable"]["type"] == "matrix_rank"
    return True


def test_sprint2_sympy_sandbox():
    """Sprint 2: SymPy sandbox all operations"""
    from app.services.sympy_sandbox import verify_computable

    # eigenvalues (correct)
    r = verify_computable("matrix_eigenvalues", {"matrix": [[1,2],[3,4]]}, ["5.3723", "-0.3723"])
    assert r["success"], f"Eigenvalues: {r}"

    # determinant
    r = verify_computable("matrix_determinant", {"matrix": [[1,2],[3,4]]}, -2)
    assert r["success"], f"Det: {r}"

    # rank
    r = verify_computable("matrix_rank", {"matrix": [[1,0],[0,1]]}, 2)
    assert r["success"], f"Rank: {r}"

    # whitelist rejection
    assert not verify_computable("rm -rf /", {}, [])["success"]

    # size limit
    big = [[0]*15 for _ in range(15)]
    assert not verify_computable("matrix_determinant", {"matrix": big}, 0)["success"]

    # value mismatch
    r = verify_computable("matrix_eigenvalues", {"matrix": [[1,2],[3,4]]}, ["999","888"])
    assert not r["success"] and "mismatch" in r.get("error", "")

    return True


def test_sprint2_error_analyzer():
    """Sprint 2: error analyzer categories"""
    from app.services.error_analyzer import ERROR_CATEGORIES

    assert "concept_confusion" in ERROR_CATEGORIES
    assert "calculation_error" in ERROR_CATEGORIES
    assert "logic_gap" in ERROR_CATEGORIES

    total = sum(len(v) for v in ERROR_CATEGORIES.values())
    assert total == 12, f"Expected 12 subtypes, got {total}"
    return True


def test_sprint2_routes():
    """Sprint 2: exercise API routes registered"""
    from app.main import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    for ep in ["/api/exercise/generate", "/api/exercise/list",
               "/api/exercise/{exercise_id}/submit",
               "/api/exercise/{exercise_id}/hint",
               "/api/exercise/{exercise_id}/report-error"]:
        assert ep in routes, f"Missing: {ep}"
    return True


def test_sprint3_insight_cache():
    """Sprint 3: insight cache logic"""
    from app.services.insight_generator import get_cached_or_generate, _empty_report

    # New user (no profile) should return None
    r = get_cached_or_generate("nonexistent_user_12345")
    assert r is None

    # Empty report structure
    er = _empty_report()
    for key in ["overall_assessment", "strengths", "weaknesses",
                "learning_trend", "recommended_focus", "recommended_strategy",
                "motivation_message"]:
        assert key in er, f"Missing key in empty report: {key}"

    return True


def test_sprint3_routes():
    """Sprint 3: insight API routes registered"""
    from app.main import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    for ep in ["/api/auth/insight", "/api/auth/insight/regenerate"]:
        assert ep in routes, f"Missing: {ep}"
    return True


def test_full_integration():
    """End-to-end: full app loads, all expected routes present"""
    from app.main import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]

    expected = [
        "/", "/health",
        "/api/qa/solve-stream",
        "/api/auth/login", "/api/auth/register",
        "/api/auth/insight", "/api/auth/insight/regenerate",
        "/api/exercise/generate", "/api/exercise/list",
        "/api/exercise/{exercise_id}/submit",
        "/api/exercise/{exercise_id}/hint",
        "/api/exercise/{exercise_id}/report-error",
    ]
    for ep in expected:
        assert ep in routes, f"Missing route: {ep}"

    assert "智学助手" in app.title
    return True


if __name__ == "__main__":
    tests = [
        ("Sprint 0", "knowledge_stages CRUD + Worker", test_sprint0_knowledge_stages),
        ("Sprint 0", "scaffolding levels + debounce", test_sprint0_scaffolding),
        ("Sprint 0", "socratic_submode schema", test_sprint0_socratic_schema),
        ("Sprint 1", "dynamic prompt assembly", test_sprint1_prompt_engine),
        ("Sprint 2", "exercise CRUD + CAS", test_sprint2_exercise_crud),
        ("Sprint 2", "markdown parser", test_sprint2_markdown_parser),
        ("Sprint 2", "SymPy sandbox", test_sprint2_sympy_sandbox),
        ("Sprint 2", "error analyzer structure", test_sprint2_error_analyzer),
        ("Sprint 2", "exercise routes", test_sprint2_routes),
        ("Sprint 3", "insight cache logic", test_sprint3_insight_cache),
        ("Sprint 3", "insight routes", test_sprint3_routes),
        ("Full", "integration", test_full_integration),
    ]

    passed = 0
    for sprint, name, fn in tests:
        try:
            assert fn()
            print(f"  [PASS] {sprint}: {name}")
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {sprint}: {name} — {e}")
        except Exception as e:
            print(f"  [ERROR] {sprint}: {name} — {type(e).__name__}: {e}")

    print(f"\n=== {passed}/{len(tests)} tests passed ===")
    if passed == len(tests):
        print("Phase 2 (Sprint 0-3) all tests passed!")
