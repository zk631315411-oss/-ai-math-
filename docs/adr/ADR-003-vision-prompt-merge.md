# ADR-003: 视觉 prompt 合一到 prompt_builder

**日期**：2026-07-03

## 背景

文字 prompt 用新版 `build_tutor_prompt`（结构化对象），视觉 prompt 转调旧 `prompt_engine.build_prompt`（散参数），两套并行。

## 决策

在 `prompt_builder.py` 新增 `build_vision_prompt`，删除 `prompt_engine.py`。

## 理由

两套 prompt 构造器风格不统一；旧版有调试写文件代码；散参数不如结构化对象清晰。

## 后果

- prompt_builder.py 承担文字+视觉两种 prompt
- prompt_engine.py 删除
