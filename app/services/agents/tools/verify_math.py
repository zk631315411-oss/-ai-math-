"""Validated SymPy verification agent tool."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.services.agents.tool_def import ToolDef
from app.services.sympy_sandbox import WHITELIST, verify_computable


VerificationType = Literal[*tuple(WHITELIST.keys())]


class VerifyMathInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    expression: str = Field(min_length=1, max_length=500)
    comp_type: VerificationType
    expected: str | list[Any] | float | int
    matrix: list[list[float]] | None = None
    vector: list[list[float]] | None = None
    degree: int | None = Field(default=None, ge=1, le=20)


def _verify_math_impl(
    expression: str,
    comp_type: str,
    expected: str | list | float | int,
    **kwargs,
) -> dict:
    data: dict = {"expression": expression}
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
    display_name="核对计算",
    description="使用受限 SymPy 验证矩阵、方程组、多项式及其他白名单数学计算。",
    input_model=VerifyMathInput,
    execute=_verify_math_impl,
)
