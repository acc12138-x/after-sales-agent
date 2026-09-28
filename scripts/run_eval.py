"""自研 RAG 评估：4 个指标 × N 题。"""
from __future__ import annotations
import os, sys, json, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")

print("=" * 70)
print("RAG 自研评估")
print("=" * 70)

# ---------- 加载测试集 ----------
with open("data/ragas/testset.json", encoding="utf-8") as f:
    testset = json.load(f)

# 默认只跑前 8 题，快一些。全跑改 None
N = int(os.environ.get("EVAL_N", "8"))
items = testset["items"][:N] if N > 0 else testset["items"]

print(f"测试集：{len(items)} 题")
print()

# ---------- Step 1: 跑 RAG 收集数据 ----------
from app.workflows.graph import graph

records = []
print("[Step 1] 跑 RAG 系统...")
for i, item in enumerate(items, 1):
    q = item["question"]
    print(f"  [{i}/{len(items)}] {q}")

    try:
        final = graph.invoke(
            {"thread_id": f"eval-{i}", "user_input": q, "messages": [], "slots": {}},
            config={"configurable": {"thread_id": f"eval-{i}"}},
        )
        answer = final.get("answer") or ""
        contexts = [c.get("text", "") for c in (final.get("retrieved") or [])]
    except Exception as e:
        print(f"    [ERR] {e}")
        answer, contexts = "", []

    records.append({
        "question": q,
        "answer": answer,
        "contexts": contexts,
        "ground_truth": item["ground_truth"],
    })

print(f"  收集完成：{len(records)} 条")
print()

# ---------- Step 2: LLM-as-judge 评分 ----------
from app.evaluation.rag_eval import evaluate_one

print("[Step 2] LLM-as-judge 评分（最慢一步）...")
print()

all_scores = []
t_start = time.time()

for i, r in enumerate(records, 1):
    t0 = time.time()
    print(f"  [{i}/{len(records)}] {r['question']}")

    scores = evaluate_one(
        question=r["question"],
        answer=r["answer"],
        contexts=r["contexts"],
        ground_truth=r["ground_truth"],
    )
    r["scores"] = scores
    all_scores.append(scores)

    dt = time.time() - t0
    print(f"    faith={scores['faithfulness']:.2f} "
          f"relev={scores['answer_relevancy']:.2f} "
          f"prec={scores['context_precision']:.2f} "
          f"recall={scores['context_recall']:.2f}  ({dt:.1f}s)")

# ---------- 汇总 ----------
metrics = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
summary = {
    m: round(sum(s[m] for s in all_scores) / len(all_scores), 4)
    for m in metrics
}

total_dt = time.time() - t_start

print()
print("=" * 70)
print("评估结果汇总")
print("=" * 70)
for m in metrics:
    print(f"  {m:<22} = {summary[m]:.4f}")
print("=" * 70)
print(f"  总耗时：{total_dt:.1f}s")
print()

# ---------- 保存 ----------
out = {
    "timestamp": datetime.now().isoformat(),
    "n_samples": len(records),
    "metrics": summary,
    "per_question": [
        {
            "question": r["question"],
            "answer": r["answer"][:200],
            "contexts_count": len(r["contexts"]),
            "ground_truth": r["ground_truth"],
            "scores": r["scores"],
        }
        for r in records
    ],
}
with open("data/ragas/eval_result.json", "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=2, default=str)

print(f"[OK] 结果 -> data/ragas/eval_result.json")
