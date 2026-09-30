"""故障码校验服务。

三层：
1. 格式校验（正则）
2. 白名单校验
3. 编辑距离匹配（推荐候选）
"""
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional

import yaml


CODES_PATH = Path(__file__).parent.parent / "config" / "error_codes.yaml"


def _load_config() -> Dict:
    if not CODES_PATH.exists():
        return {"error_codes": {}, "validator": {"edit_distance_threshold": 2, "allow_unknown": True}}
    with open(CODES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _levenshtein(a: str, b: str) -> int:
    """编辑距离。"""
    a, b = a.upper(), b.upper()
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur.append(min(cur[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = cur
    return prev[-1]


def validate_code(code: Optional[str]) -> Dict:
    """校验故障码。

    返回：
    {
      "code": "E300",                # 原码
      "valid": False,                # 是否在白名单
      "known": True/False,
      "candidates": [                # 未命中时的候选（编辑距离排序）
         {"code": "E102", "description": "温度传感器异常", "distance": 2},
         ...
      ],
      "allow_unknown": True,         # 配置项
      "message": "..."               # 给用户的提示（可选）
    }
    """
    cfg = _load_config()
    codes = cfg.get("error_codes", {}) or {}
    validator = cfg.get("validator", {}) or {}
    threshold = int(validator.get("edit_distance_threshold", 2))
    allow_unknown = bool(validator.get("allow_unknown", True))

    if not code:
        return {"code": None, "valid": False, "known": False, "candidates": [],
                "allow_unknown": allow_unknown, "message": ""}

    code_up = code.upper()
    all_known = list(codes.keys())

    # 命中白名单
    if code_up in codes:
        return {
            "code": code_up, "valid": True, "known": True,
            "description": codes[code_up].get("description", ""),
            "candidates": [], "allow_unknown": allow_unknown,
            "message": "",
        }

    # 未命中 → 找相似候选
    cands = []
    for kc in all_known:
        d = _levenshtein(code_up, kc)
        if d <= threshold:
            cands.append({
                "code": kc,
                "description": codes[kc].get("description", ""),
                "distance": d,
            })
    cands.sort(key=lambda x: x["distance"])

    return {
        "code": code_up, "valid": False, "known": False,
        "candidates": cands[:3],
        "allow_unknown": allow_unknown,
        "message": "",
    }


def build_warning(code: str, result: Dict) -> str:
    """根据校验结果生成给用户的提示语（可为空）。"""
    if result.get("known"):
        return ""
    cands = result.get("candidates") or []
    if cands:
        lines = [f"⚠️ 故障码 **{code}** 未在已知列表中。您可能是想说："]
        for i, c in enumerate(cands, 1):
            lines.append(f"  {i}. **{c['code']}** — {c['description']}")
        lines.append(f"\n如果确实是 **{code}**，工单已照常创建（已标记待人工核实）。")
        return "\n".join(lines)
    return (
        f"⚠️ 故障码 **{code}** 未在已知列表中。"
        f"工单已照常创建，已标记待人工核实。"
    )
