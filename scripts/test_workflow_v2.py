import sys, os, json, time
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

from app.rag.chunking import chunk_document
from app.workflows.nodes.rag_search import get_retriever, reset_retriever
from app.workflows.graph import graph
from app.config.settings import get_settings

# 清空并重建知识库
s = get_settings()
import shutil
if os.path.exists(s.chroma_persist_dir):
    shutil.rmtree(s.chroma_persist_dir)
os.makedirs(s.chroma_persist_dir, exist_ok=True)
reset_retriever()

doc = """# 设备 E102 报警处理

## 排查步骤
1. 检查温度传感器接线。
2. 重启设备。
3. 仍报警则更换传感器。
"""
r = get_retriever()
r.index_chunks(chunk_document(doc, doc_id="doc-e102", source="manual"))
print(f"[索引] {r.count()} 条切片")
print("=" * 60)

cases = [
    ("我要退货", "查订单+规则匹配+退货方案"),
    ("订单 O20260101001 我要退货", "带订单号的退货"),
    ("我的设备 E102 报修", "报修"),
    ("E102 报警怎么排查", "RAG 问答"),
    ("物流什么时候到 O20260201002", "查物流"),
    ("我要转人工", "HITL"),
]

for text, desc in cases:
    print()
    print(f">>> {text}    [{desc}]")
    init = {
        "thread_id": f"t-{abs(hash(text)) % 100000}",
        "user_input": text,
        "messages": [],
        "slots": {},
    }
    cfg = {"configurable": {"thread_id": init["thread_id"]}}
    try:
        t0 = time.time()
        final = graph.invoke(init, config=cfg)
        dt = time.time() - t0
        print(f"  intent:    {final.get('intent')}")
        print(f"  context:   order_id={final.get('context', {}).get('order_id')} days={final.get('context', {}).get('days_since_received')}")
        print(f"  rule:      {final.get('rule_matches', [{}])[0].get('rule_name') if final.get('rule_matches') else None}")
        print(f"  action:    {final.get('rule_next_action')}")
        print(f"  status:    {final.get('flow_status')}")
        print(f"  hitl:      {final.get('hitl_pending')}")
        print(f"  elapsed:   {dt:.2f}s")
        ans = final.get("answer", "") or ""
        print(f"  answer:    {ans[:120]}")
    except Exception as e:
        import traceback
        traceback.print_exc()

print()
print("=" * 60)
print("工作流 v2 测试完成")
