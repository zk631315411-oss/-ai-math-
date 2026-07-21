# ADR-007: 前端提取 MarkdownRenderer 公共组件

**日期**：2026-07-03

## 背景

ChatPanel、ExercisePanel、MarkerPopover 三个组件各自配置了 ReactMarkdown + remarkMath + rehypeKatex，3 处重复，改一处漏两处。

## 决策

新建 MarkdownRenderer.tsx 公共组件，统一 Markdown + KaTeX 渲染配置（含 formatMath 和 p/code/pre 自定义渲染），三个组件改用公共组件。

## 理由

消除重复；统一渲染行为；后续改渲染逻辑只需改一处。

## 后果

- 三个组件删除旧 import 和内部 RichText/formatMath
- MarkdownRenderer.tsx 新增
- 删除 44 行重复代码
