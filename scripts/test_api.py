
import sys, os, time
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 60)
print("1. 健康检查")
print(client.get("/health").json())

print()
print("=" * 60)
print("2. 上传知识")
r = client.post("/knowledge/ingest", json={
    "doc_id": "doc-e102-v2",
    "source": "manual-v2",
    "content": "# 设备 E102 报警处理\n\n## 排查步骤\n1. 检查温度传感器接线。\n2. 重启设备。\n3. 仍报警则更换传感器。\n",
})
print(r.json())

print()
print("=" * 60)
print("3. 知识库统计")
print(client.get("/knowledge/stats").json())

print()
print("=" * 60)
print("4. 对话（qa）")
t0 = time.time()
r = client.post("/chat", json={"message": "E102 报警怎么排查", "thread_id": "t1"})
print("耗时:", round(time.time() - t0, 2), "s")
print(r.json())

print()
print("=" * 60)
print("5. 建工单")
r = client.post("/tickets", json={
    "device_model": "XY200",
    "error_code": "E102",
    "description": "面板报警",
    "contact": "张三 13800138000",
    "address": "上海浦东",
})
print(r.json())
tid = r.json()["ticket_id"]

print()
print("=" * 60)
print("6. 查工单")
print(client.get(f"/tickets/{tid}").json())

print()
print("=" * 60)
print("7. 列工单")
print(client.get("/tickets").json())

print()
print("=" * 60)
print("API 测试完成")
