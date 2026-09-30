"""飞书配置 + 通知测试 API。"""
from __future__ import annotations
from pathlib import Path

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
ENV_PATH = Path(__file__).resolve().parents[3] / ".env"


def _write_env_webhook(channel: str, webhook: str) -> None:
    """把群 webhook 写进 .env（不进仓库）。

    ⚠️ webhook 是密钥，绝不要写进 feishu_routes.yaml —— 那个文件是被 git 跟踪的。
    """
    key = "FEISHU_WEBHOOK_" + channel.upper()
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    out, done = [], False
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and "=" in s and \
                s.split("=", 1)[0].strip().upper() == key:
            out.append(f"{key}={webhook}")
            done = True
        else:
            out.append(line)
    if not done:
        out += ["", "# ===== 飞书群 webhook（敏感，勿提交）=====", f"{key}={webhook}"]
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


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
    """更新群 webhook（写进 .env，避免密钥进仓库）。"""
    if req.webhook:
        try:
            _write_env_webhook(req.channel, req.webhook.strip())
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"写入 .env 失败：{e}")

    # 非敏感的 label / at_all 仍留在 YAML；YAML 里的 webhook 一律清空
    if Path(CONFIG_PATH).exists():
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        channels = cfg.setdefault("channels", {})
        ch = channels.setdefault(req.channel, {"label": req.channel, "at_all": False})
        ch["webhook"] = ""
        ch["at_all"] = req.at_all
        with open(CONFIG_PATH, "w", encoding="utf-8", newline="\n") as f:
            yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)

    return {"status": "ok", "channel": req.channel, "webhook_saved_to": ".env"}


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
