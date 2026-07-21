"""
Phase 4 Verification Tests (v2.0 updated imports)
"""
import sys, os
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_tests():
    print("=" * 60)
    print("Phase 4 Verification Tests (v2.0)")
    print("=" * 60)
    results = []

    # ---- Backend API source files ----
    try:
        assert os.path.exists("app/routers/auth.py"), "auth.py missing"
        source = open("app/routers/auth.py", encoding="utf-8").read()
        assert "get_knowledge_stats" in source, "get_knowledge_stats not imported"
        assert "get_question_assessments" in source, "get_question_assessments not imported"
        print("[PASS] 4.1  auth.py has Phase 4 API imports")
        results.append(("4.1", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.1: {e}")
        results.append(("4.1", False, str(e)[:60]))

    # ---- Schemas ----
    try:
        from app.models.schemas import (
            KnowledgeStatsResponse, DiagnosticHistoryResponse,
            KnowledgeStatsItem, DiagnosticHistoryItem
        )
        assert hasattr(KnowledgeStatsResponse, "model_fields")
        assert hasattr(DiagnosticHistoryResponse, "model_fields")
        print("[PASS] 4.2  Phase 4 schemas exist")
        results.append(("4.2", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.2: {e}")
        results.append(("4.2", False, str(e)[:60]))

    # ---- get_question_assessments ----
    try:
        from app.db.connection import init_db
        from app.db.question_assessment_db import save_question_assessment, get_question_assessments
        init_db()
        aid = f"ta_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ok = save_question_assessment(
            user_id="test_phase4_user",
            question_id="diagnostic",
            lr_coverage=0, lr_radius=-1, lr_technical=0,
            weak_points=["行列式"]
        )
        assert ok, "save_question_assessment returned False"
        records = get_question_assessments("test_phase4_user", limit=10)
        assert len(records) >= 1, f"expected >=1, got {len(records)}"
        print(f"[PASS] 4.3  get_question_assessments: {len(records)} records")
        results.append(("4.3", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.3: {e}")
        results.append(("4.3", False, str(e)[:60]))

    # ---- get_knowledge_stats ----
    try:
        from app.db.knowledge_stats_db import update_knowledge_stats, get_knowledge_stats, reset_consecutive_turns
        topic = f"test_topic_{datetime.now().strftime('%H%M%S')}"
        result = update_knowledge_stats("test_phase4_user", topic)
        assert result["consecutive_turns"] == 1
        assert result["total_asks"] == 1
        result2 = update_knowledge_stats("test_phase4_user", topic)
        assert result2["consecutive_turns"] == 2
        assert result2["total_asks"] == 2
        stats = get_knowledge_stats("test_phase4_user")
        stat = next((s for s in stats if s["topic"] == topic), None)
        assert stat is not None, f"topic {topic} not found"
        assert stat["total_asks"] == 2, f"expected 2, got {stat['total_asks']}"
        print(f"[PASS] 4.4  get_knowledge_stats: {len(stats)} topics tracked")
        results.append(("4.4", True, ""))
        reset_consecutive_turns("test_phase4_user", topic)
    except Exception as e:
        print(f"[FAIL] 4.4: {e}")
        results.append(("4.4", False, str(e)[:60]))

    # ---- Multi-delta save via save_question_assessment ----
    try:
        from app.db.question_assessment_db import save_question_assessment, get_question_assessments
        aid2 = f"ta2_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        ok = save_question_assessment(
            user_id="test_phase4_user2",
            question_id="diagnostic",
            lr_coverage=1, lr_radius=0, lr_technical=0,
            mt_coverage=0, mt_radius=-1, mt_technical=0,
            weak_points=["行列式展开", "矩阵的秩"]
        )
        assert ok
        records = get_question_assessments("test_phase4_user2", limit=5)
        r = records[0]
        assert r["weak_concepts"] == ["行列式展开", "矩阵的秩"]
        print(f"[PASS] 4.5  save_question_assessment multi-delta")
        results.append(("4.5", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.5: {e}")
        results.append(("4.5", False, str(e)[:60]))

    # ---- Frontend components exist ----
    try:
        component_files = [
            "frontend/src/components/ProfilePanel.tsx",
            "frontend/src/components/RadarChart.tsx",
            "frontend/src/components/LearningTrajectory.tsx",
            "frontend/src/components/WeakPointGraph.tsx",
            "frontend/src/components/BasicInfoEditor.tsx",
            "frontend/src/components/AuthModal.tsx",
        ]
        for f in component_files:
            assert os.path.exists(f), f"missing: {f}"
        print(f"[PASS] 4.6  All {len(component_files)} component files exist")
        results.append(("4.6", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.6: {e}")
        results.append(("4.6", False, str(e)[:60]))

    # ---- Frontend API functions ----
    try:
        api_ts = "frontend/src/services/api.ts"
        content = open(api_ts, encoding="utf-8").read()
        required = ["getMathProfile", "updateMathProfile", "getKnowledgeStats", "getDiagnosticHistory"]
        for fn in required:
            assert fn in content, f"missing function: {fn}"
        print(f"[PASS] 4.7  All Phase 4 API functions in api.ts")
        results.append(("4.7", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.7: {e}")
        results.append(("4.7", False, str(e)[:60]))

    # ---- Recharts dependency ----
    try:
        content = open("frontend/package.json", encoding="utf-8").read()
        assert "recharts" in content, "recharts not in package.json"
        print("[PASS] 4.8  recharts in package.json")
        results.append(("4.8", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.8: {e}")
        results.append(("4.8", False, str(e)[:60]))

    # ---- App.tsx cleanup + new hooks ----
    try:
        app_content = open("frontend/src/App.tsx", encoding="utf-8").read()
        assert "useAuth" in app_content, "useAuth not imported"
        assert "useTextbookPreference" in app_content, "useTextbookPreference not imported"
        assert "AuthModal" in app_content, "AuthModal not imported"
        # Check hooks exist
        assert os.path.exists("frontend/src/hooks/useAuth.ts"), "useAuth.ts missing"
        assert os.path.exists("frontend/src/hooks/useTextbookPreference.ts"), "useTextbookPreference.ts missing"
        print("[PASS] 4.9  App.tsx refactored with hooks + AuthModal")
        results.append(("4.9", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.9: {e}")
        results.append(("4.9", False, str(e)[:60]))

    # ---- DB module split verification ----
    try:
        modules = [
            "connection", "auth_db", "user_profile_db", "math_profile_db",
            "textbook_db", "textbook_section_db", "chat_history_db", "chat_log_db",
            "knowledge_stats_db", "question_assessment_db", "whitelist_db"
        ]
        for mod in modules:
            __import__(f"app.db.{mod}")
        # Verify old sqlite.py is gone
        assert not os.path.exists("app/db/sqlite.py"), "old sqlite.py still exists!"
        assert not os.path.exists("app/db/vector.py"), "old vector.py still exists!"
        assert not os.path.exists("app/services/rag.py"), "old rag.py still exists!"
        assert not os.path.exists("app/services/embedding.py"), "old embedding.py still exists!"
        print(f"[PASS] 4.10  DB split: {len(modules)} modules, old files deleted")
        results.append(("4.10", True, ""))
    except Exception as e:
        print(f"[FAIL] 4.10: {e}")
        results.append(("4.10", False, str(e)[:60]))

    # Summary
    print("=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    for tid, ok, err in results:
        print(f"  {'[PASS]' if ok else '[FAIL]'} {tid}{'  <- ' + err[:50] if err else ''}")
    return passed == total

if __name__ == "__main__":
    sys.exit(0 if run_tests() else 1)
