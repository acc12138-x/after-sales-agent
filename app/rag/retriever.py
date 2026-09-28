"""BM25 + 向量 混合召回（支持 Chroma embedded / http 两种模式）。"""
from __future__ import annotations

import os
from typing import Dict, List, Tuple

import chromadb
import jieba
from rank_bm25 import BM25Okapi

from app.config.settings import get_settings
from app.rag.chunking import Chunk
from app.rag.embedding import embed_query, embed_texts


def _make_chroma_client():
    """根据配置创建 Chroma 客户端。"""
    s = get_settings()
    if s.chroma_mode == "http":
        return chromadb.HttpClient(host=s.chroma_host, port=s.chroma_port)
    else:
        os.makedirs(s.chroma_persist_dir, exist_ok=True)
        return chromadb.PersistentClient(path=s.chroma_persist_dir)


class HybridRetriever:
    def __init__(self, persist_dir: str | None = None):
        s = get_settings()
        self.settings = s

        # HTTP 模式忽略 persist_dir
        if s.chroma_mode == "embedded" and persist_dir:
            os.makedirs(persist_dir, exist_ok=True)
            self.client = chromadb.PersistentClient(path=persist_dir)
        else:
            self.client = _make_chroma_client()

        self.collection = self.client.get_or_create_collection(
            name=s.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

        self.bm25: BM25Okapi | None = None
        self.bm25_ids: List[str] = []
        self.bm25_texts: List[str] = []

    def index_chunks(self, chunks: List[Chunk]) -> None:
        if not chunks:
            return

        children = [c for c in chunks if not c.is_parent]
        parents = [c for c in chunks if c.is_parent]

        if parents:
            self.collection.upsert(
                ids=[p.chunk_id for p in parents],
                documents=[p.text for p in parents],
                metadatas=[p.metadata for p in parents],
                embeddings=embed_texts([p.text for p in parents]),
            )

        if children:
            self.collection.upsert(
                ids=[c.chunk_id for c in children],
                documents=[c.text for c in children],
                metadatas=[c.metadata for c in children],
                embeddings=embed_texts([c.text for c in children]),
            )

            # BM25 索引只加子块（每次重建）
            self.bm25_ids = [c.chunk_id for c in children]
            self.bm25_texts = [c.text for c in children]
            tokenized = [list(jieba.cut(t)) for t in self.bm25_texts]
            self.bm25 = BM25Okapi(tokenized)

    def _ensure_bm25(self) -> None:
        """BM25 索引为空时，从 Chroma 拉所有子块重建。"""
        if self.bm25 is not None and self.bm25_ids:
            return
        try:
            res = self.collection.get(include=["documents", "metadatas"])
            ids = res.get("ids", []) or []
            docs = res.get("documents", []) or []
            metas = res.get("metadatas", []) or []
            child_ids, child_texts = [], []
            for i, m in enumerate(metas):
                if m and m.get("type") == "child":
                    child_ids.append(ids[i])
                    child_texts.append(docs[i])
            if child_ids:
                self.bm25_ids = child_ids
                self.bm25_texts = child_texts
                self.bm25 = BM25Okapi([list(jieba.cut(t)) for t in child_texts])
        except Exception:
            pass

    def search_bm25(self, query: str, k: int = 20) -> List[Tuple[str, float]]:
        self._ensure_bm25()
        if self.bm25 is None or not self.bm25_ids:
            return []
        tokens = list(jieba.cut(query))
        scores = self.bm25.get_scores(tokens)
        indexed = sorted(enumerate(scores), key=lambda x: -x[1])[:k]
        return [(self.bm25_ids[i], float(sc)) for i, sc in indexed]

    def search_vector(self, query: str, k: int = 20) -> List[Tuple[str, float]]:
        qv = embed_query(query)
        res = self.collection.query(
            query_embeddings=[qv],
            n_results=k,
            include=["distances"],
        )
        ids = res.get("ids", [[]])[0]
        distances = res.get("distances", [[]])[0]
        return [(i, 1.0 / (1.0 + d)) for i, d in zip(ids, distances)]

    def search_hybrid(
        self, query: str, k: int = 20, rrf_k: int | None = None,
    ) -> List[Tuple[str, float]]:
        rrf_k = rrf_k or self.settings.rrf_k
        bm25_res = self.search_bm25(query, k=k * 2)
        vec_res = self.search_vector(query, k=k * 2)

        scores: Dict[str, float] = {}
        for rank, (cid, _) in enumerate(bm25_res):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)
        for rank, (cid, _) in enumerate(vec_res):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (rrf_k + rank + 1)

        ranked = sorted(scores.items(), key=lambda x: -x[1])[:k]
        return ranked

    def fetch_chunks(self, ids: List[str]) -> List[Dict]:
        if not ids:
            return []
        res = self.collection.get(ids=ids, include=["documents", "metadatas"])
        out = []
        for i, cid in enumerate(res.get("ids", [])):
            out.append({
                "chunk_id": cid,
                "text": res["documents"][i],
                "metadata": res["metadatas"][i],
            })
        return out

    def expand_to_parents(self, child_ids: List[str]) -> List[Dict]:
        children = self.fetch_chunks(child_ids)
        parent_ids = list({c["metadata"].get("parent_id", "") for c in children})
        parent_ids = [p for p in parent_ids if p]
        return self.fetch_chunks(parent_ids)

    def count(self) -> int:
        try:
            return self.collection.count()
        except Exception:
            return 0
