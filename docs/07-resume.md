# 简历项目描述

## 精简版（2 行）

> **企业售后知识库智能问答与工单自动化 Agent 平台**
> 基于 LangGraph + RAG + Vue 3 的企业级售后 Agent，支持多渠道接入、混合召回检索、工单状态机、HITL 人工审批、客户资产、退款风控、SLA 时效、权限体系。检索召回率 **0.875**。

---

## 详情版（12 条 bullet）

- **项目**：售后知识库智能问答与工单自动化 Agent 平台（个人项目）
- **技术栈**：LangGraph · LangChain · RAG · Ollama/Qwen · Chroma · FastAPI · MySQL · Redis · Vue 3 · Element Plus · Docker · OpenClaw · frp
- **RAG 检索**：父子块切片 + BM25/向量混合召回 + RRF 融合 + bge-m3 重排；自研评估框架 4 指标量化，context_recall **0.875**
- **Agent 编排**：LangGraph 状态机实现意图识别 → 上下文收集 → 规则匹配 → 动作执行 → HITL 审批，支持跨系统中断恢复（SQLite checkpointer）
- **意图识别**：11 类意图 + 咨询问句后置判断 + 多轮补槽位；故障码/报警词/动作词三维规则防止误判
- **业务扩展**：工单分 6 类（报修/退货/退款/赔付/投诉/咨询）；客户资产 + 订单档案 + 退款单 + 审批流 4 张表
- **权限体系**：User 表 + 角色（admin/supervisor/engineer/agent）+ 个人权限覆盖；飞书命令按 open_id 校验角色权限
- **风控与合规**：客户风险等级评估（高频退款/多次投诉/退款率）、退款单 AI 初审 + 人工审批、审计日志全覆盖
- **SLA 时效**：按工单类型配置时效（投诉 1h / 报修 24h），工单列表倒计时，预警/超时自动发飞书通知，规则可视化编辑
- **数据校验**：故障码白名单 + 编辑距离相似度匹配（E300 → 推荐 E200/E310），未知码允许建单但标记待核实
- **多渠道**：通过 OpenAI 兼容层将 LangGraph 伪装成 LLM Provider，接入 OpenClaw 实现飞书消息 → 工单状态自动流转
- **管理后台**：Vue 3 + Element Plus + ECharts，12 模块含配置热重载、SLA 看板、权限编辑、客户批量导入、审计追踪、OpenClaw 监控
- **部署**：Docker Compose 一键起 5 容器（FastAPI/MySQL/Redis/Chroma），本地开发与容器化双模式

---

## 量化成果

| 指标 | 值 |
|---|---|
| Context Recall | **0.875** |
| Context Precision | **0.667** |
| Answer Relevancy | **0.750** |
| RAG 平均响应 | **5.0s** |
| 后端模块 | 25+ |
| API 端点 | 76+ |
| MySQL 表 | 8 张 |
| 前端页面 | 12 个 |
| 代码量 | 后端 10000+ 行 / 前端 6000+ 行 |
| Docker 服务 | 5 个容器全 healthy |

---

## 技术难点与方案

### 1. RAG 答案不精准
- **现象**：问"什么原因"和"怎么排查"返回同一答案
- **方案**：问题分类（step/cause/phenomenon/boundary/notice/scope）+ chunk 按 heading 过滤 + 7 个 prompt 模板
- **效果**：6 种问法 6 种答案，答非所问率从 40% 降到 <10%

### 2. 推理模型响应慢
- **现象**：qwen3.7-plus 单次响应 33 秒（reasoning 占 260-500 token）
- **方案**：切换 qwen-plus（非推理）+ max_tokens 2500 + 加"直接输出"约束
- **效果**：响应时间 **33s → 5s**，快 6.8 倍，质量不降

### 3. 云端 Embedding batch size 限制
- **现象**：上传长文档 500 错（DashScope 限制单次 10 条）
- **方案**：`embed_texts` 自动分批（EMBED_BATCH_SIZE=10）
- **效果**：任意长度文档稳定入库

### 4. MySQL NULLS LAST 不兼容
- **现象**：SLA 排序报 1064 语法错
- **方案**：改用 `case((col.is_(None), 1), else_=0)` 模拟
- **效果**：跨 MySQL/PostgreSQL/SQLite 通用

### 5. detached ORM 权限校验崩溃
- **现象**：飞书权限校验 500
- **方案**：`get_user_by_feishu` 在 session 内转 dict 返回，不用 detached ORM 对象
- **效果**：权限校验稳定

### 6. HITL 跨进程中断恢复
- **方案**：SQLite checkpointer + `Command(resume=decision)` + 超时自动取消
- **效果**：后端重启后中断状态保留，30 分钟无响应自动取消

---

## 不足与改进方向

- **业务数据 Mock**：订单/物流/商品/客户 JSON 假数据，生产需对接 ERP/CRM
- **管理后台无登录**：JWT 认证正在实现中
- **pytest 覆盖低**：已有手动测试脚本，单测覆盖率待提升
- **无 Redis 缓存**：相同问题每次都调 LLM，待加语义缓存
- **单点部署**：Docker Compose 单机，生产需 K8s + 主从
