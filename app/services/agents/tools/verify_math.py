"""verify_math 工具：SymPy 数学验算。"""

from __future__ import annotations

from app.services.sympy_sandbox import verify_computable, WHITELIST
from app.services.agents.tool_def import ToolDef


def _verify_math_impl(
    expression: str,
    comp_type: str,
    expected: str | list | float | int,
    **kwargs,
) -> dict:
    """用 SymPy 验算数学表达式。"""
    data = {"expression": expression}
    if comp_type.startswith("matrix_") or comp_type == "system_solve":
        if "matrix" in kwargs:
            data["matrix"] = kwargs["matrix"]
        if "vector" in kwargs:
            data["vector"] = kwargs["vector"]
    if comp_type in ("polynomial_roots", "polynomial_factor"):
        data["degree"] = kwargs.get("degree", 5)

    result = verify_computable(comp_type, data, expected)

    return {
        "success": result.get("success", False),
        "sympy_result": result.get("sympy_result"),
        "error": result.get("error"),
        "expected": expected,
        "comp_type": comp_type,
        "supported_types": list(WHITELIST.keys()),
    }


verify_math_tool = ToolDef(
    name="verify_math",
    description="用 SymPy 验算数学表达式是否正确，支持矩阵运算、多项式求根、因式分解、线性方程组求解等",
    input_schema={
        "type": "object",
        "properties": {
            "expression": {
                "type": "string",
                "description": "数学表达式，如 'x**2 - 5*x + 6'",
            },
            "comp_type": {
                "type": "string",
                "enum": list(WHITELIST.keys()),
                "description": "计算类型",
            },
            "expected": {
                "type": ["string", "number", "array"],
                "description": "预期结果，根据 comp_type 决定类型：字符串（因式分解）、数字（行列式）、数组（特征值/根）",
            },
            "matrix": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "number"}},
                "description": "矩阵数据，仅 matrix_* 和 system_solve 类型需要",
            },
            "vector": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "number"}},
                "description": "向量数据，仅 system_solve 类型需要",
            },
            "degree": {
                "type": "integer",
                "description": "多项式次数上限，可选，默认 5",
            },
        },
        "required": ["expression", "comp_type", "expected"],
    },
    execute=_verify_math_impl,
)