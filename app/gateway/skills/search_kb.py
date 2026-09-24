
"""OpenClaw Skill：知识库检索。"""
from __future__ import annotations
from typing import Any, Dict

from app.config.settings import get_settings
from app.rag.retriever import HybridRetriever
from app.rag.reranker import rerank

_RETRIEVER = None


def _get_retriever():
    global _RETRIEVER
    if _RETRIEVER is None:
        _RETRIEVER = HybridRetriever()
    return _RETRIEVER


def search_kb(query: str, top_k: int = 5) -> Dict[str, Any]:
    s = get_settings()
    r = _get_retriever()
    hits = r.search_hybrid(query, k=s.top_k_retrieve)
    ids = [cid for cid, _ in hits]
    candidates = r.fetch_chunks(ids)
    parents = r.expand_to_parents(ids)
    seen = {c["chunk_id"] for c in candidates}
    pool = candidates + [p for p in parents if p["chunk_id"] not in seen]
    reranked = rerank(query, pool, top_k=top_k)
    return {
        "query": query,
        "hits": [
            {
                "chunk_id": c["chunk_id"],
                "text": c["text"][:300],
                "source": c["metadata"].get("source", ""),
                "score": c.get("rerank_score", 0.0),
            }
            for c in reranked
        ],
    }


SCHEMA = {
    "name": "search_kb",
    "description": "在企业售后知识库中检索相关信息",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "检索关键词"},
            "top_k": {"type": "integer", "default": 5},
        },
        "required": ["query"],
    },
}
