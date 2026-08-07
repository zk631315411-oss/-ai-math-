"""RQ job that compiles allowlisted scene recipes into Manim artifacts."""

from __future__ import annotations

import shutil
import tempfile
import math
from pathlib import Path
from typing import Any

from app.config import config
from app.db.visualization_db import (
    get_animation_job,
    get_visualization_record,
    update_animation_job,
)
from app.services.visualization.expression import ExpressionError, SafeExpression
from app.services.visualization.storage import upload_file


def render_animation_job(job_id: str) -> dict[str, str]:
    job = get_animation_job(job_id)
    visualization = get_visualization_record(job["visualization_id"])
    recipe = visualization.get("animation_recipe")
    if not recipe:
        update_animation_job(job_id, "failed", error="可视化没有动画场景协议")
        raise ValueError("missing animation recipe")

    update_animation_job(job_id, "running")
    try:
        recipe = validate_animation_recipe(recipe)
        with tempfile.TemporaryDirectory(prefix="ai-math-manim-") as temp_dir:
            movie_path, poster_path = _render_scene(recipe, Path(temp_dir), job_id)
            for path in (movie_path, poster_path):
                if not path.exists() or path.stat().st_size <= 0:
                    raise RuntimeError(f"渲染产物缺失: {path.name}")
                if path.stat().st_size > config.VISUALIZATION_MAX_OUTPUT_BYTES:
                    raise RuntimeError(f"渲染产物超过大小限制: {path.name}")
            video_key = f"visualizations/{visualization['user_id']}/{visualization['id']}/{job_id}.mp4"
            poster_key = f"visualizations/{visualization['user_id']}/{visualization['id']}/{job_id}.png"
            upload_file(movie_path, video_key, "video/mp4")
            upload_file(poster_path, poster_key, "image/png")
            update_animation_job(job_id, "completed", video_key=video_key, poster_key=poster_key)
            return {"video_key": video_key, "poster_key": poster_key}
    except Exception as exc:
        try:
            from rq import get_current_job
            current_job = get_current_job()
            retries_left = int(getattr(current_job, "retries_left", 0) or 0)
        except Exception:
            retries_left = 0
        update_animation_job(job_id, "queued" if retries_left > 0 else "failed", error=str(exc))
        raise


def _render_scene(recipe: dict[str, Any], output_dir: Path, output_name: str) -> tuple[Path, Path]:
    from manim import tempconfig

    scene_class = _scene_class(recipe)
    media_dir = output_dir / "media"
    with tempconfig({
        "media_dir": str(media_dir),
        "output_file": output_name,
        "format": "mp4",
        "pixel_width": 1280,
        "pixel_height": 720,
        "frame_rate": 30,
        "write_to_movie": True,
        "disable_caching": True,
        "preview": False,
    }):
        scene = scene_class()
        scene.render()
        movie = Path(scene.renderer.file_writer.movie_file_path)
    if not movie.exists():
        matches = list(media_dir.rglob(f"{output_name}.mp4"))
        if not matches:
            raise RuntimeError("Manim 未生成 MP4")
        movie = matches[0]
    final_movie = output_dir / f"{output_name}.mp4"
    shutil.copy2(movie, final_movie)
    poster = output_dir / f"{output_name}.png"
    duration = _extract_poster_and_duration(final_movie, poster)
    if duration > 20.5:
        raise RuntimeError("动画时长超过 20 秒")
    return final_movie, poster


def validate_animation_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    """Revalidate the persisted protocol before importing or invoking Manim."""
    if not isinstance(recipe, dict) or recipe.get("version") != 1:
        raise ValueError("unsupported animation recipe version")
    template = recipe.get("template")
    if template not in {
        "secant_to_tangent", "riemann_refinement", "function_transform", "linear_map_2d",
    }:
        raise ValueError("unsupported animation template")
    duration = _finite_number(recipe.get("max_duration_seconds", 20), "duration")
    if duration <= 0 or duration > 20:
        raise ValueError("animation duration is out of range")
    raw_params = recipe.get("parameters")
    if not isinstance(raw_params, dict):
        raise ValueError("animation parameters must be an object")
    params: dict[str, Any] = {}

    if template in {"secant_to_tangent", "riemann_refinement", "function_transform"}:
        params["domain"] = _validated_domain(raw_params.get("domain"))
    if template in {"secant_to_tangent", "riemann_refinement"}:
        expression = str(raw_params.get("expression") or "")
        SafeExpression(expression, "x")
        params["expression"] = expression
    elif template == "function_transform":
        first = str(raw_params.get("from_expression") or "")
        second = str(raw_params.get("to_expression") or "")
        SafeExpression(first, "x")
        SafeExpression(second, "x")
        params["from_expression"] = first
        params["to_expression"] = second
    else:
        matrix = raw_params.get("matrix")
        if not isinstance(matrix, list) or len(matrix) != 2 or any(
            not isinstance(row, list) or len(row) != 2 for row in matrix
        ):
            raise ValueError("linear map matrix must be 2x2")
        normalized_matrix = [[_finite_number(value, "matrix value") for value in row] for row in matrix]
        vectors = raw_params.get("vectors")
        if not isinstance(vectors, list) or not 1 <= len(vectors) <= 8:
            raise ValueError("linear map must contain 1 to 8 vectors")
        normalized_vectors = []
        for item in vectors:
            if not isinstance(item, dict):
                raise ValueError("invalid linear map vector")
            x = _finite_number(item.get("x"), "vector x")
            y = _finite_number(item.get("y"), "vector y")
            normalized_vectors.append({
                "x": x,
                "y": y,
                "transformed": {
                    "x": normalized_matrix[0][0] * x + normalized_matrix[0][1] * y,
                    "y": normalized_matrix[1][0] * x + normalized_matrix[1][1] * y,
                },
            })
        params["matrix"] = normalized_matrix
        params["vectors"] = normalized_vectors

    if template == "secant_to_tangent":
        x0 = _finite_number(raw_params.get("x0", 0), "x0")
        if not params["domain"]["min"] <= x0 <= params["domain"]["max"]:
            raise ValueError("x0 must be inside the domain")
        SafeExpression(params["expression"], "x").evaluate(x0)
        params["x0"] = x0
    elif template == "riemann_refinement":
        interval = raw_params.get("interval")
        if not isinstance(interval, list) or len(interval) != 2:
            raise ValueError("Riemann interval must contain two endpoints")
        normalized_interval = [
            _finite_number(interval[0], "interval start"),
            _finite_number(interval[1], "interval end"),
        ]
        domain = params["domain"]
        if not domain["min"] <= normalized_interval[0] < normalized_interval[1] <= domain["max"]:
            raise ValueError("Riemann interval must be inside the domain")
        params["interval"] = normalized_interval

    return {
        "version": 1,
        "template": template,
        "parameters": params,
        "max_duration_seconds": duration,
    }


def _validated_domain(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        raise ValueError("animation domain must be an object")
    start = _finite_number(value.get("min"), "domain minimum")
    end = _finite_number(value.get("max"), "domain maximum")
    if start >= end or end - start > 200:
        raise ValueError("animation domain is out of range")
    return {"min": start, "max": end}


def _finite_number(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be numeric") from exc
    if not math.isfinite(result) or abs(result) > 1e4:
        raise ValueError(f"{label} is out of range")
    return result


def _duration_seconds(path: Path) -> float:
    import av

    with av.open(str(path)) as container:
        if container.duration is not None:
            return float(container.duration / av.time_base)
        stream = next((item for item in container.streams if item.type == "video"), None)
        if stream is None or stream.duration is None or stream.time_base is None:
            raise RuntimeError("animation duration is unavailable")
        return float(stream.duration * stream.time_base)


def _extract_poster_and_duration(movie_path: Path, poster_path: Path) -> float:
    """Use the FFmpeg libraries bundled with PyAV; the Manim image has no CLI binary."""
    import av

    with av.open(str(movie_path)) as container:
        stream = next((item for item in container.streams if item.type == "video"), None)
        if stream is None:
            raise RuntimeError("animation video stream is missing")
        frame = next(container.decode(stream), None)
        if frame is None:
            raise RuntimeError("animation poster frame is unavailable")
        frame.to_image().save(poster_path, format="PNG")
        if container.duration is not None:
            return float(container.duration / av.time_base)
        if stream.duration is None or stream.time_base is None:
            raise RuntimeError("animation duration is unavailable")
        return float(stream.duration * stream.time_base)


def _scene_class(recipe: dict[str, Any]):
    from manim import (
        ApplyMatrix,
        Arrow,
        Axes,
        BLUE,
        Create,
        Dot,
        FadeIn,
        GREEN,
        Line,
        NumberPlane,
        RED,
        ReplacementTransform,
        Scene,
        Transform,
        ValueTracker,
        VGroup,
        WHITE,
        YELLOW,
        always_redraw,
    )

    template = recipe.get("template")
    params = recipe.get("parameters") or {}

    class GeneratedScene(Scene):
        def construct(self):
            if template == "secant_to_tangent":
                expression = SafeExpression(str(params["expression"]), "x")
                x_min, x_max = _domain(params)
                axes = Axes(x_range=[x_min, x_max, _tick(x_min, x_max)], y_range=[-6, 6, 2], tips=False)
                graph = axes.plot(_plot_function(expression), x_range=[x_min, x_max], color=BLUE)
                x0 = float(params.get("x0", (x_min + x_max) / 2))
                h = ValueTracker(max((x_max - x_min) / 4, 1.0))
                first = Dot(axes.c2p(x0, expression.evaluate(x0)), color=YELLOW)
                second = always_redraw(lambda: Dot(axes.c2p(x0 + h.get_value(), _safe_value(expression, x0 + h.get_value())), color=RED))
                secant = always_redraw(lambda: Line(first.get_center(), second.get_center(), color=GREEN).set_length(6))
                self.play(Create(axes), Create(graph), FadeIn(first), FadeIn(second), Create(secant), run_time=2)
                self.play(h.animate.set_value(0.05), run_time=6)
                self.wait(1)
            elif template == "riemann_refinement":
                expression = SafeExpression(str(params["expression"]), "x")
                x_min, x_max = _domain(params)
                interval = params.get("interval") or [x_min, x_max]
                a, b = float(interval[0]), float(interval[1])
                axes = Axes(x_range=[x_min, x_max, _tick(x_min, x_max)], y_range=[-2, 8, 2], tips=False)
                graph = axes.plot(_plot_function(expression), x_range=[x_min, x_max], color=BLUE)
                rectangles = axes.get_riemann_rectangles(graph, x_range=[a, b], dx=(b - a) / 4, color=GREEN, fill_opacity=0.55)
                self.play(Create(axes), Create(graph), FadeIn(rectangles), run_time=2)
                for count in (8, 16, 32):
                    refined = axes.get_riemann_rectangles(graph, x_range=[a, b], dx=(b - a) / count, color=GREEN, fill_opacity=0.55)
                    self.play(ReplacementTransform(rectangles, refined), run_time=1.5)
                    rectangles = refined
                self.wait(1)
            elif template == "function_transform":
                first = SafeExpression(str(params["from_expression"]), "x")
                second = SafeExpression(str(params["to_expression"]), "x")
                x_min, x_max = _domain(params)
                axes = Axes(x_range=[x_min, x_max, _tick(x_min, x_max)], y_range=[-6, 6, 2], tips=False)
                source = axes.plot(_plot_function(first), x_range=[x_min, x_max], color=BLUE)
                target = axes.plot(_plot_function(second), x_range=[x_min, x_max], color=RED)
                self.play(Create(axes), Create(source), run_time=2)
                self.play(Transform(source, target), run_time=5)
                self.wait(1)
            elif template == "linear_map_2d":
                matrix = params["matrix"]
                plane = NumberPlane(x_range=[-6, 6, 1], y_range=[-4, 4, 1])
                vector_group = VGroup()
                target_group = VGroup()
                for item in (params.get("vectors") or [])[:8]:
                    vector_group.add(Arrow(plane.c2p(0, 0), plane.c2p(item["x"], item["y"]), buff=0, color=YELLOW))
                    transformed = item.get("transformed") or {}
                    target_group.add(Arrow(plane.c2p(0, 0), plane.c2p(transformed["x"], transformed["y"]), buff=0, color=RED))
                self.play(Create(plane), Create(vector_group), run_time=2)
                self.play(ApplyMatrix(matrix, plane), Transform(vector_group, target_group), run_time=5)
                self.wait(1)
            else:
                raise ValueError("unsupported animation template")

    return GeneratedScene


def _domain(params: dict[str, Any]) -> tuple[float, float]:
    domain = params.get("domain") or {"min": -6, "max": 6}
    return float(domain["min"]), float(domain["max"])


def _tick(start: float, end: float) -> float:
    return max(1.0, round((end - start) / 6, 1))


def _safe_value(expression: SafeExpression, value: float) -> float:
    try:
        return expression.evaluate(value)
    except ExpressionError:
        return 0.0


def _plot_function(expression: SafeExpression):
    return lambda value: _safe_value(expression, value)
