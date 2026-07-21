# ADR-001: QA 模块与诊断模块解耦

**日期**：2026-07-03

## 背景

QA 问答链路原来在 qa.py 里直接触发诊断、更新 stage。

## 决策

QA 只负责回答 + 写 QATurnRecord，不触发诊断。诊断模块独立消费 QATurnRecord。

## 理由

QA 需要低延迟（<3s），诊断是重操作（LLM 调用 + 写多个表）。耦合会导致 QA 变慢，且诊断失败会拖垮问答。

## 后果

- 新建 qa_turn_records 表
- 诊断需要改成异步消费
- QA 内部只读 stage
