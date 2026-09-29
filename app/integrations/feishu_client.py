"""飞书 API 客户端：token 管理 + 私聊 + 群 webhook。

参考文档：
- 获取 tenant_access_token: POST /open-apis/auth/v3/tenant_access_token/internal
- 发送消息: POST /open-apis/im/v1/messages?receive_id_type=open_id
"""
from __future__ import annotations
import time
from typing import Dict, Optional

import httpx

from app.config.settings import get_settings


# token 缓存（进程内）
_TOKEN_CACHE: Dict[str, any] = {"token": None, "expires_at": 0}


def _get_tenant_token() -> Optional[str]:
    """获取 tenant_access_token，带缓存（提前 5 分钟过期）。"""
    now = time.time()
    if _TOKEN_CACHE["token"] and now < _TOKEN_CACHE["expires_at"] - 300:
        return _TOKEN_CACHE["token"]

    s = get_settings()
    app_id = getattr(s, "feishu_app_id", "") or ""
    app_secret = getattr(s, "feishu_app_secret", "") or ""
    if not app_id or not app_secret:
        return None

    try:
        r = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": app_id, "app_secret": app_secret},
            timeout=10, trust_env=False,
        )
        d = r.json()
        if d.get("code") == 0:
            _TOKEN_CACHE["token"] = d["tenant_access_token"]
            _TOKEN_CACHE["expires_at"] = now + d.get("expire", 7200)
            return _TOKEN_CACHE["token"]
        else:
            print(f"[FEISHU] token error: {d}")
            return None
    except Exception as e:
        print(f"[FEISHU] token exception: {e}")
        return None


def send_private(open_id: str, text: str) -> tuple[bool, str]:
    """通过 open_id 私聊发文本消息。返回 (success, error)。"""
    if not open_id or not open_id.startswith("ou_"):
        return False, f"invalid open_id: {open_id}"

    token = _get_tenant_token()
    if not token:
        return False, "App ID/Secret 未配置或获取 token 失败"

    try:
        r = httpx.post(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "receive_id": open_id,
                "msg_type": "text",
                "content": '{"text":"' + text.replace('"', '\"').replace("\n", "\\n") + '"}',
            },
            timeout=15, trust_env=False,
        )
        d = r.json()
        if d.get("code") == 0:
            return True, ""
        return False, f"code={d.get('code')} msg={d.get('msg', '')}"
    except Exception as e:
        return False, str(e)[:200]


def send_private_markdown(open_id: str, title: str, content: str) -> tuple[bool, str]:
    """发富文本（用飞书富文本卡片格式）。"""
    # 简化：用纯文本，标题 + 换行 + 内容
    text = f"【{title}】\n{content}"
    return send_private(open_id, text)


def send_webhook(webhook: str, text: str, at_all: bool = False) -> tuple[bool, str]:
    """群 webhook 发文本。"""
    if not webhook:
        return False, "webhook 未配置"
    payload = {"msg_type": "text", "content": {"text": text}}
    if at_all:
        payload["content"]["text"] = "<at user_id=\"all\">所有人</at>\n" + text
    try:
        r = httpx.post(webhook, json=payload, timeout=10, trust_env=False)
        if r.status_code == 200:
            d = r.json()
            if d.get("code") == 0 or d.get("StatusCode") == 0:
                return True, ""
            return False, str(d)[:200]
        return False, f"HTTP {r.status_code}"
    except Exception as e:
        return False, str(e)[:200]


def test_connection() -> dict:
    """测试 App ID/Secret 是否有效。"""
    s = get_settings()
    return {
        "app_id": (getattr(s, "feishu_app_id", "") or "")[:8] + "..." if getattr(s, "feishu_app_id", "") else "(未配置)",
        "app_secret_set": bool(getattr(s, "feishu_app_secret", "")),
        "token_ok": _get_tenant_token() is not None,
    }
