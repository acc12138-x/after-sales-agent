# 终端用户 (飞书/企微/钉钉/网页)

# |

# v

# 云服务器 (阿里云 2核1.8G)

# OpenClaw Gateway (0.0.0.0:15568)

# 

# openclaw-lark (飞书)

# 

# wecom-openclaw-plugin (企业微信)

# 

# dingtalk-connector (钉钉)

# 

# Custom Provider: local-rag

# | http://127.0.0.1:18000/v1

# frps (0.61.1)

# 

# :7000 控制端口

# 

# :18000 隧道端口 -> 本地 FastAPI

# | frp 反向隧道

# v

# 本地 GPU 机器 (GTX 1060 6GB)

# frpc.exe -> 127.0.0.1:8000

# FastAPI

# 

# /v1/chat/completions OpenAI 兼容层

# 

# /threads/{id}/runs/stream SSE 流

# 

# /threads/{id}/runs/resume HITL 恢复

# 

# /chat /knowledge /tickets /health /docs

# LangGraph 工作流

# intent -> slot\_filling -> \[rag | ticket | order] -> generate -> hitl\_gate

# 

# MemorySaver checkpointer

# RAG 检索层 (父子块切片 + BM25 + 向量 + RRF + 重排)

# Ollama (bge-m3 + Qwen3-4B)

# Chroma 向量库

# 

# 

# \### 数据流

# 

# 1\. 用户在飞书发消息

# 2\. OpenClaw Gateway 接收，判断意图，调用 local-rag Provider

# 3\. Provider 请求 http://127.0.0.1:18000/v1/chat/completions

# 4\. frps 通过隧道转发到本地 frpc

# 5\. frpc 转给 127.0.0.1:8000 (FastAPI)

# 6\. FastAPI 调用 LangGraph 工作流

# 7\. LangGraph 走 RAG / 建单 / 转人工逻辑

# 8\. 结果沿原路返回

# 

# \---

# 

# \## 技术栈

# 

# | 层级 | 技术 | 版本 |

# |---|---|---|

# | 接入网关 | OpenClaw | 2026.6.10 |

# | Agent 编排 | LangGraph | 1.2.11 |

# | 后端 | FastAPI + Uvicorn | 0.141.1 |

# | LLM 框架 | LangChain | 1.4.2 |

# | 本地推理 | Ollama + Qwen3-4B / bge-m3 | 0.6.2 |

# | 向量库 | ChromaDB | 1.5.9 |

# | 检索 | rank-bm25 + jieba | - |

# | 重排 | bge-m3 余弦相似度 | - |

# | 缓存 | Redis | 8.1.0 |

# | 业务库 | SQLAlchemy + PyMySQL | 2.0.54 |

# | 任务队列 | Celery | 5.6.3 |

# | 评估 | RAGAS + LangSmith | 0.4.3 |

# | 管理后台 | Streamlit | - |

# | 内网穿透 | frp | 0.61.1 |

# | 运行环境 | Python | 3.12.7 |

# 

# \---

# 

# \## 核心功能

# 

# \### 1. 智能问答（RAG）

# 

# \- 意图识别：qa / ticket / order / complaint / human

# \- Query 改写 + 同义词扩展

# \- BM25 + 向量混合召回，RRF 融合

# \- bge-m3 余弦相似度重排

# \- 强制引用 + 无答案兜底

# 

# \### 2. 工单自动化

# 

# \- 自动建单：收集设备型号、故障码，调用 create\_ticket

# \- 自动派单：按故障码匹配工程师技能

# \- 幂等控制：防止重复建单

# \- 工单状态流转：pending -> assigned -> resolved

# 

# \### 3. HITL 人工审批

# 

# \- 触发条件：human / complaint 意图，或置信度 < 0.5

# \- 用 LangGraph interrupt() 暂停工作流

# \- 通过 SSE hitl 事件通知 OpenClaw

# \- 用户在飞书回复"同意" -> 调 langgraph\_resume 恢复

# 

# \### 4. 多渠道接入

# 

# \- 飞书：openclaw-lark（已验证 works）

# \- 企业微信：wecom-openclaw-plugin

# \- 钉钉：dingtalk-connector

# 

# \### 5. 可视化管理后台

# 

# | Tab | 功能 |

# |---|---|

# | 知识库 | 上传文档、切片、向量化、检索测试 |

# | 对话测试 | 直连 LangGraph，不用飞书 |

# | 工单 | 列表、详情、统计 |

# | 系统配置 | 可视化改 .env，一键保存 |

# | 监控 | Ollama / FastAPI / Chroma 探活 |

# 

# \---

# 

# \## 关键技术亮点

# 

# \### 1. OpenClaw + LangGraph 双引擎架构

# 

# \- OpenClaw 管接入：多渠道统一、工具网关、权限收敛

# \- LangGraph 管编排：状态机、多轮、HITL、子图

# \- 两者通过 OpenAI 兼容层桥接，OpenClaw 只需把 LangGraph 当普通 LLM Provider

# 

# \### 2. 内网穿透混合部署

# 

# \- 云端 OpenClaw（公网可达） + 本地 GPU 推理（数据不出域）

# \- frp 反向隧道打通，本地无公网 IP 也能服务

# 

# \### 3. HITL 中断恢复

# 

# \- LangGraph interrupt() + MemorySaver checkpointer

# \- SSE 事件流通知 OpenClaw，跨系统审批

# \- 用户回复后 Command(resume=...) 从断点继续

# 

# \### 4. 5 层幻觉抑制

# 

# | 层 | 手段 |

# |---|---|

# | Prompt | 强制只基于上下文，禁止自问自答 |

# | 输出限制 | num\_predict=600，防无限生成 |

# | 参数 | temperature=0.1，repeat\_penalty=1.4 |

# | 后处理 | 去 think 块、截断自问自答、压重复引用 |

# | 兜底 | 检测到拒答 -> 用检索片段 fallback |

# 

# \### 5. 父子块切片

# 

# \- 按标题层级递归切分

# \- 父块（大块）用于生成，子块（小块）用于检索

# \- 检索命中子块 -> 通过 parent\_id 回溯父块，保证上下文完整

# 

# \### 6. 混合召回 + RRF 融合

# 

# BM25 保关键词 + 向量保语义，RRF 融合：score = sum(1 / (rrf\_k + rank))

# 

# \### 7. 跨进程状态共享

# 

# \- FastAPI 与 Streamlit 通过 HTTP API 通信

# \- 工单数据统一存在 FastAPI 进程，避免双进程状态不一致

# 

# \---

# 

# \## 项目结构

# app/

# main.py FastAPI 入口

# config/

# settings.py Pydantic Settings

# llm\_router.py 混合推理路由（预留）

# gateway/skills/ OpenClaw Skills 模拟

# search\_kb.py

# create\_ticket.py

# query\_order.py

# assign\_ticket.py

# notify\_human.py

# workflows/

# graph.py LangGraph 状态图

# state.py AgentState 定义

# nodes/

# intent.py 意图识别

# slot\_filling.py 槽位填充

# rag\_search.py 混合召回

# generate.py 生成 + 后处理

# ticket\_node.py 建单

# order\_node.py 查订单

# hitl\_gate.py HITL 门控

# rag/

# chunking.py 父子块切片

# embedding.py bge-m3 封装

# retriever.py 混合召回

# reranker.py 重排

# api/routes/

# chat.py 简单问答

# tickets.py 工单 CRUD

# knowledge.py 知识上传

# stream.py SSE 端点

# openai\_compat.py OpenAI 兼容层

# admin/dashboard.py Streamlit 后台

# evaluation/ RAGAS 评估（预留）

# docs/ 需求 / 架构 / Bridge 契约

# scripts/

# start\_all.py 一键启动

# run\_admin.py Streamlit 启动

# ingest\_docs.py 批量导入

# tests/

# data/ Chroma 持久化（gitignore）

# logs/ 运行日志（gitignore）

# 

# 

# 

# \---

# 

# \## 快速开始

# 

# \### 前置依赖

# 

# \- Python 3.10+

# \- Ollama（本地模型）

# \- Docker（可选，用于 Redis / MySQL）

# \- frps / frpc（可选，用于内网穿透）

# 

# \### 1. 克隆仓库

# git clone https://github.com/acc12138-x/after-sales-agent.git

# cd after-sales-agent

# 

# 

# 

# \### 2. 创建虚拟环境

# python -m venv venv

# source venv/bin/activate

# pip install -r requirements.txt

# 

# 

# 

# \### 3. 拉取本地模型

# ollama pull bge-m3

# ollama pull qwen2.5:3b

# 

# 

# 

# \### 4. 配置环境变量

# cp .env.example .env

# 

# 

# \### 5. 一键启动

# python scripts/start\_all.py

# 

# 

# 

# 自动拉起：

# \- FastAPI -> http://127.0.0.1:8000

# \- Streamlit -> http://127.0.0.1:8501

# \- frpc（如已配置）

# 

# \### 6. 访问管理后台

# 

# 浏览器打开 http://127.0.0.1:8501

# 

# \---

# 

# \## API 文档

# 

# 启动 FastAPI 后访问 http://127.0.0.1:8000/docs

# 

# | 方法 | 路径 | 用途 |

# |---|---|---|

# | GET | /health | 健康检查 |

# | POST | /chat | 简单问答 |

# | POST | /knowledge/ingest | 文档上传 |

# | GET | /knowledge/stats | 知识库统计 |

# | POST | /tickets | 建单 |

# | GET | /tickets | 工单列表 |

# | GET | /tickets/{id} | 工单详情 |

# | POST | /threads/{id}/runs/stream | SSE 流式问答 |

# | POST | /threads/{id}/runs/resume | HITL 恢复 |

# | GET | /threads/{id}/state | 查看 thread 状态 |

# | POST | /v1/chat/completions | OpenAI 兼容层 |

# | GET | /v1/models | 模型列表 |

# 

# \---

# 

# \## 环境变量

# 

# 见 .env.example，主要项：

# 

# | 变量 | 说明 | 默认值 |

# |---|---|---|

# | OLLAMA\_BASE\_URL | Ollama 地址 | http://127.0.0.1:11434 |

# | OLLAMA\_LLM\_MODEL | 生成模型 | qwen2.5:3b |

# | OLLAMA\_EMBEDDING\_MODEL | 嵌入模型 | bge-m3:latest |

# | CHROMA\_PERSIST\_DIR | Chroma 数据目录 | ./data/chroma |

# | CHUNK\_SIZE | 切片大小 | 512 |

# | CHUNK\_OVERLAP | 切片重叠 | 64 |

# | TOP\_K\_RETRIEVE | 召回 TopK | 20 |

# | TOP\_K\_RERANK | 重排 TopK | 5 |

# | DEEPSEEK\_API\_KEY | 云端 API（可选） | 空 |

# | REDIS\_HOST | Redis 地址 | 127.0.0.1 |

# | MYSQL\_HOST | MySQL 地址 | 127.0.0.1 |

# 

# \---

# 

# \## 部署架构

# 

# \### 方案 A：纯本地（开发/测试）

# 

# 本地机器：Ollama + FastAPI + Chroma + Streamlit

# 

# \### 方案 B：云端接入 + 本地推理（生产推荐）

# 

# 云服务器（OpenClaw + frps）-- frp --> 本地 GPU（FastAPI + Ollama + Chroma）

# 

# \### 方案 C：Docker Compose 一键部署

# docker-compose up -d

# 

# text

# 

# 拉起：Chroma + Redis + MySQL + FastAPI

# 

# \---

# 

# \## 已知限制

# 

# \- 本地 GPU 要求：Qwen3-4B 在 6GB 显存上首次加载需 30-60 秒

# \- 小模型幻觉：1.5B 模型指令遵循能力弱，推荐 3B 以上

# \- 单点故障：当前为单机部署，生产建议多副本

# \- 数据持久化：工单存内存，重启丢失（MySQL 版本开发中）

# 

# \---

# 

# \## Roadmap

# 

# \- \[x] RAG 检索层

# \- \[x] LangGraph 工作流

# \- \[x] FastAPI + OpenAI 兼容层

# \- \[x] OpenClaw 集成

# \- \[x] 飞书接入

# \- \[x] frp 内网穿透

# \- \[x] Streamlit 管理后台

# \- \[x] HITL 中断恢复

# \- \[x] 一键启动脚本

# \- \[ ] RAGAS 量化评估

# \- \[ ] MySQL 工单持久化

# \- \[ ] Redis 语义缓存

# \- \[ ] Docker Compose 完整编排

# \- \[ ] 企业微信 / 钉钉接入

# \- \[ ] Prometheus / Grafana 监控

# 

# \---

# 

# \## License

# 

# Internal Use Only

