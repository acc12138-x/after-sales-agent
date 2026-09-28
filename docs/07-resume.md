# 简历项目描述

## 精简版（2 行）

> **企业售后知识库智能问答与工单自动化 Agent 平台**
> 基于 LangGraph + RAG + OpenClaw + Vue 3 的企业级售后 Agent。支持多渠道接入、混合召回检索、规则引擎、工单状态机、HITL 人工审批。检索召回率 **0.875**、上下文精确率 **0.667**。

---

## 详情版（8 条 bullet）

- **项目**：售后知识库智能问答与工单自动化 Agent 平台（个人项目）
- **技术栈**：LangGraph · LangChain · RAG · Ollama/Qwen3 · 通义千问 · Chroma · FastAPI · MySQL · Vue 3 · OpenClaw · Docker · frp
- **RAG 检索**：父子块切片 + BM25/向量混合召回 + RRF 融合 + bge-m3 重排；自研 4 指标评估框架量化，context_recall **0.875**
- **Agent 编排**：LangGraph 状态机实现意图识别 → 上下文收集 → 规则匹配 → 动作执行 → HITL 审批，支持跨系统中断恢复
- **规则引擎**：自研可复用框架（core / loaders / data 三层），19 个操作符可扩展，YAML 热加载
- **工单系统**：MySQL 持久化 + 状态机（pending → assigned → accepted → resolved → closed）+ 拒单自动重派
- **多渠道接入**：通过 OpenAI 兼容层把 LangGraph 伪装成 LLM Provider，接入 OpenClaw 实现飞书/企微统一入口
- **管理后台**：独立开发 Vue 3 + Element Plus + ECharts 前端，8 个模块含配置热重载、数据看板、审计追踪

---

## 技术栈关键词（ATS 优化）

```
核心框架：LangGraph · LangChain · FastAPI · Pydantic
RAG：父子块切片 · BM25 · 向量检索 · RRF 融合 · Reranker · 混合召回
模型层：Ollama · Qwen3 · bge-m3 · 通义千问 · DeepSeek
数据层：Chroma · MySQL · SQLAlchemy · Redis
Agent：HITL · 工具调用 · 状态机 · 中断恢复 · 规则引擎
工程化：Docker · Vue 3 · Element Plus · 审计日志 · Provider 抽象
接入：OpenClaw · OpenAI 兼容层 · frp 内网穿透 · 飞书
评估：LLM-as-judge · Faithfulness · Context Precision/Recall
```