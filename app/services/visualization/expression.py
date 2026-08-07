"""A small, non-eval mathematical expression interpreter."""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass
from typing import Callable


class ExpressionError(ValueError):
    pass


_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": abs,
    "acos": math.acos,
    "asin": math.asin,
    "atan": math.atan,
    "cos": math.cos,
    "cosh": math.cosh,
    "exp": math.exp,
    "ln": math.log,
    "log": math.log,
    "log10": math.log10,
    "sin": math.sin,
    "sinh": math.sinh,
    "sqrt": math.sqrt,
    "tan": math.tan,
    "tanh": math.tanh,
}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_BINOPS = {
    ast.Add: lambda a, b: a + b,
    ast.Sub: lambda a, b: a - b,
    ast.Mult: lambda a, b: a * b,
    ast.Div: lambda a, b: a / b,
    ast.Pow: lambda a, b: a**b,
}
_UNARYOPS = {ast.UAdd: lambda value: value, ast.USub: lambda value: -value}
_MAX_MAGNITUDE = 1e12


@dataclass(frozen=True)
class SafeExpression:
    source: str
    variable: str = "x"

    def __post_init__(self) -> None:
        if self.variable not in {"x", "t"}:
            raise ExpressionError("变量只能是 x 或 t")
        if not self.source or len(self.source) > 180:
            raise ExpressionError("表达式长度必须在 1 到 180 个字符之间")
        try:
            tree = ast.parse(self.source.replace("^", "**"), mode="eval")
        except SyntaxError as exc:
            raise ExpressionError("表达式语法无效") from exc
        if sum(1 for _ in ast.walk(tree)) > 80:
            raise ExpressionError("表达式过于复杂")
        self._validate(tree)
        object.__setattr__(self, "_tree", tree)

    def evaluate(self, value: float) -> float:
        try:
            result = float(self._evaluate(self._tree.body, {self.variable: float(value)}))
        except (ArithmeticError, OverflowError, TypeError, ValueError) as exc:
            raise ExpressionError("表达式在该点无实数值") from exc
        if not math.isfinite(result) or abs(result) > _MAX_MAGNITUDE:
            raise ExpressionError("表达式结果超出允许范围")
        return result

    def sample(self, start: float, end: float, count: int) -> list[dict[str, float | None]]:
        if not math.isfinite(start) or not math.isfinite(end) or start >= end:
            raise ExpressionError("定义域必须是有限且递增的区间")
        if end - start > 200:
            raise ExpressionError("定义域跨度不能超过 200")
        if not 32 <= count <= 600:
            raise ExpressionError("采样点数量必须在 32 到 600 之间")
        step = (end - start) / (count - 1)
        points: list[dict[str, float | None]] = []
        for index in range(count):
            x = start + step * index
            try:
                y: float | None = self.evaluate(x)
            except ExpressionError:
                y = None
            points.append({"x": round(x, 10), "y": None if y is None else round(y, 10)})
        return points

    def _validate(self, node: ast.AST) -> None:
        for item in ast.walk(node):
            if isinstance(item, (ast.Expression, ast.Load)):
                continue
            if isinstance(item, ast.Constant):
                if isinstance(item.value, bool) or not isinstance(item.value, (int, float)):
                    raise ExpressionError("表达式只允许数值常量")
                continue
            if isinstance(item, ast.Name):
                if item.id not in {self.variable, *_CONSTANTS, *_FUNCTIONS}:
                    raise ExpressionError(f"不支持的名称: {item.id}")
                continue
            if isinstance(item, ast.BinOp):
                if type(item.op) not in _BINOPS:
                    raise ExpressionError("不支持该运算符")
                continue
            if isinstance(item, ast.UnaryOp):
                if type(item.op) not in _UNARYOPS:
                    raise ExpressionError("不支持该一元运算符")
                continue
            if isinstance(item, ast.Call):
                if not isinstance(item.func, ast.Name) or item.func.id not in _FUNCTIONS:
                    raise ExpressionError("仅允许白名单数学函数")
                if item.keywords or len(item.args) != 1:
                    raise ExpressionError("数学函数必须且只能接收一个位置参数")
                continue
            if isinstance(item, tuple(_BINOPS) + tuple(_UNARYOPS)):
                continue
            raise ExpressionError(f"不支持的表达式结构: {type(item).__name__}")

    def _evaluate(self, node: ast.AST, variables: dict[str, float]) -> float:
        if isinstance(node, ast.Constant):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id in variables:
                return variables[node.id]
            return _CONSTANTS[node.id]
        if isinstance(node, ast.UnaryOp):
            return _UNARYOPS[type(node.op)](self._evaluate(node.operand, variables))
        if isinstance(node, ast.BinOp):
            left = self._evaluate(node.left, variables)
            right = self._evaluate(node.right, variables)
            if isinstance(node.op, ast.Pow) and abs(right) > 20:
                raise ExpressionError("幂指数超出允许范围")
            result = _BINOPS[type(node.op)](left, right)
            if isinstance(result, complex) or not math.isfinite(result) or abs(result) > _MAX_MAGNITUDE:
                raise ExpressionError("中间结果超出允许范围")
            return result
        if isinstance(node, ast.Call):
            return float(_FUNCTIONS[node.func.id](self._evaluate(node.args[0], variables)))
        raise ExpressionError("表达式无法求值")
