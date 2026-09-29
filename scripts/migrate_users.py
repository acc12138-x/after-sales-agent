# -*- coding: utf-8 -*-
"""迁移 engineers 表 -> users 表"""
import os, sys, json
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
sys.path.insert(0, os.getcwd())
sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select
from app.db.session import session_scope, init_db
from app.db.models.engineer import Engineer
from app.db.models.user import User


init_db()


# 默认密码（管理员）—— 首次登录后可改
DEFAULT_ADMIN_PWD = "admin123"


def _hash(pwd: str) -> str:
    import hashlib
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()


with session_scope() as s:
    # 1. 迁移现有 engineers
    engs = s.execute(select(Engineer)).scalars().all()
    print(f"  发现 {len(engs)} 个工程师")

    for i, e in enumerate(engs):
        exists = s.execute(
            select(User).where(User.name == e.name)
        ).scalar_one_or_none()
        if exists:
            print(f"    [SKIP] {e.name} 已在 users")
            continue

        uid = f"U{i + 1:04d}"
        u = User(
            user_id=uid,
            name=e.name,
            role="engineer",
            job="维修",
            skills=e.skills or "[]",
            region=e.region or "",
            status=e.status or "online",
            current_load=e.current_load or 0,
            max_load=e.max_load or 10,
            phone=e.phone or "",
            feishu_open_id=e.feishu_open_id or "",
        )
        s.add(u)
        print(f"    [ADD] {e.name} -> {uid}")

    # 2. 加一个默认管理员
    admin_exists = s.execute(
        select(User).where(User.role == "admin")
    ).scalar_one_or_none()
    if not admin_exists:
        s.add(User(
            user_id="U0000",
            name="管理员",
            role="admin",
            job="管理员",
            status="online",
            phone="",
            feishu_open_id="",
            password_hash=_hash(DEFAULT_ADMIN_PWD),
        ))
        print(f"    [ADD] 管理员 (默认密码: {DEFAULT_ADMIN_PWD})")

    # 3. 加一个示例主管
    sup_exists = s.execute(
        select(User).where(User.name == "李主管")
    ).scalar_one_or_none()
    if not sup_exists:
        s.add(User(
            user_id="U9000",
            name="李主管",
            role="supervisor",
            job="主管",
            status="online",
            region="总部",
            phone="13900139000",
            max_load=999,
        ))
        print("    [ADD] 李主管 (supervisor)")

    # 4. 加一个示例客服
    agent_exists = s.execute(
        select(User).where(User.name == "小周")
    ).scalar_one_or_none()
    if not agent_exists:
        s.add(User(
            user_id="U9001",
            name="小周",
            role="agent",
            job="客服",
            status="online",
            phone="13800138001",
            max_load=999,
        ))
        print("    [ADD] 小周 (agent)")

print()
print("[OK] 迁移完成")
