"""RAGAS 量化评估脚本。

流程：
1. 读测试集 -> 逐题跑 RAG 系统（拿 answer + retrieved contexts）
2. 构造 RAGAS 数据集
3. 用 LLM-as-judge 计算 4 个指标
4. 保存结果 JSON
"""
from __future__ import annotations
import os, sys, json, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")

print("=" * 70)
print("RAGAS 评估")
print("=" * 70)

# ============================================================
# Step 1: 跑 RAG 系统收集 answer + contexts
# ============================================================
print()
print("[Step 1] 跑 RAG 系统收集数据...")

from app.workflows.graph import graph

with open("data/ragas/testset.json", encoding="utf-8") as f:
    testset = json.load(f)

records = []
for i, item in enumerate(testset["items"], 1):
    q = item["question"]
    print(f"  [{i}/{len(testset['items'])}] {q}")

    init = {
        "thread_id": f"ragas-{i}",
        "user_input": q,
        "messages": [],
        "slots": {},
    }
    try:
        final = graph.invoke(init, config={"configurable": {"thread_id": f"ragas-{i}"}})
        answer = final.get("answer") or ""
        retrieved = final.get("retrieved", []) or []
        contexts = [c.get("text", "") for c in retrieved]
    except Exception as e:
        print(f"    [ERR] {e}")
        answer = ""
        contexts = []

    records.append({
        "question": q,
        "answer": answer,
        "contexts": contexts,
        "ground_truth": item["ground_truth"],
    })

print(f"  收集完成：{len(records)} 条")

# 保存原始记录
with open("data/ragas/raw_runs.json", "w", encoding="utf-8", newline="
") as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
print("  [OK] 原始数据 -> data/ragas/raw_runs.json")

# ============================================================
# Step 2: 初始化 RAGAS LLM-as-judge
# ============================================================
print()
print("[Step 2] 初始化 RAGAS judge LLM...")

from app.config.settings import get_settings
s = get_settings()

# 优先用 DeepSeek（有 key），否则用 Ollama
use_cloud_judge = bool(s.deepseek_api_key)
if use_cloud_judge:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    judge_llm = ChatOpenAI(
        model="deepseek-chat",
        api_key=s.deepseek_api_key,
        base_url=s.deepseek_base_url,
        temperature=0.0,
        timeout=60,
    )
    judge_emb = OpenAIEmbeddings(
        model=s.dashscope_embedding_model if s.dashscope_api_key else "text-embedding-v3",
        api_key=s.dashscope_api_key or "sk-dummy",
        base_url=s.dashscope_base_url,
        check_embedding_ctx_length=False,
    )
    print("  Judge: DeepSeek + DashScope")
else:
    from langchain_ollama import ChatOllama, OllamaEmbeddings
    judge_llm = ChatOllama(
        model=s.ollama_llm_model,
        base_url=s.ollama_base_url,
        temperature=0.0,
        num_predict=1000,
    )
    judge_emb = OllamaEmbeddings(
        model=s.ollama_embedding_model,
        base_url=s.ollama_base_url,
    )
    print(f"  Judge: Ollama {s.ollama_llm_model}")

# ============================================================
# Step 3: 用 RAGAS 评估（兼容 0.2.x 和 0.4.x API）
# ============================================================
print()
print("[Step 3] 运行 RAGAS 评估...")

try:
    from ragas import evaluate
    from ragas.metrics import (
        faithfulness, answer_relevancy,
        context_precision, context_recall,
    )
    from datasets import Dataset

    dataset = Dataset.from_dict({
        "question": [r["question"] for r in records],
        "answer": [r["answer"] for r in records],
        "contexts": [r["contexts"] for r in records],
        "ground_truth": [r["ground_truth"] for r in records],
    })

    # 包装 judge
    try:
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        judge_llm_wrapped = LangchainLLMWrapper(judge_llm)
        judge_emb_wrapped = LangchainEmbeddingsWrapper(judge_emb)
    except Exception:
        judge_llm_wrapped = judge_llm
        judge_emb_wrapped = judge_emb

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=judge_llm_wrapped,
        embeddings=judge_emb_wrapped,
    )

    # 提取结果
    df = result.to_pandas()
    summary = {}
    for col in ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]:
        if col in df.columns:
            summary[col] = float(df[col].mean())

    print()
    print("=" * 70)
    print("RAGAS 评估结果")
    print("=" * 70)
    for k, v in summary.items():
        print(f"  {k:<22} = {v:.4f}")
    print("=" * 70)

    # 保存
    out = {
        "timestamp": datetime.now().isoformat(),
        "judge": "deepseek" if use_cloud_judge else "ollama",
        "n_samples": len(records),
        "metrics": summary,
        "per_question": df.to_dict(orient="records"),
    }
    with open("data/ragas/result.json", "w", encoding="utf-8", newline="
") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=str)
    print(f"[OK] 结果 -> data/ragas/result.json")

except Exception as e:
    import traceback
    print("[ERR] RAGAS 评估失败:")
    traceback.print_exc()

    # 降级：手工简单指标
    print()
    print("[降级] 手工简单指标：")
    faithfulness_proxy = sum(1 for r in records if r["answer"] and r["contexts"]) / len(records)
    has_answer = sum(1 for r in records if len(r["answer"]) > 5) / len(records)
    print(f"  answer_rate          = {has_answer:.4f}")
    print(f"  has_context_rate     = {faithfulness_proxy:.4f}")
