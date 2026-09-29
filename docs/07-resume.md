# 简历项目描述

## 精简版（2 行）

> **企业售后知识库智能问答与工单自动化 Agent 平台**
> 基于 LangGraph + RAG + Vue 3 的企业级售后 Agent，支持多渠道接入、混合召回检索、工单状态机、HITL 人工审批、客户资产、退款风控、SLA 时效、JWT 权限体系、语义缓存。检索召回率 **0.875**，缓存命中加速 **20x**。

## 详情版（14 条 bullet）

- **项目**：售后知识库智能问答与工单自动化 Agent 平台（个人项目）
- **技术栈**：LangGraph · LangChain · RAG · Ollama/Qwen · Chroma · FastAPI · MySQL · Vue 3 · Element Plus · JWT · Docker · OpenClaw
- **RAG 检索**：父子块切片 + BM25/向量混合召回 + RRF 融合 + bge-m3 重排；自研评估框架 4 指标量化，context_recall 0.875
- **Agent 编排**：LangGraph 状态机实现意图识别 → 上下文收集 → 规则匹配 → 动作执行 → HITL 审批，支持跨系统中断恢复（SQLite checkpointer）
- **意图识别**：11 类意图 + 咨询问句后置判断 + 多轮补槽位；故障码/报警词/动作词三维规则防止误判
- **业务扩展**：工单分 6 类（报修/退货/退款/赔付/投诉/咨询）；客户资产 + 订单档案 + 退款单 + 审批流 4 张表
- **权限体系**：JWT 无状态认证 + 角色（admin/supervisor/engineer/agent）+ 个人权限覆盖；Web 后台 + 飞书命令双通道校验
- **风控与合规**：客户风险等级评估（高频退款/多次投诉/退款率）、退款单 AI 初审 + 人工审批、审计日志全覆盖
- **SLA 时效**：按工单类型配置时效（投诉 1h / 报修 24h），工单列表倒计时，预警/超时自动发飞书，规则可视化编辑
- **语义缓存**：SQLite 两级缓存（exact hash + embedding 语义 0.90 阈值），命中响应 20x 加速；知识库变更自动失效
- **主管审批台**：批量审批退款 + 超时工单改派，权限收敛到 supervisor 及以上
- **多渠道**：OpenAI 兼容层将 LangGraph 伪装成 LLM Provider，接入 OpenClaw 实现飞书消息 → 工单状态自动流转；单机器人 + 多群 webhook 路由
- **管理后台**：Vue 3 + Element Plus + ECharts，13 模块含配置热重载、SLA 看板、权限编辑、客户批量导入、审计追踪
- **测试与部署**：pytest 43 用例（意图/规则/RAG/缓存/API）；Docker Compose 一键起 5 容器

## 量化成果

| 指标 | 值 |
|---|---|
| Context Recall | **0.875** |
| Context Precision | **0.667** |
| Answer Relevancy | **0.750** |
| RAG 平均响应 | **5.0s** |
| 缓存命中加速 | **20x** |
| 后端模块 | 30+ |
| API 端点 | 90+ |
| MySQL 表 | 9 张 |
| 前端页面 | 13 个 |
| pytest 用例 | 43 |
| 代码量 | 后端 12000+ 行 / 前端 7000+ 行 |

## 技术难点与方案

### 1. RAG 答案不精准
- 现象：问"什么原因"和"怎么排查"返回同一答案
- 方案：问题分类（step/cause/phenomenon/boundary/notice/scope）+ chunk 按 heading 过滤 + 7 个 prompt 模板
- 效果：6 种问法 6 种答案，答非所问率从 40% 降到 <10%

### 2. 推理模型响应慢
- 现象：qwen3.7-plus 单次响应 33 秒（reasoning 占 260-500 token）
- 方案：切 qwen-plus（非推理）+ max_tokens 2500 + 加"直接输出"约束
- 效果：响应时间 33s → 5s，快 6.8 倍，质量不降

### 3. 云端 Embedding batch 限制
- 现象：上传长文档 500 错（DashScope 单次 10 条限制）
- 方案：embed_texts 自动分批（EMBED_BATCH_SIZE=10）
- 效果：任意长度文档稳定入库

### 4. MySQL 5.5 兼容
- 现象：NULLS LAST 语法错 1064
- 方案：case 表达式模拟
- 效果：跨 MySQL/PostgreSQL/SQLite 通用

### 5. 语义缓存设计
- 方案：两级命中（MD5 exact + embedding cosine 0.90），仅缓存 qa 类意图，知识库变更自动清空
- 效果：exact 20x 加速、semantic 11x 加速

### 6. JWT 无状态认证
- 方案：HS256 签发 + 7 天过期 + Authorization Bearer；权限模型 = 角色默认 + 个人 allow/deny 覆盖
- 效果：Web 后台 + 飞书命令共用一套权限判定

### 7. HITL 跨进程恢复
- 方案：SQLite checkpointer + Command(resume=decision) + 30 分钟超时
- 效果：后端重启后中断状态保留

## 不足与改进方向

- 业务数据 Mock：订单/物流/商品 JSON 假数据，生产需对接 ERP/CRM
- 单点部署：Docker Compose 单机，生产需 K8s + 主从
- Redis 未接入：语义缓存用 SQLite，高并发需切 Redis
- Celery 未实现：通知同步发，生产需异步
- audit_logs 未分表：百万级数据需按月分表