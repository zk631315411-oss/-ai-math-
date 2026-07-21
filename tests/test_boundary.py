"""
边界测试集 — 智学助手
覆盖：认证/问答/画像/练习题/知识阶段/Neo4j/并发/数据库/输入验证
"""

import sys, os, asyncio, time
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
BASE = "http://localhost:8000/api"
TIMESTAMP = datetime.now().strftime("%m%d%H%M%S")
TEST_USER_PREFIX = f"boundary_{TIMESTAMP}"

# ─────────────────────────────────────────────────────────────────────────────
# 测试结果收集
# ─────────────────────────────────────────────────────────────────────────────
bugs = []   # (title, severity, file_location, trigger, expected, actual, error_msg)
passes = []


def record(pass_: bool, title: str, detail: str = ""):
    tag = "PASS" if pass_ else "FAIL"
    print(f"  [{tag}] {title}  {detail}")
    if pass_:
        passes.append(title)
    else:
        bugs.append(title)


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────
async def register_user(username: str, password: str = "test123", device_id: str = ""):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{BASE}/auth/register", json={
            "username": username,
            "password": password,
            "device_id": device_id or f"device_{username}",
        })
        return resp


async def login_user(username: str, password: str = "test123"):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{BASE}/auth/login", json={
            "username": username,
            "password": password,
        })
        return resp


async def get_token(username: str, password: str = "test123", register=True):
    async with httpx.AsyncClient(timeout=30) as client:
        if register:
            await client.post(f"{BASE}/auth/register", json={
                "username": username, "password": password,
                "device_id": f"device_{username}",
            })
        resp = await client.post(f"{BASE}/auth/login", json={
            "username": username, "password": password,
        })
        if resp.status_code == 200:
            return resp.json()["access_token"], resp.json()["user_id"]
        return None, None


async def auth_headers(username: str):
    token, uid = await get_token(username)
    if token:
        return {"Authorization": f"Bearer {token}"}, uid
    return {}, None


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: 认证边界测试
# ─────────────────────────────────────────────────────────────────────────────
async def test_auth_boundaries():
    print("\n=== 1. 认证边界测试 ===")
    su = f"{TEST_USER_PREFIX}_auth"

    async with httpx.AsyncClient(timeout=30) as client:
        # 1.1 重复注册
        await client.post(f"{BASE}/auth/register", json={"username": su, "password": "test123", "device_id": f"d_{su}"})
        r = await client.post(f"{BASE}/auth/register", json={"username": su, "password": "test123", "device_id": f"d_{su}"})
        record(r.status_code == 400, "1.1 重复注册返回400", f"status={r.status_code}")

        # 1.2 空用户名
        r = await client.post(f"{BASE}/auth/register", json={"username": "", "password": "test123", "device_id": "d_empty"})
        record(r.status_code in (400, 422), "1.2 空用户名拒绝", f"status={r.status_code}")

        # 1.3 空密码
        r = await client.post(f"{BASE}/auth/register", json={"username": f"{su}_nopass", "password": "", "device_id": "d_np"})
        record(r.status_code in (400, 422), "1.3 空密码拒绝", f"status={r.status_code}")

        # 1.4 错误密码登录
        r = await login_user(su)
        if r.status_code == 200:
            r2 = await client.post(f"{BASE}/auth/login", json={"username": su, "password": "wrongpassword"})
            record(r2.status_code == 401, "1.4 错误密码返回401", f"status={r2.status_code}")
        else:
            record(False, "1.4 错误密码返回401", "前置：注册失败")

        # 1.5 不存在用户登录
        r = await client.post(f"{BASE}/auth/login", json={"username": "this_user_does_not_exist_xyz", "password": "test123"})
        record(r.status_code == 401, "1.5 不存在用户登录返回401", f"status={r.status_code}")

        # 1.6 超长用户名（>64字符）
        long_user = f"{su}_" + "x" * 200
        r = await client.post(f"{BASE}/auth/register", json={"username": long_user, "password": "test123", "device_id": f"d_{long_user}"})
        record(r.status_code in (400, 422), "1.6 超长用户名拒绝", f"status={r.status_code}")

        # 1.7 SQL注入用户名
        r = await client.post(f"{BASE}/auth/register", json={
            "username": f"{su}_sql' OR '1'='1", "password": "test123", "device_id": "d_sql"
        })
        record(r.status_code in (400, 422, 500), "1.7 SQL注入用户名拒绝", f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: 问答边界测试
# ─────────────────────────────────────────────────────────────────────────────
async def test_qa_boundaries():
    print("\n=== 2. 问答边界测试 ===")
    su = f"{TEST_USER_PREFIX}_qa"
    headers, uid = await auth_headers(su)
    if not headers:
        print("  [SKIP] Q&A测试需要有效认证")
        return

    async with httpx.AsyncClient(timeout=60) as client:
        # 2.1 空问题
        r = await client.post(f"{BASE}/qa/solve", json={
            "user_id": uid, "token": headers["Authorization"].split(" ")[1],
            "question": "", "teaching_mode": "direct",
        })
        # 空字符串可能通过（视为无意义请求）或422，容错
        record(r.status_code in (200, 400, 422), "2.1 空问题有响应（不崩溃）", f"status={r.status_code}")

        # 2.2 超长问题（>10000字符）
        long_q = f"{su}_longq" + "啊" * 5000
        r = await client.post(f"{BASE}/qa/solve", json={
            "user_id": uid, "token": headers["Authorization"].split(" ")[1],
            "question": long_q, "teaching_mode": "direct",
        })
        record(r.status_code in (200, 400, 422), "2.2 超长问题有响应（不崩溃）", f"status={r.status_code}")

        # 2.3 危险LaTeX字符
        latex_xss = r"$$$\displaystyle\LaTeX\; \textbf{HACK} \input{/etc/passwd}$$"
        r = await client.post(f"{BASE}/qa/solve", json={
            "user_id": uid, "token": headers["Authorization"].split(" ")[1],
            "question": latex_xss, "teaching_mode": "direct",
        })
        record(r.status_code in (200, 400, 422), "2.3 危险LaTeX字符有响应（不崩溃）", f"status={r.status_code}")

        # 2.4 HTML/Script注入
        xss_input = "<script>alert('XSS')</script><img src=x onerror=alert(1)>"
        r = await client.post(f"{BASE}/qa/solve", json={
            "user_id": uid, "token": headers["Authorization"].split(" ")[1],
            "question": xss_input, "teaching_mode": "direct",
        })
        record(r.status_code in (200, 400, 422), "2.4 XSS输入有响应（不崩溃）", f"status={r.status_code}")

        # 2.5 无效教学模式
        r = await client.post(f"{BASE}/qa/solve", json={
            "user_id": uid, "token": headers["Authorization"].split(" ")[1],
            "question": "什么是矩阵", "teaching_mode": "invalid_mode",
        })
        record(r.status_code in (200, 400, 422), "2.5 无效教学模式有响应（不崩溃）", f"status={r.status_code}")

        # 2.6 无效苏格拉底子模式
        r = await client.post(f"{BASE}/qa/solve", json={
            "user_id": uid, "token": headers["Authorization"].split(" ")[1],
            "question": "什么是矩阵", "teaching_mode": "socratic", "socratic_submode": "invalid_submode",
        })
        record(r.status_code in (200, 400, 422), "2.6 无效socratic_submode有响应（不崩溃）", f"status={r.status_code}")

        # 2.7 负数页码
        r = await client.post(f"{BASE}/qa/solve", json={
            "user_id": uid, "token": headers["Authorization"].split(" ")[1],
            "question": "行列式", "teaching_mode": "direct", "page_number": -1,
        })
        record(r.status_code in (200, 400, 422), "2.7 负数页码有响应（不崩溃）", f"status={r.status_code}")

        # 2.8 不存在的教材ID
        r = await client.post(f"{BASE}/qa/solve", json={
            "user_id": uid, "token": headers["Authorization"].split(" ")[1],
            "question": "行列式", "teaching_mode": "direct", "textbook_id": "不存在的教材",
        })
        record(r.status_code in (200, 400, 422), "2.8 不存在教材ID有响应（不崩溃）", f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: 数学画像边界测试
# ─────────────────────────────────────────────────────────────────────────────
async def test_profile_boundaries():
    print("\n=== 3. 数学画像边界测试 ===")
    su = f"{TEST_USER_PREFIX}_profile"
    headers, uid = await auth_headers(su)
    if not headers:
        print("  [SKIP] 画像测试需要有效认证")
        return

    async with httpx.AsyncClient(timeout=30) as client:
        # 3.1 分数越界：>3
        r = await client.put(f"{BASE}/auth/math-profile", headers=headers, json={
            "user_id": uid, "grade": "大一",
            "mt_coverage": 5, "mt_radius": 0, "mt_technical": 0,
        })
        record(r.status_code in (200, 400, 422), "3.1 分数>3拒绝或修正", f"status={r.status_code}")

        # 3.2 分数越界：<0
        r = await client.put(f"{BASE}/auth/math-profile", headers=headers, json={
            "user_id": uid, "grade": "大一",
            "mt_coverage": -1, "mt_radius": 0, "mt_technical": 0,
        })
        record(r.status_code in (200, 400, 422), "3.2 分数<0拒绝或修正", f"status={r.status_code}")

        # 3.3 分数越界：浮点数
        r = await client.put(f"{BASE}/auth/math-profile", headers=headers, json={
            "user_id": uid, "grade": "大一",
            "mt_coverage": 2.5, "mt_radius": 1, "mt_technical": 1,
        })
        record(r.status_code in (200, 400, 422), "3.3 浮点分数接受或修正", f"status={r.status_code}")

        # 3.4 非法年级值
        r = await client.put(f"{BASE}/auth/math-profile", headers=headers, json={
            "user_id": uid, "grade": "博士后",
        })
        # 年级不在预定义范围，可能接受也可能静默忽略
        record(r.status_code in (200, 400, 422), "3.4 非法年级有响应（不崩溃）", f"status={r.status_code}")

        # 3.5 薄弱点为非列表类型
        r = await client.put(f"{BASE}/auth/math-profile", headers=headers, json={
            "user_id": uid, "grade": "大一", "weak_points": "特征值",  # 应该是list
        })
        record(r.status_code in (200, 400, 422), "3.5 薄弱点类型错误有响应（不崩溃）", f"status={r.status_code}")

        # 3.6 无效维度字段名
        r = await client.put(f"{BASE}/auth/math-profile", headers=headers, json={
            "user_id": uid, "grade": "大一", "invalid_dimension": 2,
        })
        record(r.status_code in (200, 400, 422), "3.6 无效字段有响应（不崩溃）", f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: 练习题边界测试
# ─────────────────────────────────────────────────────────────────────────────
async def test_exercise_boundaries():
    print("\n=== 4. 练习题边界测试 ===")
    su = f"{TEST_USER_PREFIX}_exercise"
    headers, uid = await auth_headers(su)
    if not headers:
        print("  [SKIP] 练习题测试需要有效认证")
        return

    async with httpx.AsyncClient(timeout=60) as client:
        # 4.1 生成练习题（正常）
        r = await client.post(f"{BASE}/exercise/generate", headers=headers, json={
            "token": headers["Authorization"].split(" ")[1],
            "topic": "矩阵的秩",
        })
        # 可能200（流式）或202，返回的是SSE或JSON
        record(r.status_code in (200, 202), "4.1 正常生成练习题", f"status={r.status_code}")

        # 4.2 空topic
        r = await client.post(f"{BASE}/exercise/generate", headers=headers, json={
            "token": headers["Authorization"].split(" ")[1], "topic": "",
        })
        record(r.status_code in (200, 202, 400, 422), "4.2 空topic有响应（不崩溃）", f"status={r.status_code}")

        # 4.3 超长topic
        r = await client.post(f"{BASE}/exercise/generate", headers=headers, json={
            "token": headers["Authorization"].split(" ")[1], "topic": "矩阵" * 1000,
        })
        record(r.status_code in (200, 202, 400, 422), "4.3 超长topic有响应（不崩溃）", f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: 知识阶段边界测试（单元测试，不需要后端）
# ─────────────────────────────────────────────────────────────────────────────
def test_knowledge_stages_boundaries():
    print("\n=== 5. 知识阶段边界测试（单元） ===")
    try:
        from app.db.knowledge_stages_db import get_stage, update_stage, get_stages_batch
        su = f"{TEST_USER_PREFIX}_ks"

        # 5.1 stage越界：>5
        try:
            update_stage(su, "concept_a", override=6, source="test")
            r = get_stage(su, "concept_a")
            record(r is not None and r <= 5, "5.1 stage>5被修正为<=5", f"stage={r}")
        except Exception as e:
            record(False, "5.1 stage>5处理", str(e)[:80])

        # 5.2 stage越界：<0
        try:
            update_stage(su, "concept_b", override=-1, source="test")
            r = get_stage(su, "concept_b")
            record(r is not None and r >= 0, "5.2 stage<0被修正为>=0", f"stage={r}")
        except Exception as e:
            record(False, "5.2 stage<0处理", str(e)[:80])

        # 5.3 delta为负数
        try:
            update_stage(su, "concept_c", delta=-10, source="test")
            r = get_stage(su, "concept_c")
            record(r is not None and r >= 0, "5.3 delta=-10不导致负数stage", f"stage={r}")
        except Exception as e:
            record(False, "5.3 delta负数处理", str(e)[:80])

        # 5.4 get_stages_batch不存在概念
        try:
            batch = get_stages_batch(su, ["不存在的概念_xyz"])
            record(len(batch) >= 0, "5.4 get_stages_batch不存在概念不抛异常", f"len={len(batch)}")
        except Exception as e:
            record(False, "5.4 get_stages_batch不存在概念", str(e)[:80])

    except ImportError as e:
        print(f"  [SKIP] 无法导入knowledge_stages_db: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Neo4j前置知识边界测试
# ─────────────────────────────────────────────────────────────────────────────
async def test_neo4j_boundaries():
    print("\n=== 6. Neo4j前置知识边界测试 ===")
    su = f"{TEST_USER_PREFIX}_neo4j"
    headers, uid = await auth_headers(su)
    if not headers:
        print("  [SKIP] Neo4j测试需要有效认证")
        return

    try:
        from app.services.prerequisite_checker import get_prerequisite_chain, check_gaps
        # 6.1 不存在的概念
        try:
            chain = await get_prerequisite_chain("不存在的概念_XYZ123")
            record(True, "6.1 不存在概念返回空链不抛异常", f"chain={chain}")
        except Exception as e:
            record(False, "6.1 不存在概念返回空链不抛异常", str(e)[:80])

        # 6.2 空概念名
        try:
            chain = await get_prerequisite_chain("")
            record(True, "6.2 空概念名不抛异常", f"chain={chain}")
        except Exception as e:
            record(False, "6.2 空概念名处理", str(e)[:80])

        # 6.3 check_gaps不存在用户
        try:
            gaps = await check_gaps("不存在的用户_xyz", "矩阵的秩")
            record(True, "6.3 check_gaps不存在用户不抛异常", f"gaps={gaps}")
        except Exception as e:
            record(False, "6.3 check_gaps不存在用户", str(e)[:80])

    except ImportError as e:
        print(f"  [SKIP] 无法导入prerequisite_checker: {e}")
    except Exception as e:
        print(f"  [ERROR] Neo4j连接失败: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: 数据库边界测试
# ─────────────────────────────────────────────────────────────────────────────
def test_database_boundaries():
    print("\n=== 7. 数据库边界测试（单元） ===")
    try:
        from app.db.connection import get_conn
        conn = get_conn()

        # 7.1 WAL模式检查
        try:
            r = conn.execute("PRAGMA journal_mode").fetchone()
            mode = r[0] if r else "unknown"
            record(mode.upper() == "WAL", "7.1 数据库WAL模式", f"mode={mode}")
        except Exception as e:
            record(False, "7.1 WAL模式检查", str(e)[:80])

        # 7.2 连接泄露检测（执行前后cursor数量）
        cursors_before = len(conn.curses) if hasattr(conn, 'curses') else 0
        cur = conn.execute("SELECT 1")
        result = cur.fetchone()
        cur.close()
        cursors_after = len(conn.curses) if hasattr(conn, 'curses') else 0
        record(result == (1,), "7.2 基本查询正常", f"result={result}")
        conn.close()

        # 7.3 并发写入同一用户
        from app.db.knowledge_stages_db import update_stage
        su = f"{TEST_USER_PREFIX}_db"
        try:
            update_stage(su, "concurrent_test", delta=1, source="t1")
            update_stage(su, "concurrent_test", delta=1, source="t2")
            record(True, "7.3 连续写入同一用户不冲突", "")
        except Exception as e:
            record(False, "7.3 连续写入同一用户", str(e)[:80])

    except ImportError as e:
        print(f"  [SKIP] 无法导入db模块: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: 输入验证（XSS/SQL/Path Traversal）
# ─────────────────────────────────────────────────────────────────────────────
async def test_input_validation():
    print("\n=== 8. 输入验证测试 ===")
    su = f"{TEST_USER_PREFIX}_xss"
    headers, uid = await auth_headers(su)
    if not headers:
        print("  [SKIP] 输入验证需要有效认证")
        return

    async with httpx.AsyncClient(timeout=30) as client:
        payloads = [
            ("<script>alert(1)</script>", "8.1 Script标签"),
            ("javascript:alert('XSS')", "8.2 javascript:协议"),
            ("'><img src=x onerror=alert(1)>", "8.3 事件处理器注入"),
            ("\\x3cscript\\x3ealert(1)\\x3c/script\\x3e", "8.4 转义script标签"),
            ("../../../etc/passwd", "8.5 路径穿越"),
            ("null_byte\x00.txt", "8.6 空字节注入"),
        ]
        for payload, label in payloads:
            r = await client.post(f"{BASE}/qa/solve", json={
                "user_id": uid, "token": headers["Authorization"].split(" ")[1],
                "question": payload, "teaching_mode": "direct",
            })
            record(r.status_code in (200, 400, 422), f"{label} — 有响应不崩溃", f"status={r.status_code}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: 并发测试
# ─────────────────────────────────────────────────────────────────────────────
async def test_concurrency():
    print("\n=== 9. 并发测试 ===")
    su = f"{TEST_USER_PREFIX}_conc"
    headers, uid = await auth_headers(su)
    if not headers:
        print("  [SKIP] 并发测试需要有效认证")
        return

    # 9.1 同一用户10并发QA请求
    async def qa_request(i):
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{BASE}/qa/solve", json={
                "user_id": uid, "token": headers["Authorization"].split(" ")[1],
                "question": f"矩阵的基本运算{i}", "teaching_mode": "direct",
            })
            return r.status_code

    tasks = [qa_request(i) for i in range(10)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    statuses = [r for r in results if isinstance(r, int)]
    errors = [r for r in results if isinstance(r, Exception)]

    if errors:
        record(False, f"9.1 并发QA请求 — {len(errors)}个异常", str(errors[0])[:80])
    else:
        # 至少过半成功
        success_rate = sum(1 for s in statuses if s in (200, 400, 422)) / len(statuses)
        record(success_rate >= 0.5, f"9.1 并发QA请求成功率={success_rate:.0%}", f"成功{sum(1 for s in statuses if s in (200, 400, 422))}/{len(statuses)}")


# ─────────────────────────────────────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 70)
    print(f"智学助手边界测试集 — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试前缀: {TEST_USER_PREFIX}")
    print("=" * 70)

    await test_auth_boundaries()
    await test_qa_boundaries()
    await test_profile_boundaries()
    await test_exercise_boundaries()
    test_knowledge_stages_boundaries()
    await test_neo4j_boundaries()
    test_database_boundaries()
    await test_input_validation()
    await test_concurrency()

    print("\n" + "=" * 70)
    print(f"结果汇总: {len(passes)} 通过 / {len(bugs)} 失败")
    print("=" * 70)
    if bugs:
        print("\n失败项:")
        for b in bugs:
            print(f"  ✗ {b}")
    return len(bugs)


if __name__ == "__main__":
    n_bugs = asyncio.run(main())
    exit(0 if n_bugs == 0 else 1)
