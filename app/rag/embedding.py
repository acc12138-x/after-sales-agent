
"""Ollama bge-m3 嵌入封装。"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from langchain_ollama import OllamaEmbeddings

from app.config.settings import get_settings


@lru_cache
def get_embeddings() -> OllamaEmbeddings:
    s = get_settings()
    return OllamaEmbeddings(
        model=s.ollama_embedding_model,
        base_url=s.ollama_base_url,
    )


def embed_texts(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    return get_embeddings().embed_documents(texts)


def embed_query(text: str) -> List[float]:
    return get_embeddings().embed_query(text)
