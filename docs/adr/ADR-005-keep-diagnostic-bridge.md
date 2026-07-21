# ADR-005: 保留 app/db/diagnostic.py 桥接文件

**日期**：2026-07-03

## 背景

`app/db/diagnostic.py` 是从旧 `认知诊断模块` re-export 的桥接文件，仅被 8 个 test 文件引用。

## 决策

暂保留，作为后续诊断消费 QATurnRecord 的改造基础。

## 理由

删它需要同时改 8 个 test 的 import；诊断改造时正好从这里入手。

## 后果

- diagnostic.py 内部已指向新路径 `app.services.diagnosis`
- test 暂不动
