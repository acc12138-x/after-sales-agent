"""飞书配置 + 通知测试 API。"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import yaml

from app.api.routes.auth import get_current_user
from app.integrations.feishu_client import test_connection
from app.services.feishu_router import (
    dispatch, dispatch_to_user, list_config,
)

router = APIRouter(prefix="/feishu", tags=["feishu"])

CONFIG_PATH = Path(__file__).parents[2] / "config" / "feishu_routes.yaml"


# ============================================================
# Schemas
# ============================================================
class WebhookUpdate(BaseModel):
    channel: str
    webhook: str
    at_all: bool = False


class TestPrivateRequest(BaseModel):
    user_id: int
    title: str = "测试通知"
    content: str = "这是一条测试消息"


class TestDispatchRequest(BaseModel):
    event: str
    title: str = "测试事件"
    content: str = "内容"


# ============================================================
# 配置
# ============================================================
@router.get("/config")
async def get_config():
    """获取当前飞书配置（脱敏）。"""
    return list_config()


@router.get("/status")
async def status():
    """测试 App ID/Secret 是否有效。"""
    return test_connection()


@router.put("/webhook")
async def update_webhook(req: WebhookUpdate, user: dict = Depends(get_current_user)):
    """更新群 webhook。"""
    if not Path(CONFIG_PATH).exists():
        raise HTTPException(status_code=500, detail="config 文件不存在")

    with open(CONFIG_PATH, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    channels = cfg.setdefault("channels", {})
    ch = channels.setdefault(req.channel, {"label": req.channel, "at_all": False})
    ch["webhook"] = req.webhook
    ch["at_all"] = req.at_all

    with open(CONFIG_PATH, "w", encoding="utf-8", newline="\n") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    return {"status": "ok", "channel": req.channel}


# ============================================================
# 测试
# ============================================================
@router.post("/test-private")
async def test_private(req: TestPrivateRequest, user: dict = Depends(get_current_user)):
    """给指定用户私聊发测试消息。"""
    return dispatch_to_user(req.user_id, req.title, req.content)


@router.post("/test-dispatch")
async def test_dispatch(req: TestDispatchRequest, user: dict = Depends(get_current_user)):
    """模拟一个事件分发。"""
    return dispatch(req.event, req.title, req.content)


# ============================================================
# 手动发送
# ============================================================
class ManualSendRequest(BaseModel):
    open_id: str
    text: str


@router.post("/send")
async def send_raw(req: ManualSendRequest, user: dict = Depends(get_current_user)):
    """直接通过 open_id 发消息（调试用）。"""
    from app.integrations.feishu_client import send_private
    ok, err = send_private(req.open_id, req.text)
    return {"ok": ok, "error": err}
