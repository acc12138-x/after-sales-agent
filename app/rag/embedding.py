"""嵌入封装：根据 base_url 自动路由到 Ollama 原生或 OpenAI 兼容。

关键：DashScope 等云端 embedding 有 batch size 限制（一般 10 条/次），
所以 embed_texts 自动分批调用。
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List

from app.config.settings import get_settings


# 单批最大条数（DashScope text-embedding 系列限制 10）
EMBED_BATCH_SIZE = int(os.environ.get("EMBED_BATCH_SIZE", "10"))


def _is_ollama_base(base_url: str) -> bool:
    if not base_url:
        return True
    return "11434" in base_url or "ollama" in base_url.lower()


@lru_cache
def get_embeddings():
    s = get_settings()
    base_url = s.embedding_base_url or s.ollama_base_url
    model = s.embedding_model or s.ollama_embedding_model

    if _is_ollama_base(base_url):
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=model,
            base_url=base_url,
        )

    from langchain_openai import OpenAIEmbeddings
    api_key = s.embedding_api_key or "sk-dummy"
    return OpenAIEmbeddings(
        model=model,
        api_key=api_key,
        base_url=base_url,
        check_embedding_ctx_length=False,
    )


def embed_texts(texts: List[str]) -> List[List[float]]:
    """分批调用，兼容云端 batch size 限制。"""
    if not texts:
        return []

    # 本地 Ollama 无 batch 限制，一次性传
    s = get_settings()
    base_url = s.embedding_base_url or s.ollama_base_url
    if _is_ollama_base(base_url):
        return get_embeddings().embed_documents(texts)

    # 云端：分批
    all_vecs: List[List[float]] = []
    total = len(texts)
    for i in range(0, total, EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        vecs = get_embeddings().embed_documents(batch)
        all_vecs.extend(vecs)
    return all_vecs


def embed_query(text: str) -> List[float]:
    return get_embeddings().embed_query(text)
