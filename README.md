# Enterprise After-Sales Knowledge Base Agent Platform

> 企业售后知识库智能问答与工单自动化 Agent 平台

基于 **LangGraph + RAG + Ollama/云端API + OpenClaw + Vue 3** 的企业级售后 Agent。
支持多渠道接入、混合召回检索、规则引擎、工单状态机、HITL 人工审批。

---

## 📊 量化指标（自研评估框架）

| 指标 | 值 | 说明 |
|---|---|---|
| Context Recall | **0.875** | 检索召回率（优秀） |
| Context Precision | **0.667** | 上下文精确率（良好） |
| Answer Relevancy | **0.688** | 答案相关性 |
| Faithfulness | **0.688** | 忠实度（受限于本地模型） |

评估方式：8 题测试集 × 4 指标 × LLM-as-judge（通义千问）

---

## 🏗️ 整体架构

```
飞书 / 企微 / 钉钉
        │
        ▼
┌────────────────────────────────────┐
│  OpenClaw Gateway（云端）           │
│  ├─ openclaw-lark（飞书）           │
│  └─ Custom Provider: local-rag      │
└────────────────┬───────────────────┘
                 │ OpenAI 兼容层
                 ▼
┌────────────────────────────────────┐
│  FastAPI 后端                       │
│  LangGraph · RAG · 规则引擎         │
│  Chroma · MySQL · Redis             │
└────────────────┬───────────────────┘
                 │
                 ▼
┌────────────────────────────────────┐
│  Vue 3 前端（Element Plus）         │
│  8 Tab 管理后台                     │
└────────────────────────────────────┘
```

---

## 🧰 技术栈

| 层级 | 技术 |
|---|---|
| Agent 编排 | LangGraph 1.2 · LangChain 1.4 |
| 后端框架 | FastAPI 0.141 · Pydantic 2.13 |
| 本地推理 | Ollama · Qwen3-4B · bge-m3 |
| 云端 API | 通义千问 · DeepSeek · Moonshot · 智谱 · OpenAI |
| 向量库 | Chroma 1.5 |
| 检索 | rank-bm25 · jieba · RRF 融合 |
| 数据层 | MySQL 8 · SQLAlchemy 2.0 |
| 前端 | **Vue 3 · Vite · Element Plus · ECharts** |
| 接入网关 | OpenClaw 2026.6.10 |
| 内网穿透 | frp 0.61.1 |
| 容器化 | Docker 29.2 · Docker Compose 5.0 |
| 运行环境 | Python 3.12 · Node.js 24 |

---

## ✨ 核心功能

### 1. RAG 检索增强
- 父子块切片（子块检索、父块生成）
- BM25 + 向量混合召回 + RRF 融合
- bge-m3 余弦相似度重排
- 相关性阈值 + 实体词覆盖（双重过滤）

### 2. LangGraph 状态机
- 意图识别（11 类）→ 咨询问句后置判断
- 上下文收集（订单 / 物流 / 商品 / 客户）
- 规则引擎匹配 → 动作执行
- HITL 中断 + MemorySaver 恢复

### 3. 规则引擎（自研框架）
- core / loaders / data 三层分离
- 19 个内置操作符 + 可扩展
- 支持点号路径（user.vip）
- YAML 数据可热加载

### 4. 工单状态机
- pending → assigned → accepted → in_progress → resolved → closed
- 拒单自动重派（排除原工程师）
- 派单算法：技能 + 在线 + 负载升序

### 5. 多渠道接入
- OpenAI 兼容层：把 LangGraph 伪装成 LLM Provider
- OpenClaw 零改动接入飞书

### 6. Vue 3 前端管理后台
- 8 个 Tab：对话 / 知识库 / 工单 / 工程师 / 审计 / 通知 / 配置 / 监控
- ECharts 可视化
- 配置热重载

---

## 📁 项目结构

```
app/                      后端
  main.py                 FastAPI 入口
  config/                 Provider 抽象
  workflows/              LangGraph 工作流
  rag/                    RAG 检索层
  rules/                  规则引擎
  services/               业务服务
  intent/                 意图识别
  api/routes/             REST 路由
  db/                     SQLAlchemy 模型
  audit/                  审计日志
  notify/                 通知模拟
  evaluation/             自研评估
frontend/                 前端
  src/views/              8 个页面
  src/api/                HTTP 封装
  src/router/             路由
  src/layouts/            主布局
scripts/                  脚本
data/                     Chroma + ragas
docs/                     文档
```

---

## 🚀 快速开始

### 后端

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python scripts\start_all.py
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:5173

---

## 📡 主要 API

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | /chat | 智能问答 |
| GET  | /knowledge/docs | 文档列表 |
| POST | /knowledge/ingest-file | 文件上传 |
| GET  | /tickets | 工单列表 |
| POST | /tickets/{id}/accept | 接单 |
| POST | /tickets/{id}/reject | 拒单（自动重派） |
| GET  | /engineers | 工程师列表 |
| GET  | /logs/audit | 审计日志 |
| GET  | /logs/notifications | 通知记录 |
| POST | /admin/reload | 热重载引擎 |
| GET  | /admin/dashboard/stats | 看板数据 |

详见 http://127.0.0.1:8000/docs

---

## 🔬 RAG 评估

```bash
python scripts/run_eval.py
```

自研评估框架（不依赖 ragas）实现 4 个指标：
- faithfulness
- answer_relevancy
- context_precision
- context_recall

---

## 📄 License

Internal Use Only