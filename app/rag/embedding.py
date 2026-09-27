"""嵌入封装：支持 Ollama bge-m3 / DashScope text-embedding-v3 切换。

两种模型维度都是 1024，可无缝互换，不需重建 Chroma。
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from app.config.settings import get_settings


@lru_cache
def get_embeddings():
    s = get_settings()

    if s.embedding_provider == "dashscope" and s.dashscope_api_key:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=s.dashscope_embedding_model,
            api_key=s.dashscope_api_key,
            base_url=s.dashscope_base_url,
            check_embedding_ctx_length=False,
        )

    from langchain_ollama import OllamaEmbeddings
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
