# app/services/visualization/ — 数学可视化 spec 工具

## 为什么存在

给 LLM 提供一个**安全、结构化**的数学可视化出口：模型只能描述「画什么」，
由本模块校验并产出规范化 spec；**任何环节都不执行模型提供的任意代码**，
渲染只发生在后台 worker 的白名单食谱上。

## 意图 → 规范（spec）

- `expression.py`：`SafeExpression` 基于 `ast` 的安全表达式解释器（**不是 eval**）——
  变量限 `x` / `t`，长度 ≤ 180，AST 节点数 ≤ 80，只允许内置函数白名单
  （`abs` / `sin` / `cos` / `exp` / `ln` / `sqrt` 等）与常量 `pi` / `e`，
  非法输入抛 `ExpressionError`。
- `spec_builder.py`：`build_visualization()` 校验并产出规范化 spec —— 统一采样数
  （32–600）、调色板取色、标题截断（80 字）、生成唯一 `id`；非法类型抛 `ValueError` 拒绝。
  各类型细节：`function_2d` 1–4 条曲线、区间跨度 ≤ 200；`parametric_2d` 参数域默认
  (0, 2π)；`vector_2d` 由 vectors / points / segments 组合；`linear_transform_2d` 由
  matrix + vectors 描述。

产出结构（function_2d，节选）：

```json
{
  "id": "<uuid>", "version": 1, "kind": "function_2d",
  "title": "y = x^2",
  "spec": {"domain": {"min": -10.0, "max": 10.0},
           "series": [{"id": "curve-1", "label": "y = x^2",
                       "expression": "x^2", "color": "#2563eb",
                       "points": [{"x": -10.0, "y": 100.0}]}]},
  "animation_available": false, "animation_status": "not_requested",
  "_animation_recipe": null
}
```

## 支持类型

- 图形：`function_2d` / `parametric_2d` / `vector_2d` / `linear_transform_2d`
- 动画模板：`secant_to_tangent` / `riemann_refinement` / `function_transform` / `linear_map_2d`

## 在工具调用链中的位置

`agents/tools/create_math_visualization.py` 是 QA 工具链的一环：
模型输出严格参数 → `build_visualization` 产出 spec artifact → `ToolRuntime.artifact_handler`
落库（`app/db/visualization_db.py`）→ 以 `visualization` SSE 事件推给前端。
QA 侧还有 `_ensure_requested_animation`：用户显式要求动画时，用同一个经过校验的
spec builder 回填动画食谱，绝不执行模型提供的代码。

## 动画后台渲染

- `queue.py`：RQ 入队边界，保持**不 import Manim**；入队失败会把任务标记为 failed，
  前端可轮询 `reconcile_animation_job` 修复 RQ 超时/worker 死亡后的状态；
- `app/workers/manim_worker.py`：校验白名单动画食谱（`validate_animation_recipe`）→
  Manim 渲染 mp4/png → 上传，产物大小受限（`VISUALIZATION_MAX_OUTPUT_BYTES`）；
- `storage.py`：S3 兼容对象存储上传（minio），生成带 TTL 的临时 URL
  （`VISUALIZATION_URL_TTL_SECONDS`）。

## 前端

`frontend/src/components/MathVisualization.tsx` 消费 `visualization` SSE 事件，
用 `frontend/src/components/PlotlyChart.ts`（Plotly 封装）渲染 2D 图，动画走
`visualization_id` 轮询取 mp4 播放地址。

## 边界

只产出 spec，不做教学解释——讲解、策略、回答全部由 QA 链路完成。

## 思路变动历史

- 2026-08-07：可靠的可视化工具运行时落地（安全表达式解析 + spec 规范化 + RQ 动画队列）。
