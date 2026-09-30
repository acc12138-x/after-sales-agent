"""OpenClaw 网关状态：启动时探活一次，结果缓存，供 /health 与 /admin 复用。

`OPENCLAW_ENABLED` 的语义
------------------------
- `true` ：启动时探活网关，并在 `/health` 中体现可达性
- `false`：跳过探活（本地调试常见），`/health` 显示为"已关闭"

⚠️ 这个开关只影响 **探活与健康上报**，不影响 `/v1/chat/completions`
端点本身 —— 该端点始终挂载，网关随时可以调进来。所以它**不是**集成的总闸。
"""
from __future__ import annotations

import time
from typing import Any, Dict

_STATE: Dict[str, Any] = {
    "enabled": False,
    "gateway_url": "",
    "reachable": None,       # True / False / None(未探活)
    "checked_at": None,      # unix 时间戳
    "message": "尚未探活",
}


def get_state() -> Dict[str, Any]:
    """读取缓存的探活结果（不发起网络请求）。"""
    return dict(_STATE)


def probe(timeout: float = 5.0) -> Dict[str, Any]:
    """探测网关 `/v1/models` 是否可达，并更新缓存。"""
    from app.config.settings import get_settings

    s = get_settings()
    _STATE["enabled"] = bool(getattr(s, "openclaw_enabled", False))
    _STATE["gateway_url"] = getattr(s, "openclaw_gateway_url", "") or ""
    _STATE["checked_at"] = time.time()

    if not _STATE["enabled"]:
        _STATE["reachable"] = None
        _STATE["message"] = "OPENCLAW_ENABLED=false，未探活"
        return get_state()

    if not _STATE["gateway_url"]:
        _STATE["reachable"] = False
        _STATE["message"] = "未配置 OPENCLAW_GATEWAY_URL"
        return get_state()

    try:
        import httpx

        api_key = getattr(s, "openclaw_api_key", "") or ""
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
        url = _STATE["gateway_url"].rstrip("/") + "/v1/models"
        r = httpx.get(url, headers=headers, timeout=timeout, trust_env=False)
        _STATE["reachable"] = r.status_code == 200
        _STATE["message"] = f"HTTP {r.status_code}"
    except Exception as e:
        _STATE["reachable"] = False
        _STATE["message"] = str(e)[:150]

    return get_state()
