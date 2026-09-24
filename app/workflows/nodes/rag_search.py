
from __future__ import annotations
from typing import Dict, List

from app.config.settings import get_settings
from app.rag.retriever import HybridRetriever
from app.rag.reranker import rerank
from app.workflows.state import AgentState

_RETRIEVER: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = HybridRetriever()
    return _RETRIEVER


def reset_retriever() -> None:
    global _RETRIEVER
    _RETRIEVER = None


SYNONYMS = {
    "报警": ["报警", "告警", "异常", "故障"],
    "排查": ["排查", "检查", "处理", "怎么修"],
    "重启": ["重启", "复位", "重新启动"],
}


def rewrite_query(q: str) -> str:
    tokens = [q]
    for key, syns in SYNONYMS.items():
        if key in q:
            tokens.extend([s for s in syns if s != key])
    return " ".join(tokens)


def rag_search_node(state: AgentState) -> AgentState:
    s = get_settings()
    query = state.get("user_input", "")
    rewritten = rewrite_query(query)

    retriever = get_retriever()
    hits = retriever.search_hybrid(rewritten, k=s.top_k_retrieve)
    child_ids = [cid for cid, _ in hits]
    candidates = retriever.fetch_chunks(child_ids)

    parents = retriever.expand_to_parents(child_ids)
    seen = {c["chunk_id"] for c in candidates}
    pool = candidates + [p for p in parents if p["chunk_id"] not in seen]

    reranked = rerank(rewritten, pool, top_k=s.top_k_rerank)

    if not reranked:
        return {**state, "retrieved": [], "confidence": 0.0, "query_rewritten": rewritten}

    top_score = reranked[0].get("rerank_score", 0.0)
    confidence = max(0.0, min(1.0, float(top_score)))

    return {
        **state,
        "query_rewritten": rewritten,
        "retrieved": reranked,
        "confidence": confidence,
    }
