from app.services.sympy_sandbox import verify_computable


def test_sympy_quality_gate_covers_core_matrix_operations() -> None:
    assert verify_computable(
        "matrix_eigenvalues", {"matrix": [[1, 2], [3, 4]]}, ["5.3723", "-0.3723"]
    )["success"]
    assert verify_computable(
        "matrix_determinant", {"matrix": [[1, 2], [3, 4]]}, -2
    )["success"]
    assert verify_computable(
        "matrix_rank", {"matrix": [[1, 0], [0, 1]]}, 2
    )["success"]


def test_sympy_quality_gate_rejects_unsafe_or_invalid_answers() -> None:
    assert not verify_computable("remove_file_system", {}, [])["success"]
    assert not verify_computable(
        "matrix_determinant", {"matrix": [[0] * 15 for _ in range(15)]}, 0
    )["success"]
    result = verify_computable(
        "matrix_eigenvalues", {"matrix": [[1, 2], [3, 4]]}, ["999", "888"]
    )
    assert not result["success"]
    assert "mismatch" in result.get("error", "")
