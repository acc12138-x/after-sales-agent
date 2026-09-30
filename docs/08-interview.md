# 面试话术与深挖问答

## 一、1 分钟项目介绍

我做的项目叫 **企业对话式企业业务 Agent 平台**。

**背景**：企业售后客服要同时应对产品手册、历史工单、订单系统，重复劳动多、工单派单靠人工。

**架构**：三块——
1. **接入层**用 OpenClaw 做多渠道网关（飞书/企微/钉钉），通过 OpenAI 兼容层对接我的服务
2. **编排层**用 LangGraph 做状态机：意图识别 → 上下文收集 → 规则匹配 → 动作执行 → HITL 审批
3. **能力层**是 RAG 检索 + 规则引擎 + 业务服务 + 权限体系

**技术亮点**：
- RAG 用父子块切片 + BM25/向量混合召回 + RRF 融合 + 重排，context_recall 0.875
- 意图识别加咨询问句后置判断，避免"E102 报警怎么排查"被误判成建单
- 语义缓存用 SQLite 两级命中（exact + embedding 0.90），命中响应 20x 加速
- JWT 权限体系：Web 后台 + 飞书命令双通道校验，角色 + 个人覆盖
- HITL 用 LangGraph 的 interrupt + SQLite checkpointer，支持跨进程中断恢复

**量化结果**：context_recall 0.875，缓存加速 20x，pytest 43 用例，13 Tab Vue 3 后台，Docker 化部署。

**不足**：业务数据 Mock，生产需替换 Service 实现。

---

## 二、核心难点深挖

### 难点 1：RAG 检索结果不相关时仍强行回答

**现象**：用户问"今天天气怎么样"，系统返回"E102 报警排查步骤"。

**根因**：向量检索永远返回 TopK，没有相关性阈值。

**解决方案（5 层过滤）**：
1. Prompt 约束
2. 阈值过滤：rerank_score < 0.55 拒答
3. 实体词覆盖
4. 无答案拒答
5. fallback 用检索片段兜底

### 难点 2：LLM 输出带思考痕迹

**现象**：答案里出现标题路径、中英混杂、繁体、引用重复。

**解决方案（多层后处理）**：去 think 块 → 剥 heading → 截断自问自答 → 引用去重 → 繁转简 → 强制编号。

### 难点 3：HITL 跨系统中断恢复

**方案**：SqliteSaver 持久化 + interrupt() 暂停 + Command(resume) 恢复 + 30 分钟超时。

### 难点 4：语义缓存设计

**方案**：
- 两级命中：exact（MD5）+ semantic（embedding 余弦 0.90）
- 只缓存 qa 类
- 失效：TTL 24h + ingest 后清空
- 后端可插拔

**效果**：exact 20x、semantic 11x 加速。

### 难点 5：JWT 权限体系

**方案**：
- 角色默认权限 + 个人 allow/deny 覆盖
- effective = 角色默认 + allow - deny
- 双通道：Web 走 Depends，飞书走 open_id 校验
- 前端菜单过滤 hasPerm

### 难点 6：多飞书群路由

**方案**：单机器人 + 多群 webhook + 事件路由 yaml + 降级到 notifications 表。

### 难点 7：MySQL 5.5 兼容

**方案**：case 表达式模拟 NULLS LAST，跨数据库通用。

---

## 三、常见深挖问题

### Q1：为什么用 LangGraph 而不是 LangChain Agent？

LangChain Agent 是隐式循环，LLM 自己决定下一步，不可控；LangGraph 是显式状态机，每个节点可测、可观测、可中断。我的场景需要 HITL、状态持久化、多轮槽位填充。

### Q2：父子块切片怎么理解？

用小块检索、用大块生成。父块 = 一个 section，子块 = section 内的小片段。

### Q3：RRF 融合是什么？

Reciprocal Rank Fusion，公式 score = Σ 1/(k + rank)，k 通常取 60。只看排名，天然解决 BM25 和向量分数量纲不同的问题。

### Q4：怎么保证不瞎编？

4 道防线：Prompt 约束 + 阈值过滤 + 无答案兜底 + 后处理。

### Q5：工单派单怎么保证公平？

技能匹配 + 在线状态 + 负载未满 + 负载升序。拒单后排除原工程师，重派给下一个。

### Q6：本地模型 vs 云端 API 怎么选？

Provider 抽象 + base_url 判断。开发用本地，生产用云端。评估用云端。

### Q7：为什么不做微调？

成本高 + 优先度低。RAG + Prompt + 后处理已解决 80% 问题。未来用 QLoRA 微调。

### Q8：项目有没有上生产？

架构是生产级，业务数据是 Mock。核心理念：框架是真的，业务是假的。

### Q9：语义缓存如何避免脏数据？

3 个失效机制：TTL 24h、ingest 后清空、只缓存 qa 类。

### Q10：JWT 怎么防篡改？

HS256 签名 + secret 存 .env（128 字符）+ 7 天过期 + 前端 localStorage。

### Q11：为什么用 SQLite 缓存而不是 Redis？

SQLite 零依赖、<10ms、可持久化，适合中小规模。Redis 适合多实例。架构预留 RedisBackend，业务代码零改动。

### Q12：43 个 pytest 用例覆盖了什么？

intent 12 个 + rules 7 个 + services 6 个 + cache 4 个 + rag 3 个 + api_auth 7 个 + api_tickets 4 个。没覆盖 chat 全流程（云端 LLM 慢）和 approvals 批量。

---

## 四、简历提交前自检清单

| 项 | 状态 |
|---|---|
| GitHub 有 README + 架构图 | 是 |
| 有量化数据（4 指标 + 20x 缓存） | 是 |
| 能一句话说清项目做什么 | 是 |
| 能演示端到端流程 | 是 |
| 有 5+ 个可深挖的难点 | 是 |
| 有 pytest 单测 | 是 |
| 诚实说明 Mock 和未做 | 是 |
| 代码有注释和文档（8/8 篇） | 是 |