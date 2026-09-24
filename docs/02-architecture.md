# 技术架构设计文档

## 1. 整体分层架构

接入层（OpenClaw Channels）：企业微信 | 飞书 | 钉钉 | 网页聊天窗 | HTTP API

Agent 编排层（LangGraph）：意图识别 -> 槽位填充 -> RAG 检索 -> 工具路由 -> HITL
子图：RAG 检索子图 / 工单子图 / 人工接管子图

执行与工具层（OpenClaw Skills + MCP）：
search_kb | create_ticket | query_order | assign_ticket | notify_human
权限收敛 | 工具白名单 | 幂等控制

模型与数据层：
LLM Router：云端API(DeepSeek/通义) <-> Ollama bge-m3
Chroma（向量） | Redis（缓存） | MySQL（业务）

## 2. 核心设计原则

LangGraph 管内，OpenClaw 管外。

- LangGraph：复杂业务状态机、多轮对话、HITL、子图编排
- OpenClaw：多渠道接入、会话控制、工具执行网关、权限收敛

两者通过 openclaw-langgraph-bridge 插件桥接：

- OpenClaw Agent 保持对话控制权
- LangGraph 工作流处理后端执行
- 通过 SSE 事件流 + Webhook 回调双向通信

## 3. 关键数据流

### 3.1 简单问答流

用户 -> OpenClaw Channel -> OpenClaw Agent
    -> langgraph_dispatch
    -> LangGraph: intent -> rag_search -> generate
    -> SSE: terminal 事件
    -> OpenClaw Agent 唤醒
    -> 回复用户

### 3.2 建单流

用户："帮我报修 E102 设备"
    -> OpenClaw Agent: 意图=报修, 槽位缺失
    -> 追问设备型号/地址/联系人
    -> langgraph_dispatch
    -> LangGraph: ticket_subgraph（建单->派单->通知）
    -> SSE: terminal 事件
    -> OpenClaw Agent 回复工单号

### 3.3 HITL 流

LangGraph 执行到 hitl_gate 节点
    -> interrupt() 暂停
    -> SSE: hitl 事件
    -> Bridge 唤醒 OpenClaw Agent（状态=waiting）
    -> Agent 在原始对话中展示审批卡片
    -> 用户回复"同意"
    -> Agent 调用 langgraph_resume
    -> LangGraph 从断点继续

## 4. 技术选型

| 组件 | 选择 | 理由 |
|---|---|---|
| 接入网关 | OpenClaw | 多渠道统一、工具白名单、权限收敛 |
| Agent 编排 | LangGraph | 状态机、持久化、HITL、子图 |
| 本地模型 | Ollama + Qwen2.5 | 1060 可跑，Q4 量化 |
| 嵌入模型 | bge-m3（Ollama） | 中文强，1024 维 |
| 向量库 | Chroma | 零配置，10 万文档以内够用 |
| 缓存 | Redis | 语义缓存、会话状态、幂等键 |
| 业务库 | MySQL | 工单、用户、审计 |
| 评估 | RAGAS + LangSmith | 量化 + 追踪 |
| 后端 | FastAPI | 异步、OpenAPI |
| 部署 | Docker Compose | 一键启动 |

## 5. LLM 混合推理路由

def route_llm(query, sensitivity, complexity):
    if sensitivity == "high":
        return local_llm        # 敏感 -> Ollama
    if complexity == "high":
        return cloud_llm        # 复杂 -> 云端 API
    return local_llm            # 默认本地，省成本

云端 API 超时/限流时自动降级到本地。

## 6. 项目目录映射

| 目录 | 职责 |
|---|---|
| app/gateway/ | OpenClaw 配置与 Skills |
| app/workflows/ | LangGraph 状态图与节点 |
| app/rag/ | 检索、重排、切片 |
| app/api/ | FastAPI 路由 |
| app/evaluation/ | RAGAS 评估 |
| docs/ | 全部文档 |
| tests/ | 测试 |
