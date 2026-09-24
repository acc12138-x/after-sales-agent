
import sys, os, json, time
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

print("=" * 60)
print("1. 上传知识")
client.post("/knowledge/ingest", json={
    "doc_id": "doc-e102-v5",
    "source": "manual-v5",
    "content": "# 设备 E102 报警处理\n\n## 排查步骤\n1. 检查温度传感器接线。\n2. 重启设备。\n3. 仍报警则更换传感器。\n",
})
print("上传完成")

print()
print("=" * 60)
print("2. GET /v1/models")
r = client.get("/v1/models")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print()
print("=" * 60)
print("3. POST /v1/chat/completions (非流式)")
t0 = time.time()
r = client.post("/v1/chat/completions", json={
    "model": "local-rag",
    "messages": [{"role": "user", "content": "E102 报警怎么排查"}],
    "stream": False,
    "session_id": "test-session-1",
})
print("耗时:", round(time.time() - t0, 2), "s")
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print()
print("=" * 60)
print("4. POST /v1/chat/completions (流式)")
t0 = time.time()
with client.stream("POST", "/v1/chat/completions", json={
    "model": "local-rag",
    "messages": [{"role": "user", "content": "E102 报警怎么排查"}],
    "stream": True,
    "session_id": "test-session-2",
}) as resp:
    chunks = []
    for line in resp.iter_lines():
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:]
        if payload == "[DONE]":
            break
        try:
            obj = json.loads(payload)
            delta = obj.get("choices", [{}])[0].get("delta", {})
            if "content" in delta:
                chunks.append(delta["content"])
        except Exception:
            pass
    print("耗时:", round(time.time() - t0, 2), "s")
    print("拼出的回答：", "".join(chunks)[:300])

print()
print("=" * 60)
print("5. HITL 场景")
r = client.post("/v1/chat/completions", json={
    "model": "local-rag",
    "messages": [{"role": "user", "content": "我要转人工"}],
    "stream": False,
    "session_id": "test-session-hitl",
})
print(json.dumps(r.json(), ensure_ascii=False, indent=2))

print()
print("=" * 60)
print("OpenAI 兼容层测试完成")
