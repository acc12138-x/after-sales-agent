"""初始化工程师数据（幂等）。"""
import json
import os
import sys

os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
sys.path.insert(0, os.getcwd())

from sqlalchemy import select
from app.db.session import init_db, session_scope
from app.db.models.engineer import Engineer

init_db()

SEED = [
    {"name": "张工", "skills": ["E1", "E2", "E102"], "region": "华东", "max_load": 10},
    {"name": "李工", "skills": ["E2", "E3"], "region": "华南", "max_load": 8},
    {"name": "王工", "skills": ["E102", "E200"], "region": "华北", "max_load": 8},
    {"name": "赵工", "skills": ["E1", "E3", "E200"], "region": "西南", "max_load": 10},
]

with session_scope() as s:
    for item in SEED:
        exists = s.execute(select(Engineer).where(Engineer.name == item["name"])).scalar_one_or_none()
        if exists:
            print(f"[SKIP] {item['name']} 已存在")
            continue
        s.add(Engineer(
            name=item["name"],
            skills=json.dumps(item["skills"], ensure_ascii=False),
            region=item["region"],
            status="online",
            max_load=item["max_load"],
            current_load=0,
        ))
        print(f"[ADD] {item['name']}")

print()
print("[OK] seed 完成")
