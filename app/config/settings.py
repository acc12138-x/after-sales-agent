
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

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_embedding_model: str = "bge-m3:latest"
    ollama_llm_model: str = "qwen2.5-1.5b:latest"

    chroma_persist_dir: str = "./data/chroma"
    chroma_collection: str = "knowledge_base"

    chunk_size: int = 512
    chunk_overlap: int = 64
    top_k_retrieve: int = 20
    top_k_rerank: int = 5
    rrf_k: int = 60

    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    redis_db: int = 0

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "agent"
    mysql_password: str = "agent_password"
    mysql_database: str = "after_sales_agent"

    llm_router_mode: str = "hybrid"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"


@lru_cache
def get_settings() -> Settings:
    return Settings()
