
import sys, os, json, time
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 60)
print("1. 上传知识")
r = client.post("/knowledge/ingest", json={
    "doc_id": "doc-e102-v4",
    "source": "manual-v4",
    "content": "# 设备 E102 报警处理\n\n## 排查步骤\n1. 检查温度传感器接线。\n2. 重启设备。\n3. 仍报警则更换传感器。\n",
})
print(r.json())

print()
print("=" * 60)
print("2. SSE 流：普通问答")
t0 = time.time()
with client.stream("POST", "/threads/t-qa/runs/stream",
                   json={"input": {"message": "E102 报警怎么排查"}}) as resp:
    for line in resp.iter_lines():
        if line:
            print(line)
print("耗时:", round(time.time() - t0, 2), "s")

print()
print("=" * 60)
print("3. SSE 流：HITL 触发")
with client.stream("POST", "/threads/t-hitl/runs/stream",
                   json={"input": {"message": "我要转人工"}}) as resp:
    for line in resp.iter_lines():
        if line:
            print(line)

print()
print("=" * 60)
print("4. 查看 thread 状态")
print(client.get("/threads/t-hitl/state").json())

print()
print("=" * 60)
print("5. resume 恢复 HITL")
r = client.post("/threads/t-hitl/runs/resume", json={"decision": "approve"})
print(r.json())

print()
print("=" * 60)
print("6. resume 后再看状态")
print(client.get("/threads/t-hitl/state").json())

print()
print("=" * 60)
print("SSE 测试完成")
