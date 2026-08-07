"""SymPy 沙箱：子进程隔离执行 + 操作白名单 + 类型专用适配器。

核心原则：LLM 出的代码一行都不执行。LLM 只输出结构化 computable 数据，
计算逻辑 100% 由后端写死。适配器在子进程内完成 SymPy→纯 Python 转换，
跨进程边界只传 dict/list/float，不传 SymPy 对象（避免 pickle 崩溃）。
"""

import multiprocessing as mp


# 每个操作类型的 SymPy 调用 + 尺寸限制
WHITELIST = {
    "matrix_eigenvalues": 10,   # max size
    "matrix_determinant": 10,
    "matrix_inverse": 5,
    "matrix_rank": 10,
    "system_solve": 5,          # max unknowns
    "polynomial_roots": 5,      # max degree
    "polynomial_factor": 10,
}


def _validate_size(comp_type: str, data: dict):
    max_size = WHITELIST.get(comp_type, 0)
    if max_size == 0:
        return False

    if comp_type.startswith("matrix_"):
        m = data.get("matrix", [])
        if not isinstance(m, list) or len(m) > max_size:
            return False
        for row in m:
            if not isinstance(row, list) or len(row) > max_size:
                return False

    if comp_type in ("system_solve", "polynomial_roots", "polynomial_factor"):
        default_degree = len(data.get("matrix", [])) if comp_type == "system_solve" else 0
        if data.get("degree", default_degree) > max_size:
            return False

    return True


def _run_sympy_worker(comp_type: str, data: dict):
    """在子进程中执行，返回纯 Python 类型。"""
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, -1))  # 512MB
    except (ImportError, AttributeError, ValueError):
        pass  # Windows 不支持 RLIMIT_AS

    import sympy

    if comp_type == "matrix_eigenvalues":
        M = sympy.Matrix(data["matrix"])
        result = M.eigenvals()
        values = []
        for ev, mult in result.items():
            numeric = round(float(ev.evalf()), 6)
            for _ in range(mult):
                values.append(numeric)
        normalized = sorted(values)

    elif comp_type == "matrix_determinant":
        M = sympy.Matrix(data["matrix"])
        result = M.det()
        normalized = round(float(result.evalf()), 6)

    elif comp_type == "matrix_inverse":
        M = sympy.Matrix(data["matrix"])
        inv = M.inv()
        normalized = [[round(float(x.evalf()), 6) for x in row] for row in inv.tolist()]

    elif comp_type == "matrix_rank":
        M = sympy.Matrix(data["matrix"])
        result = M.rank()
        normalized = int(result)

    elif comp_type == "system_solve":
        A = sympy.Matrix(data["matrix"])
        b = sympy.Matrix(data.get("vector", [[0]]))
        solution = A.gauss_jordan_solve(b)[0]
        normalized = [[round(float(x.evalf()), 6) for x in row] for row in solution.tolist()]

    elif comp_type == "polynomial_roots":
        x = sympy.Symbol("x")
        eq = sympy.sympify(data["expression"])
        roots = sympy.solve(eq, x)
        normalized = sorted([round(float(r.evalf()), 6) for r in roots])

    elif comp_type == "polynomial_factor":
        x = sympy.Symbol("x")
        eq = sympy.sympify(data["expression"])
        factored = sympy.factor(eq)
        normalized = str(factored)

    else:
        return {"success": False, "error": f"Unknown type: {comp_type}"}

    return {"success": True, "data": normalized}


def _sympy_process_entry(conn, comp_type: str, data: dict) -> None:
    try:
        conn.send(_run_sympy_worker(comp_type, data))
    except Exception as exc:
        conn.send({"success": False, "error": str(exc)})
    finally:
        conn.close()


def verify_computable(comp_type: str, data: dict, expected) -> dict:
    """
    安全入口：输入校验 → 子进程执行 → 比对。

    expected 是 LLM 声称的答案（纯 Python 类型）。
    """
    if comp_type not in WHITELIST:
        return {"success": False, "error": f"Type '{comp_type}' not in whitelist"}

    if not _validate_size(comp_type, data):
        return {"success": False, "error": "Size limit exceeded"}

    # 安全校验 LLM 数据中不含危险内容
    raw = str(data)
    for forbidden in ("eval", "exec", "import", "__", "open(", "os."):
        if forbidden in raw:
            return {"success": False, "error": f"Forbidden token: {forbidden}"}

    parent_conn, child_conn = mp.get_context("spawn").Pipe(duplex=False)
    process = mp.get_context("spawn").Process(
        target=_sympy_process_entry, args=(child_conn, comp_type, data), daemon=True,
    )
    process.start()
    child_conn.close()
    try:
        if not parent_conn.poll(10):
            process.terminate()
            process.join(timeout=1)
            return {"success": False, "error": "Timeout (10s)"}
        result = parent_conn.recv()
    except (EOFError, OSError) as exc:
        return {"success": False, "error": str(exc)}
    finally:
        parent_conn.close()
        if process.is_alive():
            process.terminate()
        process.join(timeout=1)

    if not result.get("success"):
        return result

    sympy_data = result["data"]

    # 比对
    if comp_type in ("matrix_eigenvalues", "polynomial_roots"):
        if not isinstance(expected, list):
            return {"success": False, "error": "Expected must be a list"}
        expected_sorted = sorted([round(float(x), 6) for x in expected])
        if len(sympy_data) != len(expected_sorted):
            return {"success": False, "error": "Count mismatch",
                    "sympy": sympy_data, "expected": expected_sorted}
        for a, b in zip(sympy_data, expected_sorted):
            if abs(a - b) > 1e-4:
                return {"success": False, "error": "Value mismatch",
                        "sympy": sympy_data, "expected": expected_sorted}

    elif comp_type == "matrix_determinant":
        if abs(sympy_data - float(expected)) > 1e-4:
            return {"success": False, "error": "Det mismatch",
                    "sympy": sympy_data, "expected": expected}

    elif comp_type == "matrix_rank":
        if sympy_data != int(expected):
            return {"success": False, "error": "Rank mismatch",
                    "sympy": sympy_data, "expected": expected}

    elif comp_type == "matrix_inverse":
        try:
            expected_matrix = [[round(float(value), 6) for value in row] for row in expected]
        except (TypeError, ValueError):
            return {"success": False, "error": "Expected must be a matrix"}
        if sympy_data != expected_matrix:
            return {"success": False, "error": "Inverse mismatch",
                    "sympy": sympy_data, "expected": expected_matrix}

    elif comp_type == "system_solve":
        try:
            expected_solution = [[round(float(value), 6) for value in row] for row in expected]
        except (TypeError, ValueError):
            return {"success": False, "error": "Expected must be a solution matrix"}
        if sympy_data != expected_solution:
            return {"success": False, "error": "Solution mismatch",
                    "sympy": sympy_data, "expected": expected_solution}

    elif comp_type == "polynomial_factor":
        if str(sympy_data) != str(expected):
            return {"success": False, "error": "Factor mismatch",
                    "sympy": sympy_data, "expected": expected}

    return {"success": True, "sympy_result": sympy_data}
