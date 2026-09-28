from functools import lru_cache
import os

os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost,::1")

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Enterprise After-Sales Knowledge Base Agent Platform"
    app_env: str = "development"
    app_port: int = 8000
    app_debug: bool = True
    log_level: str = "DEBUG"

    # ============================================================
    # LLM（通用 OpenAI 兼容）
    # ============================================================
    # provider 标识：ollama_native / deepseek / dashscope_llm / ...
    # - ollama_native 走 langchain-ollama
    # - 其他都走 OpenAI 兼容接口
    llm_provider: str = "ollama_native"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5-1.5b:latest"
    llm_api_key: str = ""

    # ============================================================
    # Embedding（通用 OpenAI 兼容）
    # ============================================================
    embedding_provider: str = "ollama_native"
    embedding_base_url: str = "http://127.0.0.1:11434"
    embedding_model: str = "bge-m3:latest"
    embedding_api_key: str = ""

    # ============================================================
    # Ollama 原生模式专用（兼容保留）
    # ============================================================
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_llm_model: str = "qwen2.5-1.5b:latest"
    ollama_embedding_model: str = "bge-m3:latest"

    # ============================================================
    # Chroma 向量库
    # ============================================================
    # embedded: 本地持久化目录
    # http:     连接 Chroma 服务
    chroma_mode: str = "embedded"
    chroma_host: str = "127.0.0.1"
    chroma_port: int = 8001
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection: str = "knowledge_base"

    # ============================================================
    # RAG
    # ============================================================
    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_retrieve: int = 20
    top_k_rerank: int = 5
    rrf_k: int = 60
    # 相关性阈值：重排后最高分低于此值 -> 判定为"无相关知识"
    min_relevance_score: float = 0.55
    # 余弦相似度阈值：向量召回的原始分数下限
    min_vector_score: float = 0.3

    # ============================================================
    # Redis
    # ============================================================
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    # ============================================================
    # MySQL
    # ============================================================
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3307
    mysql_user: str = "agent"
    mysql_password: str = "agent_password"
    mysql_database: str = "after_sales_agent"

    # 兼容旧字段
    llm_router_mode: str = "hybrid"


@lru_cache
def get_settings() -> Settings:
    return Settings()
