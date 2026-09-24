# OpenClaw x LangGraph Bridge 契约

## 1. 概述

Bridge 插件负责 OpenClaw 与 LangGraph 之间的双向通信，通过两条通道：

- SSE 流：Bridge 订阅 LangGraph 的 /threads/{thread_id}/runs/stream 端点
- Webhook 回调：LangGraph 运行时向 Bridge 的 webhook 推送事件

## 2. SSE 端点契约

POST {langgraphBaseUrl}/threads/{thread_id}/runs/stream
Headers:
  Content-Type: application/json
  x-api-key: {langgraphApiKey}
Body:
  { "input": { "messages": [...] }, "stream_mode": ["updates","custom"] }

## 3. 五种事件类型

| 事件 | 触发条件 | Agent 行为 |
|---|---|---|
| status | 中间进度更新 | 静默更新，不唤醒 |
| milestone | 阶段开始/结束 | 默认静默（decision_only=true） |
| decision | 需要人工选择 | 始终唤醒 |
| hitl | 工作流在 interrupt() 暂停 | 始终唤醒，状态置 waiting |
| terminal | 工作流结束 | 始终唤醒，状态置 succeeded/failed |

## 4. Bridge 工具清单

| 工具 | 作用 |
|---|---|
| langgraph_dispatch | 派发工作流，返回 flow_id |
| langgraph_inspect | 查看运行状态 |
| langgraph_inspect_workflow | 读取工作流输入 schema |
| langgraph_list_workflows | 发现可用工作流 |
| langgraph_resume | 恢复 HITL 中断 |

## 5. HITL 恢复流程

1. LangGraph 执行到 hitl_gate，调用 interrupt()
2. LangGraph 通过 SSE 发出 hitl 事件
3. Bridge 唤醒 OpenClaw Agent（状态=waiting）
4. Agent 在原始对话线程中展示审批请求
5. 用户回复 "approve" 或 "block_revise: 原因"
6. Agent 调用 langgraph_resume(flow_id, decision)
7. LangGraph 从断点继续执行

## 6. 规范化回复格式

用户对 HITL 请求的回复必须规范化为：

- approve —— 通过
- block_revise: <原因> —— 打回修改

不符合格式的回复，由 Agent 重新追问。

## 7. Session 隔离

- 每个对话线程独立 Session
- 每个 Session 独立 Agent 实例
- 无共享状态，避免串扰
- thread_id 与 OpenClaw session_key 一一映射

## 8. 错误处理

| 错误 | 处理 |
|---|---|
| SSE 断流 | Bridge 自动重连，从断点续订 |
| Webhook 丢失 | LangGraph 重试 3 次，间隔指数退避 |
| resume 失败 | 状态回滚到 hitl_pending，允许重试 |
| thread_id 冲突 | 新 Session 隔离，不复用旧 thread_id |
