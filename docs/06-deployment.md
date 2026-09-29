# 部署文档

## 1. 环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| Python | 3.12+ | 后端 |
| Node.js | 20+ | 前端构建 |
| MySQL | 8.0 | 业务库 |
| Redis | 7 | 缓存（预留） |
| Chroma | 1.5+ | 向量库（embedded 或 HTTP） |
| Ollama | 最新 | 本地 LLM / Embedding / Rerank |
| Docker | 29+ | 可选，一键起全栈 |
| Docker Compose | v2+ | 可选 |

## 2. 本地开发（推荐）

### 2.1 后端

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
docker compose up -d mysql redis chroma
python scripts/init_db.py
python scripts/seed_engineers.py
python scripts/seed_customers.py
python scripts/migrate_users.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

访问 http://127.0.0.1:8000/docs

### 2.2 前端

```powershell
cd frontend
npm install
npm run dev
```

访问 http://127.0.0.1:5173

### 2.3 一键启动脚本

```powershell
python scripts/start_all.py
```

这个脚本会：检查端口、起 FastAPI、起 frpc（如存在）。

## 3. Ollama 本地模型

```powershell
ollama pull bge-m3
ollama pull qwen2.5:3b
ollama list
```

用途：

- bge-m3：本地 Embedding（可选）+ Rerank
- qwen2.5:3b：备用 LLM（云端失败时降级）

## 4. Docker 全栈

### 4.1 起全栈

```powershell
docker compose build app
docker compose up -d
docker compose ps
```

预期：

```
NAME           IMAGE            STATUS
easkb-app      easkb-app        Up (healthy)   0.0.0.0:8000->8000
easkb-chroma   chromadb/chroma  Up             0.0.0.0:8001->8000
easkb-mysql    mysql:8.0        Up (healthy)   0.0.0.0:3307->3306
easkb-redis    redis:7-alpine   Up (healthy)   0.0.0.0:6379->6379
```

### 4.2 容器化注意点

| 配置 | 本地 | 容器内 |
|---|---|---|
| MySQL host | 127.0.0.1 | mysql |
| MySQL port | 3307 | 3306 |
| Ollama | 127.0.0.1:11434 | host.docker.internal:11434 |
| Chroma | 127.0.0.1:8001 | chroma:8000 |
| Chroma mode | embedded | http |

见 .env.production。

### 4.3 常用命令

```powershell
docker compose logs app -f
docker compose restart app
docker compose down
docker compose down -v
docker exec -it easkb-mysql bash
```

## 5. 生产化建议

### 5.1 安全

- .env 不进 Git（已 ignore）
- LLM/Embedding API Key 用 secret manager
- 管理后台加登录（users.password_hash 已预留）
- MySQL 主从 + 定期备份
- Nginx 反代 + HTTPS

### 5.2 高可用

- Redis 用于语义缓存
- LangGraph checkpointer 从 SQLite 换 PostgreSQL
- 多 worker（uvicorn --workers 4）
- 消息队列（Celery）处理异步通知

### 5.3 监控

- Prometheus 暴露 /metrics
- 日志聚合（Loki / ELK）
- 关键指标：RAG 延迟、LLM 成本、SLA 达标率、转人工率
- 健康检查：/health（已有）

## 6. 常见问题

| 现象 | 原因 | 修法 |
|---|---|---|
| MySQL 连不上 | Docker 没起 | docker compose up -d mysql |
| Ollama 连不上 | 服务没跑 | ollama serve |
| Embedding 400 | batch size 超限 | 已内置分批（EMBED_BATCH_SIZE=10） |
| 前端白屏 | vite proxy 未生效 | 检查 vite.config.js |
| 上传 500 | 云端 embedding 配额 | 检查 API Key 余额 |
| 命令 401 | 云端 LLM Key 错 | 检查 .env LLM_API_KEY |
| NULLS LAST 语法错 | MySQL 不支持 | 已改用 case 表达式 |
| 权限校验 500 | detached ORM | 已改为 dict 返回 |

## 7. 目录约定

| 目录 | 持久化 | 备份 |
|---|---|---|
| data/chroma/ | 是 | 是 |
| data/imports/ | 临时 | 否（定期清） |
| data/checkpoints.db | 是 | 建议 |
| logs/ | 是 | 轮转 |
| data/ragas/ | 是 | 是 |

## 8. 版本历史

| 版本 | 主要变更 |
|---|---|
| 0.1.0 | MVP：RAG + 意图 + 建单 + 退款 + HITL |
| 0.2.0 | 用户权限 + SLA 通知 + 客户导入 + Docker |