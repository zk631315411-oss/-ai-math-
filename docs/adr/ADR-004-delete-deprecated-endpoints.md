# ADR-004: 删除 deprecated 非流式端点

**日期**：2026-07-03

## 背景

`/api/qa/solve`（非流式）和 4 个 textbook 端点无前端调用，是早期版本残留。

## 决策

删除 `/api/qa/solve` + 旧三件套（build_prompt/solve_with_vision/parse_answer）+ textbook.py 整个文件 + auth.py legacy KG 端点。

## 理由

前端只走 `/solve-stream`；教材导入走 CLI；KG 查询用新版 v4.4 SQLite 端点。

## 后果

- qa.py 从 348 行降到 100 行
- textbook.py 删除
- auth.py 删除 legacy 端点
