# -*- coding: utf-8 -*-
"""飞书链路一键诊断。

回答两个问题：
  1. 后端能不能把消息 **发到** 飞书？（出站：直连飞书应用 API）
  2. 网关能不能把用户消息 **送进** 后端？（入站：经 OpenClaw 网关）

用法（在项目根目录执行）：

    # 只做只读检查，不发任何消息
    python scripts/feishu_doctor.py

    # 真实发送测试（会在私聊/群里出现一条【诊断测试】消息）
    python scripts/feishu_doctor.py --send --open-id ou_xxxxxxxx
    python scripts/feishu_doctor.py --send --chat-id oc_xxxxxxxx
    python scripts/feishu_doctor.py --send --mobile 13800138000

不带参数时，会自动从 users 表里挑一个已绑定 open_id / chat_id 的人员来测。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
os.environ.setdefault("no_proxy", os.environ["NO_PROXY"])

OK, BAD, WARN = "✅", "❌", "⚠️ "
_RESULTS: list[tuple[str, bool]] = []


def section(title: str) -> None:
    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


def report(name: str, ok: bool, detail: str = "", fix: str = "") -> None:
    print(f"{OK if ok else BAD} {name}" + (f"：{detail}" if detail else ""))
    if not ok and fix:
        print(f"     ↳ 修复：{fix}")
    _RESULTS.append((name, ok))


def info(msg: str) -> None:
    print(f"   {msg}")


def mask(v: str) -> str:
    v = v or ""
    if not v:
        return "(未配置)"
    return v if len(v) <= 12 else v[:8] + "..." + v[-4:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--send", action="store_true", help="真的发一条测试消息")
    ap.add_argument("--open-id", default="", help="要测的飞书 open_id (ou_...)")
    ap.add_argument("--chat-id", default="", help="要测的飞书 chat_id (oc_...)")
    ap.add_argument("--mobile", default="", help="用手机号反查 open_id")
    ap.add_argument("--email", default="", help="用邮箱反查 open_id")
    ap.add_argument("--chat-members", default="",
                    help="列出该群成员的 open_id (oc_...)，需机器人已进群 + im:chat:readonly")
    args = ap.parse_args()

    # ---------------------------------------------------------------- 1
    section("1. 配置检查")
    from app.config.settings import get_settings

    s = get_settings()
    app_id = getattr(s, "feishu_app_id", "") or getattr(s, "openclaw_feishu_app_id", "") or ""
    app_secret = (getattr(s, "feishu_app_secret", "")
                  or getattr(s, "openclaw_feishu_app_secret", "") or "")
    info(f"App ID        : {app_id or '(未配置)'}")
    info(f"App Secret    : {'已配置' if app_secret else '未配置'}（不打印）")
    info(f"OpenClaw 开关 : {getattr(s, 'openclaw_enabled', False)}")
    info(f"网关地址      : {getattr(s, 'openclaw_gateway_url', '') or '(未配置)'}")
    report("应用凭据已配置", bool(app_id and app_secret),
           fix="在 .env 里填 OPENCLAW_FEISHU_APP_ID / OPENCLAW_FEISHU_APP_SECRET")

    # ---------------------------------------------------------------- 2
    section("2. 应用凭据（tenant_access_token）")
    from app.integrations.feishu_client import _get_tenant_token

    token = _get_tenant_token()
    report("获取 tenant_access_token", bool(token),
           detail="成功" if token else "失败",
           fix="检查 App ID/Secret 是否正确、服务器能否访问 open.feishu.cn")

    # ---------------------------------------------------------------- 3
    section("3. 出站 · 私聊（open_id）")
    open_id = args.open_id.strip()
    if not open_id:
        who, open_id = _pick_from_db("feishu_open_id")
        if open_id:
            info(f"（未指定 --open-id，自动取用 users 表里「{who}」绑定的）")

    if not open_id:
        report("私聊通道", False, "没有可用的 open_id",
               "用 --open-id 指定，或去「人员管理」绑定 open_id")
    elif not open_id.startswith("ou_"):
        report("open_id 格式", False, f"{open_id!r} 不是 ou_ 开头",
               "open_id 必须以 ou_ 开头")
    else:
        report("open_id 格式", True, open_id)
        if args.send:
            from app.integrations.feishu_client import send_private
            ok, err = send_private(open_id, "【诊断测试】飞书私聊通道 — 售后 Agent")
            report("私聊发送", ok, detail=err or "已送达",
                   fix=_fix_for(err))
        else:
            info("（只读模式，未发送；加 --send 才会真发）")

    # ---------------------------------------------------------------- 4
    section("4. 出站 · 群（chat_id）")
    chat_id = args.chat_id.strip()
    if not chat_id:
        who, chat_id = _pick_from_db("feishu_chat_id")
        if chat_id:
            info(f"（未指定 --chat-id，自动取用 users 表里「{who}」绑定的）")

    if not chat_id:
        report("群通道", False, "没有可用的 chat_id",
               "用 --chat-id 指定，或去「人员管理」填 chat_id")
    elif not chat_id.startswith("oc_"):
        report("chat_id 格式", False, f"{chat_id!r} 不是 oc_ 开头",
               "chat_id 必须以 oc_ 开头")
    else:
        report("chat_id 格式", True, chat_id)
        if args.send:
            from app.integrations.feishu_client import send_to_chat
            ok, err = send_to_chat(chat_id, "【诊断测试】飞书群通道 — 售后 Agent")
            report("群发送", ok, detail=err or "已送达", fix=_fix_for(err))
        else:
            info("（只读模式，未发送；加 --send 才会真发）")

    # ---------------------------------------------------------------- 5
    section("5. 反查 open_id（手机号 / 邮箱）")
    if not (args.mobile or args.email):
        info("（未指定 --mobile / --email，跳过）")
    elif not token:
        report("反查", False, "token 获取失败，无法反查")
    else:
        from app.integrations.feishu_client import batch_get_user_ids
        res = batch_get_user_ids(
            mobiles=[args.mobile] if args.mobile else None,
            emails=[args.email] if args.email else None,
        )
        if res.get("error"):
            report("调用反查接口", False, res["error"],
                   "确认应用具备联系人查询权限")
        else:
            found = res.get("open_ids") or {}
            if found:
                for k, v in found.items():
                    report(f"反查到 {k}", True, f"open_id={v}")
            else:
                report("反查结果", False, "查不到该用户",
                       "该手机号/邮箱对应的用户可能不存在，或不在本应用的"
                       "「可用范围」内 —— 到飞书开放平台把用户加入可用范围")

    # ---------------------------------------------------------------- 6
    section("6. 机器人在哪些群（需要 im:chat:readonly）")
    if token:
        import httpx
        try:
            r = httpx.get("https://open.feishu.cn/open-apis/im/v1/chats?page_size=20",
                          headers={"Authorization": f"Bearer {token}"},
                          timeout=15, trust_env=False)
            d = r.json()
            if d.get("code") == 0:
                items = (d.get("data") or {}).get("items") or []
                report("列出机器人所在群", True, f"共 {len(items)} 个")
                for it in items[:10]:
                    info(f"   {it.get('chat_id')}  {it.get('name') or '(无名)'}")
                if not items:
                    info("   （机器人还没被拉进任何群）")
            else:
                report("列出机器人所在群", False,
                       f"code={d.get('code')} {d.get('msg', '')}",
                       "到飞书开放平台申请 im:chat:readonly 权限")
        except Exception as e:
            report("列出机器人所在群", False, str(e)[:120], "检查网络")

    # ---------------------------------------------------------------- 6b
    section("6b. 群成员 open_id（需要 im:chat:readonly + 机器人已进群）")
    if not args.chat_members:
        info("（未指定 --chat-members，跳过）")
        info("用法：--chat-members oc_xxxxxxxx  → 列出该群每个人的 open_id")
    elif not token:
        report("拉取群成员", False, "token 不可用，无法查询")
    else:
        import httpx
        cid = args.chat_members.strip()
        try:
            r = httpx.get(
                f"https://open.feishu.cn/open-apis/im/v1/chats/{cid}/members",
                params={"member_id_type": "open_id", "page_size": 50},
                headers={"Authorization": f"Bearer {token}"},
                timeout=15, trust_env=False,
            )
            d = r.json()
            if d.get("code") == 0:
                items = (d.get("data") or {}).get("items") or []
                report("拉取群成员", True, f"共 {len(items)} 人")
                for m in items[:50]:
                    info(f"   {m.get('member_id')}  {m.get('name') or '(无名)'}")
                info("↑ 把某个人的 member_id（ou_...）填到「人员管理 → 飞书 Open ID」即可")
            else:
                report("拉取群成员", False,
                       f"code={d.get('code')} {d.get('msg', '')}",
                       "确认机器人已进该群，且应用已开通 im:chat:readonly 权限")
        except Exception as e:
            report("拉取群成员", False, str(e)[:120], "检查网络")

    # ---------------------------------------------------------------- 7
    section("7. 入站 · OpenClaw 网关")
    from app.gateway.health import probe
    st = probe()
    if not st.get("enabled"):
        report("网关探活", False, "OPENCLAW_ENABLED=false，未探活",
               "需要探活就在 .env 里设 OPENCLAW_ENABLED=true（不影响 /v1 对接）")
    else:
        report("网关可达", bool(st.get("reachable")),
               f"{st.get('gateway_url') or '-'} · {st.get('message')}",
               "确认网关进程在跑、地址端口正确、防火墙放行")

    section("8. 入站 · 后端自身（本地自测，不依赖网关）")
    info("用下面这条命令模拟网关发一条消息进来：")
    print()
    print('   curl -X POST http://127.0.0.1:8000/v1/chat/completions \\')
    print('     -H "Content-Type: application/json" \\')
    print('     -d \'{"model":"local-rag","stream":false,'
          '"session_id":"doctor-1",'
          '"messages":[{"role":"user","content":"你好"}]}\'')
    print()
    info("后端日志里应出现 [REQ] 与 [CMD] 行；返回 answer 即说明入站链路通。")

    # ---------------------------------------------------------------- 汇总
    section("汇总")
    bad = [n for n, ok in _RESULTS if not ok]
    for n, ok in _RESULTS:
        print(f"  {OK if ok else BAD} {n}")
    print()
    if bad:
        print(f"共 {len(_RESULTS)} 项，失败 {len(bad)} 项：")
        for n in bad:
            print(f"  - {n}")
        return 1
    print(f"共 {len(_RESULTS)} 项，全部通过 🎉")
    return 0


def _pick_from_db(field: str) -> tuple[str, str]:
    """从 users 表里挑第一个该字段非空的值，返回 (姓名, 值)。"""
    try:
        from sqlalchemy import select

        from app.db.models.user import User
        from app.db.session import session_scope

        with session_scope() as s:
            for u in s.execute(select(User)).scalars().all():
                v = (getattr(u, field, "") or "").strip()
                if v:
                    return u.name, v
    except Exception as e:
        print(f"   （读数据库失败：{str(e)[:100]}）")
    return "", ""


def _fix_for(err: str) -> str:
    err = err or ""
    if "99992361" in err or "cross app" in err:
        return ("这个 open_id 是别的飞书应用签发的。用「人员管理 → 按手机号反查」"
                "重新获取本应用的 open_id")
    if "230002" in err:
        return "机器人不在该群里，把机器人拉进群，或改用私聊 open_id"
    if "99991672" in err:
        return "应用缺少对应权限，按报错里的链接到飞书开放平台申请"
    if "invalid open_id" in err or "invalid chat_id" in err:
        return "ID 格式不对（open_id 需 ou_ 开头，chat_id 需 oc_ 开头）"
    return "看报错码到飞书开放平台排查"


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
