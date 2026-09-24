
import sys, os, shutil
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")
os.chdir(r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

from app.rag.chunking import chunk_document
from app.workflows.nodes.rag_search import get_retriever, reset_retriever
from app.workflows.graph import graph
from app.config.settings import get_settings

# 清空默认 chroma 目录，避免历史数据干扰
s = get_settings()
if os.path.exists(s.chroma_persist_dir):
    shutil.rmtree(s.chroma_persist_dir)
os.makedirs(s.chroma_persist_dir, exist_ok=True)

reset_retriever()

doc = """# 设备 E102 报警处理

## 故障现象
设备面板显示 E102 报警，蜂鸣器持续响。

## 排查步骤
1. 检查温度传感器接线是否松动。
2. 若接线正常，重启设备。
3. 重启后仍报警，更换温度传感器。

## 适用范围
XX 系列设备，2023 年后批次。
"""

retriever = get_retriever()
chunks = chunk_document(doc, doc_id="doc-e102", source="manual")
retriever.index_chunks(chunks)
print("索引完成：", retriever.count(), "条")
print("=" * 60)

cases = [
    ("qa",      "设备 E102 报警怎么排查"),
    ("ticket",  "帮我报修 E102 设备，型号 XY200"),
    ("order",   "我的订单到哪了"),
    ("human",   "我要转人工"),
]

for name, q in cases:
    print(f"\n>>> 测试 {name}: {q}")
    init: dict = {
        "thread_id": f"t-{name}",
        "user_input": q,
        "messages": [],
        "slots": {},
    }
    try:
        final = graph.invoke(init)
        print("  intent   :", final.get("intent"))
        print("  slots    :", final.get("slots"))
        print("  missing  :", final.get("missing_slots"))
        print("  conf     :", round(final.get("confidence", 0.0), 4))
        print("  status   :", final.get("flow_status"))
        print("  hitl     :", final.get("hitl_pending"))
        print("  hitl_why :", final.get("hitl_reason"))
        ans = final.get("answer") or ""
        print("  answer   :", ans[:120].replace("\n", " "))
    except Exception:
        import traceback
        traceback.print_exc()

print("\n" + "=" * 60)
print("工作流测试完成")
