
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
print("2. 上传知识")
r = client.post("/knowledge/ingest", json={
    "doc_id": "doc-e102-v3",
    "source": "manual-v3",
    "content": "# 设备 E102 报警处理\n\n## 排查步骤\n1. 检查温度传感器接线。\n2. 重启设备。\n3. 仍报警则更换传感器。\n",
})
print(r.json())

print()
print("3. 对话（qa）—— 关键测试")
t0 = time.time()
r = client.post("/chat", json={"message": "E102 报警怎么排查", "thread_id": "t1"})
dt = time.time() - t0
j = r.json()
ans = j.get("answer", "")
print("耗时:", round(dt, 2), "s")
print("答案长度:", len(ans))
print("答案:", ans[:300])

print()
print("4. HITL 测试")
r = client.post("/chat", json={"message": "我要转人工", "thread_id": "t2"})
j = r.json()
print("hitl_pending:", j.get("hitl_pending"), "| status:", j.get("flow_status"))

print()
print("=" * 60)
print("快速测试完成")
