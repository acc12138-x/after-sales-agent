# 数据设计文档

## 1. 数据模型总览

```
customers ──1:N──> orders
    │
    │ 1:N
    ▼
refunds ──N:1──> tickets ──N:1──> users

独立表：audit_logs / notifications / approval_flows
```

## 2. 表清单

| 表名 | 用途 | 规模 |
|---|---|---|
| users | 人员（含权限、飞书ID） | 10-100 |
| customers | 客户 + VIP + 风险 | 万级 |
| orders | 订单 + 保修 | 十万级 |
| tickets | 工单 + 状态机 + SLA | 十万级 |
| refund_requests | 退款单 + AI 审批 | 万级 |
| audit_logs | 操作审计 | 百万级 |
| notifications | 消息通知 | 百万级 |
| approval_flows | 审批流配置 | 十级 |

## 3. 核心表字段

### 3.1 tickets（工单）

| 字段 | 类型 | 说明 |
|---|---|---|
| ticket_id | VARCHAR(32) PK | T + 8 位 hex |
| status | VARCHAR(20) | pending/assigned/accepted/in_progress/resolved/closed/rejected/cancelled |
| assigned_to | VARCHAR(64) | 工程师姓名 |
| assigned_engineer_id | INT | 关联 users.id |
| device_model | VARCHAR(128) | 设备型号 |
| error_code | VARCHAR(64) | 故障码 |
| description | TEXT | 描述 |
| contact | VARCHAR(256) | 联系方式 |
| address | VARCHAR(512) | 地址 |
| missing_fields | VARCHAR(256) | 缺失字段（逗号分隔） |
| ticket_type | VARCHAR(32) | repair/return/exchange/refund/complaint/inquiry |
| related_order_id | VARCHAR(64) | 关联订单 |
| related_refund_id | VARCHAR(64) | 关联退款单 |
| sla_deadline | DATETIME | SLA 截止 |
| sla_status | VARCHAR(16) | normal/warning/overdue |
| risk_flag | VARCHAR(16) | ""/suspicious/high_risk |
| code_verified | BOOL | 故障码是否白名单 |
| reject_reason | VARCHAR(256) | 拒单原因 |
| resolved_note | TEXT | 解决备注 |
| assign_count | INT | 派单次数 |
| created_at | DATETIME | 创建时间 |
| assigned_at / accepted_at / resolved_at / closed_at | DATETIME | 状态时间戳 |

**状态机**：

```
pending → assigned → accepted → in_progress → resolved → closed
              ↓         ↓            ↓
           rejected ←───┴────────────┘（可回到 assigned 重派）
```

### 3.2 users（人员）

| 字段 | 类型 | 说明 |
|---|---|---|
| id | INT PK | 自增 |
| user_id | VARCHAR(32) UNIQUE | U0001 |
| name | VARCHAR(64) UNIQUE | 张工 |
| role | VARCHAR(32) | admin/supervisor/engineer/agent |
| job | VARCHAR(32) | 维修/客服/主管 |
| skills | TEXT | JSON: ["E102","E205"] |
| region | VARCHAR(64) | 华东 |
| status | VARCHAR(16) | online/offline/busy |
| current_load / max_load | INT | 当前/最大负载 |
| phone | VARCHAR(32) | |
| email | VARCHAR(128) | |
| feishu_open_id | VARCHAR(128) | 飞书通知 ID |
| dept | VARCHAR(64) | 部门 |
| permissions | TEXT | JSON: {"allow":[], "deny":[]} |
| password_hash | VARCHAR(256) | 管理后台登录 |

**角色默认权限**：

| 角色 | 权限 |
|---|---|
| admin | *（全部） |
| supervisor | ticket.*, refund.*, audit.view, user.*, customer.*, sla.* |
| engineer | ticket.view/accept/reject/resolve, customer.view, sla.view |
| agent | ticket.view/create, customer.view/create, refund.view/create, sla.view |

### 3.3 customers（客户）

| 字段 | 类型 | 说明 |
|---|---|---|
| customer_id | VARCHAR(32) PK | C + 6 位 hex |
| name / phone / email / address | VARCHAR | 基本信息 |
| vip_level | VARCHAR(16) | normal/silver/gold/diamond |
| risk_level | VARCHAR(16) | normal/suspicious/high_risk |
| risk_score | INT | 0-100 |
| total_orders / total_refunds / total_complaints / total_tickets | INT | 累计数 |

**风控规则**：

| 规则 | 权重 |
|---|---|
| 高频退款（≥3 次） | 30 |
| 退款率高（≥60%） | 25 |
| 多次投诉（≥2 次） | 30 |
| 短期多退款（30 天内≥2 次） | 25 |
| 低订单多退款 | 15 |

score ≥ 70 → high_risk；≥ 40 → suspicious。

### 3.4 refund_requests（退款单）

| 字段 | 类型 | 说明 |
|---|---|---|
| refund_id | VARCHAR(32) PK | RF + 8 位 hex |
| ticket_id / customer_id / order_id | VARCHAR | 关联 |
| refund_type | VARCHAR(32) | refund_only/return_refund/compensation/shipping_fee |
| amount | NUMERIC(10,2) | 金额 |
| reason | TEXT | 原因 |
| status | VARCHAR(32) | pending/ai_review/pending_approval/approved/executed/rejected/cancelled |
| ai_suggestion | VARCHAR(32) | approve/reject/need_human |
| ai_confidence | FLOAT | 0-1 |
| ai_reason | TEXT | AI 判断理由 |
| risk_flag | VARCHAR(16) | 风控标记 |
| approver / approval_note / approved_at / executed_at | | 审批信息 |

**AI 初审规则**：

| 条件 | 建议 | 置信度 |
|---|---|---|
| 高风险客户 | need_human | 0.3 |
| 疑似风险 | need_human | 0.5 |
| 金额 ≤ 100 | approve | 0.9 |
| 金额 ≤ 500 | approve | 0.7 |
| 金额 ≤ 2000 | need_human | 0.6 |
| 金额 > 2000 | need_human | 0.4 |

### 3.5 audit_logs / notifications

**audit_logs**：id, actor, action, target_type, target_id, detail(JSON), result(ok/fail), created_at

**notifications**：id, channel(feishu/sms/email), target, event, title, content, status(sent/failed/pending), created_at

## 4. 索引建议

| 表 | 索引 | 原因 |
|---|---|---|
| tickets | status, assigned_to, created_at, sla_deadline | 列表/排序/扫描 |
| users | name(UK), role, feishu_open_id | 登录/权限/飞书 |
| customers | phone(UK), risk_level | 唯一/筛选 |
| refunds | customer_id, status | 关联/筛选 |
| audit_logs | created_at, target_id | 倒序/查询 |

## 5. 数据演进

- MVP：MySQL 8.0 + SQLAlchemy 2.0，8 张表
- 扩展：加 sla_notified_at（防重复通知）、user_sessions（登录态）
- 归档：audit_logs 按月分表，notifications 保留 90 天

## 6. Mock vs 真实

`app/services/impl/` 里的 Order/Logistics/Product/Customer 是 JSON Mock 实现。
生产切换只需替换该类，不改调用方（依赖 `BaseService` + 注册中心）。