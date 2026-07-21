# state：V2 长期状态投影

状态模块不解释对话，也不调用 LLM。它只消费已校验的 `StageObservation` 与关闭后的 `dimension_window`，通过确定性规则更新长期画像。

## Stage

- `certain` 正证据可初始化或晋升 Stage。
- `probable` 只在与当前 Stage 一致时增加置信度。
- `hypothesis` 只入证据账本。
- `projection_role=supporting` 的观察只记录 `suppressed` 投影日志，不修改 Stage，也不参与反证累计。
- 第一条强反证降低置信度；两条不同事件的强反证才降一级。
- 所有写入记录 `state_projection_log`，按证据 ID 幂等。

## 15维素养

- 单条 `DimensionObservation` 不修改 `math_profiles`。
- 同一 `user_id + sequence_id` 累计五个不同事件后关闭窗口。
- 每个分面至少三个事件、同向权重至少三分之二且达到 2.0 才调整一级；`certain=1.0`，`probable=0.5`。
- 一个窗口对一个分面最多调整一级，结果限制在 0-3。

发布档位由 `DIAGNOSIS_V2_MODE` 控制，默认 `shadow` 不执行任何正式画像投影。
