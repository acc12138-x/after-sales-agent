
"""基于 bge-m3 嵌入余弦相似度的轻量重排。"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from app.rag.embedding import embed_query, embed_texts


def _cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) + 1e-9
    return float(a @ b / denom)


def rerank(query: str, candidates: List[Dict], top_k: int = 5) -> List[Dict]:
    if not candidates:
        return []

    qv = embed_query(query)
    texts = [c["text"] for c in candidates]
    cvs = embed_texts(texts)

    scored = [(_cosine(qv, cv), c) for cv, c in zip(cvs, candidates)]
    scored.sort(key=lambda x: -x[0])

    out: List[Dict] = []
    for score, c in scored[:top_k]:
        c = dict(c)
        c["rerank_score"] = score
        out.append(c)
    return out
