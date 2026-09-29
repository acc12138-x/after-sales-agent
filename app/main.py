
from __future__ import annotations
import re

import os

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost,::1")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import approvals, chat, tickets, knowledge, stream, openai_compat, admin, engineers, audit, customers, refunds, sla, users, auth, feishu
from app.api.schemas.models import HealthResponse
import asyncio
from contextlib import asynccontextmanager
from app.config.settings import get_settings

settings = get_settings()


# ============================================================
# SLA 后台定时扫描（每 5 分钟）
# ============================================================
async def sla_scanner():
    """后台循环：每 5 分钟扫一次 SLA。"""
    # 启动后延迟 10 秒首次扫描
    await asyncio.sleep(10)
    while True:
        try:
            from app.services.sla_service import scan_all_tickets
            stats = scan_all_tickets()
            print(f"[SLA] 扫描完成: {stats}")
        except Exception as e:
            print(f"[SLA] 扫描失败: {e}")
        await asyncio.sleep(300)  # 5 分钟


@asynccontextmanager
async def lifespan(app):
    """启动时挂后台任务。"""
    task = asyncio.create_task(sla_scanner())
    print("[启动] SLA 定时扫描已启动（每 5 分钟）")
    yield
    task.cancel()
    print("[关闭] SLA 定时扫描已停止")

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="企业售后知识库智能问答与工单自动化 Agent 平台",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)
app.include_router(tickets.router)
app.include_router(knowledge.router)
app.include_router(stream.router)
app.include_router(openai_compat.router)
app.include_router(admin.router)
app.include_router(engineers.router)
app.include_router(users.router)
app.include_router(approvals.router)
app.include_router(auth.router)
app.include_router(audit.router)
app.include_router(customers.router)
app.include_router(refunds.router)
app.include_router(sla.router)
app.include_router(feishu.router)


@app.get("/cache/stats")
async def cache_stats():
    from app.services.cache_service import get_cache
    return get_cache().stats()


@app.post("/cache/clear")
async def cache_clear():
    from app.services.cache_service import get_cache
    n = get_cache().clear_all()
    return {"cleared": n}


@app.post("/cache/cleanup")
async def cache_cleanup():
    from app.services.cache_service import get_cache
    n = get_cache().clear_expired()
    return {"cleared": n}


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }
