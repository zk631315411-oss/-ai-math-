"""Phase 2 端到端 API 测试 — 模拟真实用户流程。"""
import httpx
import json
import asyncio

BASE = "http://localhost:8000/api"


async def main():
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        # ============ 1. 用户注册 ============
        device_id = "e2e-test-device-phase2"
        resp = await client.post(f"{BASE}/auth/register", json={
            "username": f"phase2_tester",
            "password": "test123",
            "device_id": device_id,
        })
        if resp.status_code == 400:
            resp = await client.post(f"{BASE}/auth/login", json={
                "username": "phase2_tester",
                "password": "test123",
            })
        assert resp.status_code == 200, f"Auth failed: {resp.text}"
        token = resp.json()["access_token"]
        user_id = resp.json()["user_id"]
        results.append(("1. Auth (register/login)", True))

        headers = {"Authorization": f"Bearer {token}"}

        # ============ 2. 苏格拉底子模式 via QA ============
        for submode, check in [("unclassified", ""), ("preview", ""), ("exam_review", ""), ("connected_review", "")]:
            # SSE 流式请求
            async with client.stream("POST", f"{BASE}/qa/solve-stream", json={
                "user_id": user_id,
                "token": token,
                "question": "什么是矩阵的秩？" if submode == "unclassified" else f"测试{submode}模式",
                "teaching_mode": "socratic",
                "socratic_submode": submode,
                "textbook_id": "gaodai_shang",
                "page_number": 30,
            }) as response:
                assert response.status_code == 200, f"QA {submode} failed: {response.status_code}"
                stages = []
                content = ""
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line[6:])
                        if "stage" in data:
                            stages.append(data["stage"])
                        if "content" in data:
                            content += data["content"]
        results.append((f"2. QA socratic_submode={submode}", len(content) > 0))

        # ============ 3. 动态 Prompt 引擎 ============
        async with client.stream("POST", f"{BASE}/qa/solve-stream", json={
            "user_id": user_id,
            "token": token,
            "question": "行列式和特征值有什么关系？",
            "teaching_mode": "socratic",
            "socratic_submode": "connected_review",
            "textbook_id": "gaodai_shang",
            "page_number": 35,
        }) as response:
            stages = []
            content = ""
            thinking = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if "stage" in data: stages.append(data["stage"])
                        if "content" in data: content += data["content"]
                        if "thinking" in data: thinking += data.get("text", "")
                    except Exception:
                        pass
        results.append(("3. Dynamic Prompt (stages)", len(stages) >= 2))
        results.append(("3b. Dynamic Prompt (response)", len(content) > 50))

        # ============ 4. 智能出题 ============
        async with client.stream("POST", f"{BASE}/exercise/generate", json={
            "user_id": user_id,
            "token": token,
            "topic": "矩阵的秩",
        }) as response:
            assert response.status_code == 200, f"Exercise generate failed: {response.status_code}"
            full = ""
            exercise_id = ""
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                        if "content" in data: full += data["content"]
                        if "done" in data: exercise_id = data.get("exercise_id", "")
                    except Exception:
                        pass
        results.append(("4. Exercise generate (streaming)", len(full) > 50))
        results.append(("4b. Exercise generate (saved)", bool(exercise_id)))

        # ============ 5. 提示链 ============
        hint_levels = []
        for _ in range(4):  # 请求 4 次，第 4 次应该 exhausted
            resp = await client.post(f"{BASE}/exercise/{exercise_id}/hint")
            data = resp.json()
            hint_levels.append(data["hint_level"])
        results.append(("5. Hint chain progression", hint_levels == [1, 2, 3, 3]))

        # ============ 6. 提交答案 (CAS + async error analysis) ============
        resp = await client.post(f"{BASE}/exercise/{exercise_id}/submit", json={
            "student_answer": "错误答案，秩应该是 1"
        })
        data = resp.json()
        results.append(("6. Submit grading", "is_correct" in data and "grading_feedback" in data))

        # CAS: resubmit should return already_submitted
        resp2 = await client.post(f"{BASE}/exercise/{exercise_id}/submit", json={
            "student_answer": "第二次提交"
        })
        data2 = resp2.json()
        results.append(("6b. CAS duplicate submit", data2.get("already_submitted", False)))

        # ============ 7. 题目纠错 ============
        resp = await client.post(f"{BASE}/exercise/{exercise_id}/report-error")
        results.append(("7. Report error", resp.status_code == 200))

        # ============ 8. 画像洞察 ============
        resp = await client.get(f"{BASE}/auth/insight", headers=headers)
        assert resp.status_code == 200, f"Insight failed: {resp.text}"
        insight = resp.json()["insight"]
        results.append(("8. Insight generated", "overall_assessment" in insight))
        results.append(("8b. Insight structure", all(k in insight for k in ["strengths", "weaknesses", "learning_trend", "recommended_focus", "motivation_message"])))

        # ============ 9. 缓存 ============
        resp2 = await client.get(f"{BASE}/auth/insight", headers=headers)
        results.append(("9. Insight cached", resp2.json().get("cached", False)))

        # ============ 10. 画像数据 ============
        resp = await client.get(f"{BASE}/auth/math-profile", headers=headers)
        assert resp.status_code == 200
        profile = resp.json()
        results.append(("10. Math profile", "dimensions" in profile and "overall_average" in profile))

        resp = await client.get(f"{BASE}/auth/knowledge-stats", headers=headers)
        results.append(("10b. Knowledge stats", resp.status_code == 200))

        resp = await client.get(f"{BASE}/auth/diagnostic-history", headers=headers)
        results.append(("10c. Diagnostic history", resp.status_code == 200))

        # ============ 11. 题目纠错 ============
        resp = await client.get(f"{BASE}/exercise/list", params={"user_id": user_id, "limit": 5})
        ex_list = resp.json()["exercises"]
        results.append(("11. Exercise list", len(ex_list) >= 1))

        # ============ 12. 强制重新生成洞察 ============
        resp = await client.post(f"{BASE}/auth/insight/regenerate", headers=headers)
        results.append(("12. Insight regenerate", resp.status_code == 200))

    # Print results
    print()
    for label, ok in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

    passed = sum(1 for _, ok in results if ok)
    print(f"\n=== {passed}/{len(results)} E2E tests passed ===")
    if passed == len(results):
        print("All E2E tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
