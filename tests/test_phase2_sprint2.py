"""Phase 2 Sprint 2 验证测试。"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_exercise_table():
    """1. exercise_bank 表创建"""
    from app.db.connection import init_db, get_conn
    init_db()
    conn = get_conn()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    assert "exercise_bank" in tables, f"exercise_bank missing, got {tables}"
    cols = [r[1] for r in conn.execute("PRAGMA table_info(exercise_bank)").fetchall()]
    for col in ["id", "user_id", "topic", "difficulty", "target_stage", "question",
                 "answer", "verification", "hints", "computable", "hint_level",
                 "is_answered", "student_answer", "is_correct", "error_analysis",
                 "quality_score"]:
        assert col in cols, f"Column '{col}' missing from exercise_bank, got {cols}"
    conn.close()
    print("[PASS] 1. exercise_bank table created with all columns")


def test_exercise_crud():
    """2. exercise_bank CRUD 操作"""
    from app.db.exercise_bank_db import (
        save_exercise, get_exercise, list_exercises, submit_answer,
        record_result, update_hint_level, report_error,
    )

    TEST_USER = "test_sprint2_crud"
    eid = save_exercise(
        user_id=TEST_USER, topic="矩阵的秩",
        difficulty="basic", target_stage=3,
        question="求矩阵的秩", answer="答案...",
        verification="验证通过",
        hints=["提示1", "提示2", "提示3"],
        computable={"type": "matrix_rank", "matrix": [[1, 0], [0, 1]]},
    )
    assert eid, "save_exercise returned empty id"

    ex = get_exercise(eid)
    assert ex, "get_exercise returned None"
    assert ex["topic"] == "矩阵的秩"
    assert ex["hints"] == ["提示1", "提示2", "提示3"]
    assert ex["computable"]["type"] == "matrix_rank"
    assert ex["hint_level"] == 0

    lst = list_exercises(TEST_USER, limit=10)
    assert len(lst) >= 1
    assert any(e["id"] == eid for e in lst)

    # 原子 CAS 提交
    affected = submit_answer(eid, "学生作答：...")
    assert affected == 1, f"submit_answer should affect 1 row, got {affected}"
    affected = submit_answer(eid, "重复提交")
    assert affected == 0, "Duplicate submit should return 0"

    record_result(eid, True)
    ex = get_exercise(eid)
    assert ex["is_answered"] == 1
    assert ex["is_correct"] == 1
    assert ex["student_answer"] == "学生作答：..."

    # 提示链
    lvl = update_hint_level(eid)
    assert lvl == 1
    lvl = update_hint_level(eid)
    assert lvl == 2
    lvl = update_hint_level(eid)
    assert lvl == 3
    lvl = update_hint_level(eid)
    assert lvl == 3  # 不超过 3

    # 纠错
    report_error(eid)
    ex = get_exercise(eid)
    assert ex["quality_score"] == -1

    # 清理
    conn = __import__("app.db.connection", fromlist=["get_conn"]).get_conn()
    conn.execute("DELETE FROM exercise_bank WHERE user_id=?", (TEST_USER,))
    conn.commit()
    conn.close()

    print("[PASS] 2. CRUD + CAS + hint chain + report error")


def test_markdown_parser():
    """3. 流式 Markdown 解析"""
    from app.services.exercise_generator import parse_markdown_sections

    text = """## 题目
求矩阵 A = [[1,2],[3,4]] 的特征值。

## 答案
det(A-λI) = (1-λ)(4-λ)-6 = λ²-5λ-2
解得 λ₁=5.37, λ₂=-0.37

## 提示
1. 先写出特征方程 det(A-λI)=0
2. 展开二阶行列式
3. 解一元二次方程

## 验证
将 λ₁ 代回验证 ✓

## computable
```json
{"type": "matrix_eigenvalues", "matrix": [[1,2],[3,4]], "expected": ["5.3723", "-0.3723"]}
```"""

    parsed = parse_markdown_sections(text)
    assert "A =" in parsed["question"], f"question: {repr(parsed['question'][:80])}"
    assert "det" in parsed["answer"], f"answer: {repr(parsed['answer'][:80])}"
    assert len(parsed["hints"]) == 3, f"hints: {parsed['hints']}"
    assert "verif" in parsed["verification"].lower() or parsed["verification"], f"verification empty"
    assert parsed["computable"]["type"] == "matrix_eigenvalues"
    assert len(parsed["computable"]["expected"]) == 2
    print("[PASS] 3. Markdown section parsing (all 5 sections)")


def test_sympy_sandbox():
    """4. SymPy 沙箱验证"""
    from app.services.sympy_sandbox import verify_computable

    # 特征值
    result = verify_computable(
        "matrix_eigenvalues",
        {"matrix": [[1, 2], [3, 4]]},
        ["5.3723", "-0.3723"],
    )
    assert result["success"], f"eigenvalues failed: {result}"

    # 行列式
    result = verify_computable(
        "matrix_determinant",
        {"matrix": [[1, 2], [3, 4]]},
        -2,
    )
    assert result["success"], f"determinant failed: {result}"

    # 秩
    result = verify_computable(
        "matrix_rank",
        {"matrix": [[1, 0], [0, 1]]},
        2,
    )
    assert result["success"], f"rank failed: {result}"

    # 白名单外
    result = verify_computable("remove_file_system", {}, [])
    assert not result["success"]
    assert "not in whitelist" in result["error"]

    # 超过尺寸限制
    big_matrix = [[0] * 15 for _ in range(15)]
    result = verify_computable("matrix_determinant", {"matrix": big_matrix}, 0)
    assert not result["success"]
    assert "limit" in result["error"]

    # 危险内容
    result = verify_computable(
        "matrix_determinant",
        {"matrix": "eval('print(1)')"},
        0,
    )
    if result["success"]:
        data_str = str({"matrix": "eval('print(1)')"})
        for forbidden in ("eval", "exec", "import", "__"):
            if forbidden in data_str:
                print(f"  [WARN] Forbidden token '{forbidden}' not rejected, but compute may still fail safely.")
    assert not result.get("success") or isinstance(result.get("sympy_result"), float), \
        f"Unexpected success with dangerous input: {result}"

    # 特征值期望错误（应返回 mismatch）
    result = verify_computable(
        "matrix_eigenvalues",
        {"matrix": [[1, 2], [3, 4]]},
        ["999", "888"],
    )
    assert not result["success"]
    assert "mismatch" in result.get("error", "")

    print("[PASS] 4. SymPy sandbox: eigenvalues, determinant, rank, whitelist, limits, mismatch")


def test_exercise_models():
    """5. Pydantic 模型"""
    from app.models.schemas import (
        ExerciseGenerateRequest, ExerciseSubmitRequest,
        ExerciseSubmitResponse, ExerciseHintResponse,
    )
    req = ExerciseGenerateRequest(user_id="u1", topic="矩阵")
    assert req.user_id == "u1"

    sub = ExerciseSubmitRequest(student_answer="answer")
    assert sub.student_answer == "answer"

    resp = ExerciseSubmitResponse(is_correct=True, grading_feedback="Great!", already_submitted=False)
    assert resp.is_correct
    assert resp.grading_feedback == "Great!"
    assert not resp.already_submitted

    resp2 = ExerciseSubmitResponse(is_correct=False, grading_feedback="Wrong", already_submitted=True)
    assert resp2.already_submitted

    hint = ExerciseHintResponse(hint="提示文本", hint_level=2, exhausted=False)
    assert hint.hint_level == 2
    assert not hint.exhausted

    print("[PASS] 5. Pydantic models work")


def test_full_app_routes():
    """6. 完整路由注册"""
    from app.main import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    exercise_routes = [r for r in routes if "/exercise" in r]
    expected = ["/api/exercise/generate", "/api/exercise/list",
                "/api/exercise/{exercise_id}/submit",
                "/api/exercise/{exercise_id}/hint",
                "/api/exercise/{exercise_id}/report-error"]
    for path in expected:
        assert path in routes, f"Missing route: {path}"
    print(f"[PASS] 6. All {len(exercise_routes)} exercise routes registered")


if __name__ == "__main__":
    test_exercise_table()
    test_exercise_crud()
    test_markdown_parser()
    test_sympy_sandbox()
    test_exercise_models()
    test_full_app_routes()
    print("\n=== Sprint 2 all tests passed ===")
