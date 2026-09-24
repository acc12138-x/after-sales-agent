
import sys
sys.path.insert(0, r"I:\XMWJ\PYxm\Enterprise After-Sales Knowledge Base Agent Platform")

from app.rag.chunking import chunk_document
from app.rag.retriever import HybridRetriever
from app.rag.reranker import rerank

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

chunks = chunk_document(doc, doc_id="doc-e102", source="manual")
print("切片数:", len(chunks))
for c in chunks[:5]:
    print("  -", c.chunk_id, "| parent=", c.is_parent, "|", c.text[:30].replace("\n", " "))

retriever = HybridRetriever(persist_dir="./data/chroma_test")
retriever.index_chunks(chunks)
print("索引完成，集合中", retriever.count(), "条")

query = "E102 报警怎么排查"
hits = retriever.search_hybrid(query, k=5)
print("混合召回 Top5:", hits)

ids = [cid for cid, _ in hits]
docs = retriever.fetch_chunks(ids)
print("取回", len(docs), "条")
for d in docs[:3]:
    print("  -", d["chunk_id"], "|", d["text"][:40].replace("\n", " "))

reranked = rerank(query, docs, top_k=3)
print("重排 Top3:")
for r in reranked:
    print("  - score=", round(r["rerank_score"], 4), "|", r["text"][:40].replace("\n", " "))
