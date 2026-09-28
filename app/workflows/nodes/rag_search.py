
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


import re as _re

# 从 query 中提取可能的"实体词"（型号、错误码、品牌）
ENTITY_PATTERNS = [
    _re.compile(r"\b[A-Z]{1,4}\d{2,5}\b"),    # E102 / XY200 / ABC123
    _re.compile(r"\b[A-Za-z]{3,}\b"),           # 英文词
]


def _extract_entities(text: str) -> list:
    entities = []
    for pat in ENTITY_PATTERNS:
        for m in pat.finditer(text):
            e = m.group(0)
            if len(e) >= 2:
                entities.append(e.lower())
    return entities


def _entity_hit(query: str, chunks: list) -> bool:
    """query 里的实体词是否出现在 Top 结果里。"""
    entities = _extract_entities(query)
    if not entities:
        return False
    combined = " ".join((c.get("text", "") or "").lower() for c in chunks[:3])
    for e in entities:
        if e in combined:
            return True
    return False


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
        return {
            **state,
            "retrieved": [],
            "confidence": 0.0,
            "query_rewritten": rewritten,
            "flow_status": "rejected",
        }

    top_score = float(reranked[0].get("rerank_score", 0.0))
    confidence = max(0.0, min(1.0, top_score))

    # ============ 相关性阈值过滤 + 实体词覆盖 ============
    # 1. 分数 >= 阈值 -> 通过
    # 2. 或 query 里的实体词（型号/故障码）出现在 Top 结果 -> 通过
    # 3. 否则 -> 拒答
    is_relevant = (top_score >= s.min_relevance_score) or _entity_hit(rewritten, reranked)

    if not is_relevant:
        return {
            **state,
            "query_rewritten": rewritten,
            "retrieved": [],           # 清空检索结果
            "confidence": confidence,
            "flow_status": "rejected",  # 标记为拒答
        }

    # 只保留超过阈值的结果
    reranked = [c for c in reranked if float(c.get("rerank_score", 0.0)) >= s.min_relevance_score * 0.8]

    return {
        **state,
        "query_rewritten": rewritten,
        "retrieved": reranked,
        "confidence": confidence,
    }
