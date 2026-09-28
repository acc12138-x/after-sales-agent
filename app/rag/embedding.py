"""嵌入封装：根据 base_url 自动路由到 Ollama 原生或 OpenAI 兼容。

判断规则：
- base_url 含 "11434" 或 "ollama" -> Ollama 原生
- 其他 -> OpenAI 兼容（DashScope / OpenAI / 智谱 等）
"""
from __future__ import annotations

from functools import lru_cache
from typing import List

from app.config.settings import get_settings


def _is_ollama_base(base_url: str) -> bool:
    """根据 base_url 判断是否走 Ollama 原生。"""
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
    if not texts:
        return []
    return get_embeddings().embed_documents(texts)


def embed_query(text: str) -> List[float]:
    return get_embeddings().embed_query(text)
