"""Validation and normalized artifact construction for math plots."""

from __future__ import annotations

import math
import uuid
from typing import Any

from app.services.visualization.expression import ExpressionError, SafeExpression


KINDS = {"function_2d", "parametric_2d", "vector_2d", "linear_transform_2d"}
ANIMATION_TEMPLATES = {
    "secant_to_tangent",
    "riemann_refinement",
    "function_transform",
    "linear_map_2d",
}
_COLORS = ["#2563eb", "#dc2626", "#059669", "#7c3aed"]


def build_visualization(
    *,
    kind: str,
    title: str = "",
    series: list[dict[str, Any]] | None = None,
    domain: dict[str, Any] | None = None,
    parameter_domain: dict[str, Any] | None = None,
    samples: int = 240,
    vectors: list[dict[str, Any]] | None = None,
    points: list[dict[str, Any]] | None = None,
    segments: list[dict[str, Any]] | None = None,
    matrix: list[list[float]] | None = None,
    animation: dict[str, Any] | None = None,
    **_: Any,
) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"不支持的可视化类型: {kind}")
    normalized_title = str(title or "数学示意图").strip()[:80]
    if kind == "function_2d":
        spec = _function_spec(series or [], domain or {}, samples)
    elif kind == "parametric_2d":
        spec = _parametric_spec(series or [], parameter_domain or domain or {}, samples)
    elif kind == "vector_2d":
        spec = _vector_spec(vectors or [], points or [], segments or [])
    else:
        spec = _linear_transform_spec(matrix, vectors or [])
    recipe = _animation_recipe(kind, spec, animation)
    return {
        "id": str(uuid.uuid4()),
        "version": 1,
        "kind": kind,
        "title": normalized_title,
        "spec": spec,
        "animation_available": recipe is not None,
        "animation_status": "not_requested",
        "_animation_recipe": recipe,
    }


def _range(data: dict[str, Any], default: tuple[float, float]) -> tuple[float, float]:
    start = _finite(data.get("min", default[0]), "区间下界")
    end = _finite(data.get("max", default[1]), "区间上界")
    if start >= end or end - start > 200:
        raise ValueError("区间必须递增且跨度不超过 200")
    return start, end


def _function_spec(series: list[dict[str, Any]], domain: dict[str, Any], samples: int) -> dict[str, Any]:
    if not 1 <= len(series) <= 4:
        raise ValueError("二维函数必须包含 1 到 4 条曲线")
    start, end = _range(domain, (-10.0, 10.0))
    count = int(samples)
    output = []
    for index, item in enumerate(series):
        source = str(item.get("expression", "")).strip()
        expression = SafeExpression(source, "x")
        points = expression.sample(start, end, count)
        _require_curve_points(points)
        output.append({
            "id": f"curve-{index + 1}",
            "label": str(item.get("label") or f"y = {source}")[:60],
            "expression": source,
            "color": str(item.get("color") or _COLORS[index])[:20],
            "points": points,
        })
    return {"domain": {"min": start, "max": end}, "series": output}


def _parametric_spec(series: list[dict[str, Any]], domain: dict[str, Any], samples: int) -> dict[str, Any]:
    if not 1 <= len(series) <= 4:
        raise ValueError("参数曲线必须包含 1 到 4 条曲线")
    start, end = _range(domain, (0.0, 2 * math.pi))
    count = int(samples)
    if not 32 <= count <= 600:
        raise ValueError("采样点数量必须在 32 到 600 之间")
    step = (end - start) / (count - 1)
    output = []
    for index, item in enumerate(series):
        x_source = str(item.get("x_expression", "")).strip()
        y_source = str(item.get("y_expression", "")).strip()
        x_expr, y_expr = SafeExpression(x_source, "t"), SafeExpression(y_source, "t")
        sampled: list[dict[str, float | None]] = []
        for point_index in range(count):
            t = start + step * point_index
            try:
                x, y = x_expr.evaluate(t), y_expr.evaluate(t)
                sampled.append({"x": round(x, 10), "y": round(y, 10)})
            except ExpressionError:
                sampled.append({"x": None, "y": None})
        _require_curve_points(sampled)
        output.append({
            "id": f"curve-{index + 1}",
            "label": str(item.get("label") or f"({x_source}, {y_source})")[:60],
            "x_expression": x_source,
            "y_expression": y_source,
            "color": str(item.get("color") or _COLORS[index])[:20],
            "points": sampled,
        })
    return {"parameter_domain": {"min": start, "max": end}, "series": output}


def _vector_spec(vectors: list[dict[str, Any]], points: list[dict[str, Any]], segments: list[dict[str, Any]]) -> dict[str, Any]:
    if len(vectors) > 12 or len(points) > 20 or len(segments) > 20:
        raise ValueError("向量示意图元素数量超出限制")
    if not vectors and not points and not segments:
        raise ValueError("向量示意图至少需要一个元素")
    return {
        "vectors": [_xy_item(item, index, "vector") for index, item in enumerate(vectors)],
        "points": [_xy_item(item, index, "point") for index, item in enumerate(points)],
        "segments": [_segment_item(item, index) for index, item in enumerate(segments)],
    }


def _linear_transform_spec(matrix: list[list[float]] | None, vectors: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(matrix, list) or len(matrix) != 2 or any(not isinstance(row, list) or len(row) != 2 for row in matrix):
        raise ValueError("线性变换矩阵必须是 2×2")
    normalized_matrix = [[_finite(value, "矩阵元素") for value in row] for row in matrix]
    if not 1 <= len(vectors) <= 8:
        raise ValueError("线性变换需要 1 到 8 个向量")
    normalized_vectors = []
    for index, item in enumerate(vectors):
        vector = _xy_item(item, index, "vector")
        x, y = vector["x"], vector["y"]
        vector["transformed"] = {
            "x": normalized_matrix[0][0] * x + normalized_matrix[0][1] * y,
            "y": normalized_matrix[1][0] * x + normalized_matrix[1][1] * y,
        }
        normalized_vectors.append(vector)
    return {"matrix": normalized_matrix, "vectors": normalized_vectors}


def _xy_item(item: dict[str, Any], index: int, prefix: str) -> dict[str, Any]:
    return {
        "id": f"{prefix}-{index + 1}",
        "x": _finite(item.get("x", 0), "横坐标"),
        "y": _finite(item.get("y", 0), "纵坐标"),
        "label": str(item.get("label") or "")[:40],
        "color": str(item.get("color") or _COLORS[index % len(_COLORS)])[:20],
    }


def _segment_item(item: dict[str, Any], index: int) -> dict[str, Any]:
    start = item.get("start") or {}
    end = item.get("end") or {}
    return {
        "id": f"segment-{index + 1}",
        "start": {"x": _finite(start.get("x", 0), "线段起点"), "y": _finite(start.get("y", 0), "线段起点")},
        "end": {"x": _finite(end.get("x", 0), "线段终点"), "y": _finite(end.get("y", 0), "线段终点")},
        "label": str(item.get("label") or "")[:40],
        "color": str(item.get("color") or "#64748b")[:20],
    }


def _animation_recipe(kind: str, spec: dict[str, Any], animation: dict[str, Any] | None) -> dict[str, Any] | None:
    if not animation:
        return None
    template = str(animation.get("template") or "")
    if template not in ANIMATION_TEMPLATES:
        raise ValueError("不支持的动画模板")
    raw_params = dict(animation.get("parameters") or {})
    params: dict[str, Any] = {}
    if template in {"secant_to_tangent", "riemann_refinement"}:
        if kind != "function_2d":
            raise ValueError("该动画模板只支持二维函数")
        params["expression"] = spec["series"][0]["expression"]
        params["domain"] = spec["domain"]
        if any(point["y"] is None for point in spec["series"][0]["points"]):
            raise ValueError("包含非实数点或奇点的函数暂不支持动画")
    elif template == "function_transform":
        if kind != "function_2d" or len(spec["series"]) < 2:
            raise ValueError("函数形变动画需要至少两条二维函数")
        params["from_expression"] = spec["series"][0]["expression"]
        params["to_expression"] = spec["series"][1]["expression"]
        params["domain"] = spec["domain"]
        if any(point["y"] is None for series in spec["series"][:2] for point in series["points"]):
            raise ValueError("包含非实数点或奇点的函数暂不支持形变动画")
    elif template == "linear_map_2d":
        if kind != "linear_transform_2d":
            raise ValueError("线性映射动画需要二维线性变换")
        params["matrix"] = spec["matrix"]
        params["vectors"] = spec["vectors"]
    if template == "secant_to_tangent":
        params["x0"] = _finite(raw_params.get("x0", 0), "切点")
        if not params["domain"]["min"] <= params["x0"] <= params["domain"]["max"]:
            raise ValueError("切点必须位于函数定义域内")
        SafeExpression(params["expression"], "x").evaluate(params["x0"])
    if template == "riemann_refinement":
        interval = raw_params.get("interval") or [params["domain"]["min"], params["domain"]["max"]]
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError("积分区间必须包含两个端点")
        params["interval"] = [_finite(interval[0], "积分区间"), _finite(interval[1], "积分区间")]
        if not params["domain"]["min"] <= params["interval"][0] < params["interval"][1] <= params["domain"]["max"]:
            raise ValueError("积分区间必须位于函数定义域内并保持递增")
    return {"version": 1, "template": template, "parameters": params, "max_duration_seconds": 20}


def _finite(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}必须是数值") from exc
    if not math.isfinite(result) or abs(result) > 1e4:
        raise ValueError(f"{label}超出允许范围")
    return result


def _require_curve_points(points: list[dict[str, float | None]]) -> None:
    finite_points = sum(
        1 for point in points
        if point.get("x") is not None and point.get("y") is not None
    )
    if finite_points < 2:
        raise ValueError("曲线在所选区间内没有足够的有限实数点")
