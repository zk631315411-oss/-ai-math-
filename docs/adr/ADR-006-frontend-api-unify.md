# ADR-006: 前端 API 调用统一收口到 api.ts

**日期**：2026-07-03

## 背景

前端 4 个组件（App.tsx、ExercisePanel.tsx、KnowledgeGraph.tsx、ProfilePanel.tsx）共有 17 处散装 fetch，硬编码 `/api/` 路径，未走 API_BASE 常量，开发环境可能 404，且无统一错误处理。

## 决策

在 api.ts 新增 13 个封装函数，4 个组件的散装 fetch 全部替换为调用 api.ts 函数。

## 理由

统一 API 调用入口；所有请求走 API_BASE；统一 res.ok 检查和错误消息；组件不再关心 URL 拼接。

## 后果

- api.ts 从 305 行扩展到约 400 行
- 4 个组件删除散装 fetch
- 前后端接口契约不变
