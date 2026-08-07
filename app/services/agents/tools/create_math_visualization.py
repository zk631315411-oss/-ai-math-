"""Structured and validated mathematical visualization tool."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel, model_validator

from app.services.agents.tool_def import ToolDef
from app.services.visualization.spec_builder import build_visualization


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Domain(StrictInput):
    min: float | None = None
    max: float | None = None


class Animation(StrictInput):
    template: Literal[
        "secant_to_tangent", "riemann_refinement", "function_transform", "linear_map_2d"
    ] = Field(description=(
        "Required when the user asks for an animation. Use secant_to_tangent for a secant "
        "approaching a tangent, riemann_refinement for Riemann sums, function_transform for "
        "function deformation, and linear_map_2d for a 2D matrix transformation."
    ))
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Template parameters such as expression, x0, h_start, h_end, and duration.",
    )


class FunctionSeries(StrictInput):
    expression: str = Field(min_length=1, max_length=180)
    label: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)


class ParametricSeries(StrictInput):
    x_expression: str = Field(min_length=1, max_length=180)
    y_expression: str = Field(min_length=1, max_length=180)
    label: str | None = Field(default=None, max_length=60)
    color: str | None = Field(default=None, max_length=20)


class XYItem(StrictInput):
    x: float
    y: float
    label: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=20)


class Segment(StrictInput):
    start: XYItem
    end: XYItem
    label: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=20)


class Function2DInput(StrictInput):
    kind: Literal["function_2d"]
    title: str = Field(default="", max_length=80)
    series: list[FunctionSeries] = Field(min_length=1, max_length=4)
    domain: Domain | None = None
    samples: int = Field(default=240, ge=32, le=600)
    animation: Animation | None = Field(
        default=None,
        description=(
            "Animation recipe. Include this whenever the user requests animation or dynamic "
            "derivation; for a secant approaching a tangent use secant_to_tangent."
        ),
    )


class Parametric2DInput(StrictInput):
    kind: Literal["parametric_2d"]
    title: str = Field(default="", max_length=80)
    series: list[ParametricSeries] = Field(min_length=1, max_length=4)
    parameter_domain: Domain | None = None
    samples: int = Field(default=240, ge=32, le=600)


class Vector2DInput(StrictInput):
    kind: Literal["vector_2d"]
    title: str = Field(default="", max_length=80)
    vectors: list[XYItem] = Field(default_factory=list, max_length=12)
    points: list[XYItem] = Field(default_factory=list, max_length=20)
    segments: list[Segment] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def require_content(self) -> "Vector2DInput":
        if not self.vectors and not self.points and not self.segments:
            raise ValueError("向量示意图至少需要一个元素")
        return self


MatrixRow = Annotated[list[float], Field(min_length=2, max_length=2)]


class LinearTransform2DInput(StrictInput):
    kind: Literal["linear_transform_2d"]
    title: str = Field(default="", max_length=80)
    matrix: list[MatrixRow] = Field(min_length=2, max_length=2)
    vectors: list[XYItem] = Field(min_length=1, max_length=8)
    animation: Animation | None = Field(
        default=None,
        description=(
            "Animation recipe. Include linear_map_2d whenever the user asks to animate the "
            "matrix transformation."
        ),
    )


VisualizationUnion = Annotated[
    Union[Function2DInput, Parametric2DInput, Vector2DInput, LinearTransform2DInput],
    Field(discriminator="kind"),
]


class MathVisualizationInput(RootModel[VisualizationUnion]):
    pass


def _create_math_visualization_impl(**kwargs: Any) -> dict[str, Any]:
    artifact = build_visualization(**kwargs)
    return {
        "model_result": {
            "success": True,
            "visualization_id": artifact["id"],
            "kind": artifact["kind"],
            "summary": "数学示意图已生成并显示在回答下方，请结合图形解释关键变化。",
        },
        "artifacts": [artifact],
    }


create_math_visualization_tool = ToolDef(
    name="create_math_visualization",
    display_name="生成数学示意图",
    description=(
        "生成受限交互数学示意图。支持二维函数、参数曲线、向量和二维线性变换；"
        "仅在图形明显有助于理解时调用，每个回答最多调用一次。"
        "如果用户明确要求动画，必须在参数中提供 animation，并选择对应的受限模板。"
    ),
    input_model=MathVisualizationInput,
    execute=_create_math_visualization_impl,
    max_calls_per_turn=1,
    kind="artifact",
)
