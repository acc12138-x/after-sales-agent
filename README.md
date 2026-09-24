# Enterprise After-Sales Knowledge Base Agent Platform

企业售后知识库智能问答与工单自动化 Agent 平台。

## 项目简介

基于 **OpenClaw（执行网关） + LangGraph（状态机编排） + 混合推理（云端 API + 本地 Ollama）** 的企业级售后 Agent 平台。

支持多渠道接入（企业微信 / 飞书 / 钉钉 / 网页），实现：

- RAG 知识库智能问答（带引用溯源）
- 自动创建工单 / 自动分派 / 自动通知
- 关键操作 HITL 人工审批
- 混合推理路由（敏感走本地，复杂走云端）
- RAGAS 评估 + LangSmith 链路追踪

## 整体架构
接入层（OpenClaw Channels）
|
Agent 编排层（LangGraph）
|
执行与工具层（OpenClaw Skills + MCP）
|
模型与数据层（云端API / Ollama + Chroma + Redis + MySQL）


## 技术栈

| 层级 | 技术 |
|---|---|
| 接入 | OpenClaw Channels |
| 编排 | LangGraph |
| 执行 | OpenClaw Skills + MCP |
| 模型 | 云端API（DeepSeek/通义） + Ollama Qwen2.5 |
| RAG | Chroma + bge-m3 + BM25 |
| 缓存 | Redis |
| 业务 | MySQL |
| 评估 | RAGAS + LangSmith |
| 后端 | FastAPI |
| 部署 | Docker + Nginx + 云服务器 |

## 目录结构
app/
main.py # FastAPI 入口
config/ # 全局配置 + LLM 路由
gateway/ # OpenClaw 配置 + Skills
workflows/ # LangGraph 工作流
rag/ # RAG 检索层
evaluation/ # RAGAS 评估
api/ # API 路由
docs/ # 需求、架构、Bridge 契约等文档
tests/ # 单元测试与集成测试
scripts/ # 初始化脚本
data/ # 原始/处理后数据


## 快速开始

### 1. 激活虚拟环境

I:\XMWJ\PYxm\venvs\easkb-agent\Scripts\Activate.ps1

### 2. 安装依赖

pip install -r requirements.txt

### 3. 配置环境变量
Copy-Item .env.example .env
编辑 .env，按需填写 API Key

### 4. 启动依赖服务
docker-compose up -d chroma redis mysql


### 5. 启动 FastAPI
uvicorn app.main:app --reload --port 8000


## 文档索引

| 文档 | 内容 |
|---|---|
| docs/01-requirements.md | 需求分析 |
| docs/02-architecture.md | 技术架构 |
| docs/03-bridge-contract.md | OpenClaw-LangGraph Bridge 规范 |
| docs/04-data-design.md | 数据库与存储设计 |
| docs/05-api-spec.md | API 接口文档 |
| docs/06-deployment.md | 部署与运维 |

## 项目状态

- [x] 项目结构搭建
- [x] Python 环境与依赖
- [ ] 需求分析 + 架构设计
- [ ] RAG 检索层
- [ ] LangGraph 工作流
- [ ] OpenClaw Skills + Bridge 联调
- [ ] FastAPI + 评估监控
- [ ] 测试 + 部署

## License

Internal Use Only
