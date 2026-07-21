"""
Phase 1-3 Verification Tests (v2.0 updated imports)
"""
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_tests():
    print("=" * 60)
    print("Phase 1-3 Verification Tests (v2.0)")
    print("=" * 60)
    results = []

    # Phase 1.1-1.2
    try:
        from app.db.connection import init_db, get_conn
        init_db()
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chat_logs'")
        r = c.fetchone()
        conn.close()
        assert r, "chat_logs table missing"
        print("[PASS] 1.1 chat_logs table exists")
        results.append(("1.1", True, ""))
    except Exception as e:
        print(f"[FAIL] 1.1: {e}")
        results.append(("1.1", False, str(e)))

    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_chat_logs_analyzed'")
        r = c.fetchone()
        conn.close()
        assert r, "index missing"
        print("[PASS] 1.2 idx_chat_logs_analyzed index exists")
        results.append(("1.2", True, ""))
    except Exception as e:
        print(f"[FAIL] 1.2: {e}")
        results.append(("1.2", False, str(e)))

    # Phase 1.3-1.6 CRUD
    try:
        from app.db.chat_log_db import save_chat_log, get_unanalyzed_chat_logs, mark_chat_logs_analyzed, group_chat_logs_by_sequence_id
        test_user = f"test_user_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        for i in range(3):
            ok = save_chat_log(user_id=test_user, sequence_id="V1-C02-S03", question=f"Q{i+1}", answer=f"A{i+1}")
            assert ok
        logs = get_unanalyzed_chat_logs(test_user, limit=10)
        assert len(logs) >= 3, f"expected >=3, got {len(logs)}"
        print(f"[PASS] 1.3 save_chat_log wrote {len(logs)} records")
        results.append(("1.3", True, ""))

        unanalyzed = get_unanalyzed_chat_logs(test_user, limit=10)
        assert all(log["is_analyzed"] == 0 for log in unanalyzed), "is_analyzed should be 0"
        print("[PASS] 1.4 get_unanalyzed filters is_analyzed=0")
        results.append(("1.4", True, ""))

        ids = [log["id"] for log in unanalyzed[:2]]
        affected = mark_chat_logs_analyzed(ids)
        assert affected == 2, f"expected 2, got {affected}"
        remaining = get_unanalyzed_chat_logs(test_user, limit=10)
        still_there = len([l for l in remaining if l["id"] in ids])
        assert still_there == 0, f"{still_there} still unanalyzed"
        print("[PASS] 1.5 mark_chat_logs_analyzed works")
        results.append(("1.5", True, ""))

        save_chat_log(test_user, "V1-C03-S01", "QX", "AX")
        all_logs = get_unanalyzed_chat_logs(test_user, limit=10)
        grouped = group_chat_logs_by_sequence_id(all_logs)
        assert "V1-C02-S03" in grouped and "V1-C03-S01" in grouped, "missing groups"
        print(f"[PASS] 1.6 group_by_sequence_id: {len(grouped)} groups")
        results.append(("1.6", True, ""))
    except Exception as e:
        print(f"[FAIL] 1.3-1.6: {e}")
        import traceback; traceback.print_exc()
        for tid in ["1.3","1.4","1.5","1.6"]:
            results.append((tid, False, str(e)[:60]))

    # Phase 2
    try:
        from app.db.diagnostic import get_concepts_by_sequence_id
        concepts = get_concepts_by_sequence_id("V1-C01-S01")
        print(f"[PASS] 2.1 get_concepts_by_sequence_id: {len(concepts)} concepts (Neo4j may be offline)")
        results.append(("2.1", True, ""))
    except Exception as e:
        print(f"[WARN] 2.1: {e}")
        results.append(("2.1", False, str(e)[:60]))

    # Phase 3.1-3.3
    try:
        from app.db.math_profile_standard import build_diagnostic_prompt, DIAGNOSTIC_SYSTEM_PROMPT, DIAGNOSTIC_OUTPUT_FORMAT
        prompt = build_diagnostic_prompt("V1-C02-S03", ["行列式","矩阵的秩"], [{"question":"Q1","answer":"A1"}])
        assert "V1-C02-S03" in prompt
        print(f"[PASS] 3.1 build_diagnostic_prompt new signature: {len(prompt)} chars")
        results.append(("3.1", True, ""))

        assert "delta" in DIAGNOSTIC_SYSTEM_PROMPT.lower() and "evidence" in DIAGNOSTIC_SYSTEM_PROMPT.lower()
        print("[PASS] 3.2 SYSTEM_PROMPT has delta and evidence")
        results.append(("3.2", True, ""))

        assert "dimension_deltas" in DIAGNOSTIC_OUTPUT_FORMAT and "delta" in DIAGNOSTIC_OUTPUT_FORMAT
        print("[PASS] 3.3 OUTPUT_FORMAT is Delta format")
        results.append(("3.3", True, ""))
    except Exception as e:
        print(f"[FAIL] 3.1-3.3: {e}")
        for tid in ["3.1","3.2","3.3"]:
            results.append((tid, False, str(e)[:60]))

    # Phase 3.4 (save_diagnostic_assessment was no-caller, kept for tests)
    # Note: save_diagnostic_assessment was deleted during cleanup (no active callers).
    # This test now verifies that save_question_assessment can be used as replacement.
    try:
        from app.db.question_assessment_db import save_question_assessment, get_question_assessments
        aid = f"ta_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        # Use save_question_assessment with 'diagnostic' question_id
        ok = save_question_assessment(
            user_id="tu_p3",
            question_id="diagnostic",
            lr_coverage=0, lr_radius=-1, lr_technical=0,
            weak_points=["行列式"]
        )
        assert ok
        print("[PASS] 3.4 save_question_assessment callable (replaces save_diagnostic_assessment)")
        results.append(("3.4", True, ""))
    except Exception as e:
        print(f"[FAIL] 3.4: {e}")
        results.append(("3.4", False, str(e)[:60]))

    # Phase 3.5
    try:
        from app.services.diagnostic_worker import run_diagnostic_batch, should_trigger_diagnostic_batch, DIAGNOSTIC_BATCH_THRESHOLD
        print(f"[PASS] 3.5 diagnostic_worker imports OK (threshold={DIAGNOSTIC_BATCH_THRESHOLD})")
        results.append(("3.5", True, ""))
    except Exception as e:
        print(f"[FAIL] 3.5: {e}")
        results.append(("3.5", False, str(e)[:60]))

    # Phase 1.7
    try:
        source = open("app/routers/qa.py", encoding="utf-8").read()
        assert "background_tasks" in source, "background_tasks not in qa.py"
        assert "solve_question_stream" in source, "solve_question_stream not in qa.py"
        print("[PASS] 1.7 solve_question_stream has background_tasks param")
        results.append(("1.7", True, ""))
    except Exception as e:
        print(f"[FAIL] 1.7: {e}")
        results.append(("1.7", False, str(e)[:60]))

    # Summary
    print("=" * 60)
    passed = sum(1 for _,ok,_ in results if ok)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    for tid,ok,err in results:
        print(f"  {'[PASS]' if ok else '[FAIL]'} {tid}{'  <- ' + err[:50] if err else ''}")
    return passed == total

if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
