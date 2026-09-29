# API 规范

> 基线：`http://127.0.0.1:8000` · 交互式文档：`/docs` · OpenAPI：`/openapi.json`

## 认证说明

当前版本未启用全局认证。

- **管理后台**：应加登录（users.password_hash 已预留）
- **飞书入口**：通过 `user` 字段传 `open_id`，服务端查 users 表校验权限

## 端点总览

### chat（1）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/chat` | 主对话入口，支持 HITL 恢复 |

### tickets（15）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/tickets` | 工单列表（含 SLA 倒计时） |
| POST | `/tickets` | 创建工单 |
| GET | `/tickets/{id}` | 工单详情 |
| PATCH | `/tickets/{id}` | 补全工单 |
| POST | `/tickets/{id}/accept` | 接单 |
| POST | `/tickets/{id}/reject` | 拒单（自动重派） |
| POST | `/tickets/{id}/start` | 开始处理 |
| POST | `/tickets/{id}/resolve` | 标记解决 |
| POST | `/tickets/{id}/close` | 关闭工单 |
| GET | `/tickets/{id}/audit` | 工单审计日志 |
| GET | `/tickets/{id}/notifications` | 工单通知记录 |

### users（12）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/users/meta` | 角色、权限字典 |
| GET | `/users` | 人员列表 |
| POST | `/users` | 创建人员 |
| GET | `/users/{id}` | 人员详情 |
| PUT | `/users/{id}` | 更新人员 |
| DELETE | `/users/{id}` | 删除人员 |
| POST | `/users/{id}/toggle-status` | 上线/下线 |
| GET | `/users/{id}/permissions` | 有效权限 |
| POST | `/users/{id}/check` | 检查单条权限 |
| POST | `/users/rebuild-load` | 重建负载 |

### customers（9）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/customers` | 客户列表 |
| POST | `/customers` | 创建客户 |
| GET | `/customers/{id}` | 客户详情 |
| GET | `/customers/{id}/orders` | 客户订单 |
| GET | `/customers/{id}/tickets` | 客户工单 |
| GET | `/customers/{id}/refunds` | 客户退款 |
| GET | `/customers/{id}/risk` | 风险评估 |
| POST | `/customers/import/upload` | 上传 Excel（返回预览） |
| POST | `/customers/import/confirm` | 确认导入 |
| GET | `/customers/import/template` | 下载模板 |

### refunds（6）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/refunds` | 退款列表 |
| POST | `/refunds` | 创建退款（AI 初审） |
| GET | `/refunds/{id}` | 退款详情 |
| POST | `/refunds/{id}/approve` | 人工审批 |
| POST | `/refunds/{id}/execute` | 执行打款 |
| GET | `/refunds/stats/summary` | 退款统计 |

### knowledge（7）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/knowledge/ingest` | 文本入库 |
| POST | `/knowledge/ingest-file` | 文件上传（PDF/Word/Excel） |
| GET | `/knowledge/docs` | 文档列表 |
| GET | `/knowledge/docs/{id}/detail` | 文档详情 |
| DELETE | `/knowledge/docs/{id}` | 删除文档 |
| GET | `/knowledge/stats` | 知识库统计 |

### sla（5）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/sla/summary` | SLA 汇总 |
| POST | `/sla/scan` | 手动扫描 |
| GET | `/sla/tickets` | 实时 SLA 列表 |
| GET | `/sla/rules` | 读规则 |
| PUT | `/sla/rules` | 更新规则 |

### logs（4）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/logs/audit` | 审计日志 |
| GET | `/logs/notifications` | 通知记录 |
| GET | `/logs/audit/stats` | 审计统计 |
| GET | `/logs/notifications/stats` | 通知统计 |

### engineers（6，兼容保留）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/engineers` | 列表 |
| POST | `/engineers` | 创建 |
| PUT | `/engineers/{id}` | 更新 |
| DELETE | `/engineers/{id}` | 删除 |
| POST | `/engineers/{id}/toggle-status` | 切换 |
| POST | `/engineers/rebuild-load` | 重建负载 |

### admin（5）

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin/config` | 读配置 |
| POST | `/admin/config` | 改配置 |
| POST | `/admin/reload` | 热重载 |
| GET | `/admin/provider-templates` | Provider 模板 |
| GET | `/admin/dashboard/stats` | 看板数据 |
| GET | `/admin/openclaw/status` | OpenClaw 探活 |

### v1（OpenAI 兼容层，3）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/chat/completions` | OpenAI 兼容对话（飞书用） |
| GET | `/v1/models` | 模型列表 |
| GET | `/v1/models` | 同上 |

### threads（SSE，3）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/threads/{id}/runs/stream` | SSE 流式执行 |
| POST | `/threads/{id}/runs/resume` | 恢复 HITL |
| GET | `/threads/{id}/state` | 查看状态 |

**总计：约 76 个端点。**

## 关键端点示例

### POST /chat — 主对话入口

```json
// 请求
{
  "message": "E102 报警怎么排查",
  "thread_id": "web-abc123",
  "user_id": "anonymous"
}
```

```json
// 响应
{
  "thread_id": "web-abc123",
  "answer": "1. 检查温度传感器接线...\n2. 若接线正常，重启设备...",
  "intent": "qa",
  "confidence": 0.85,
  "citations": [{"index": 1, "source": "manual-v6"}],
  "flow_status": "succeeded",
  "hitl_pending": false
}
```

### POST /v1/chat/completions — 飞书入口

```json
{
  "model": "local-rag",
  "messages": [{"role": "user", "content": "接单 T12345678"}],
  "stream": false,
  "user": "ou_zhang_open_id"
}
```

### POST /customers/import/upload

`multipart/form-data`，字段 `file`（xlsx/xls/csv）。

返回：`{token, headers, auto_mapping, total_rows, preview[10]}`

### POST /customers/import/confirm

```json
{
  "token": "abc...",
  "mapping": {"客户姓名": "name", "手机号": "phone"}
}
```

返回：`{total, success, skipped, failed, errors[]}`

## 权限说明

飞书命令的权限映射：

| 命令 | 需要权限 |
|---|---|
| 接单 / 开始处理 | ticket.accept |
| 标记完成 | ticket.resolve |
| 拒单 | ticket.reject |
| 改派 | ticket.reassign |
| 审核退款 | refund.approve |
| 执行退款 | refund.execute |

## 错误码

| HTTP | 含义 |
|---|---|
| 400 | 参数错误 / 状态不允许 |
| 404 | 资源不存在 |
| 409 | 唯一键冲突 |
| 500 | 内部错误 |
| 503 | 依赖不可用（如无可用工程师） |