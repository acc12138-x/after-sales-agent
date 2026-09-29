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
    # LLM锛堥€氱敤 OpenAI 鍏煎锛?    # ============================================================
    # provider 鏍囪瘑锛歰llama_native / deepseek / dashscope_llm / ...
    # - ollama_native 璧?langchain-ollama
    # - 鍏朵粬閮借蛋 OpenAI 鍏煎鎺ュ彛
    llm_provider: str = "ollama_native"
    llm_base_url: str = "http://127.0.0.1:11434"
    llm_model: str = "qwen2.5-1.5b:latest"
    llm_api_key: str = ""

    # ============================================================
    # Embedding锛堥€氱敤 OpenAI 鍏煎锛?    # ============================================================
    embedding_provider: str = "ollama_native"
    embedding_base_url: str = "http://127.0.0.1:11434"
    embedding_model: str = "bge-m3:latest"
    embedding_api_key: str = ""

    # ============================================================
    # Ollama 鍘熺敓妯″紡涓撶敤锛堝吋瀹逛繚鐣欙級
    # ============================================================
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_llm_model: str = "qwen2.5-1.5b:latest"
    ollama_embedding_model: str = "bge-m3:latest"

    # ============================================================
    # Chroma 鍚戦噺搴?    # ============================================================
    # embedded: 鏈湴鎸佷箙鍖栫洰褰?    # http:     杩炴帴 Chroma 鏈嶅姟
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
    # 鐩稿叧鎬ч槇鍊硷細閲嶆帓鍚庢渶楂樺垎浣庝簬姝ゅ€?-> 鍒ゅ畾涓?鏃犵浉鍏崇煡璇?
    min_relevance_score: float = 0.55
    # 浣欏鸡鐩镐技搴﹂槇鍊硷細鍚戦噺鍙洖鐨勫師濮嬪垎鏁颁笅闄?    min_vector_score: float = 0.3

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

    # ============================================================
    # OpenClaw 缃戝叧
    # ============================================================
    openclaw_enabled: bool = True
    openclaw_gateway_url: str = "http://127.0.0.1:18000"
    openclaw_api_key: str = "local-rag-key"
    openclaw_feishu_app_id: str = ""
    openclaw_feishu_app_secret: str = ""

    # 鍏煎鏃у瓧娈?    # HITL 超时（秒）
    hitl_timeout_seconds: int = 1800

    # ============================================================
    # JWT
    # ============================================================
    # 数据库模式：mysql / sqlite
    # 缓存后端：sqlite / redis
    cache_backend: str = "sqlite"
    redis_url: str = "redis://127.0.0.1:6379/0"

    db_mode: str = "sqlite"

    jwt_secret: str = "CHANGE_ME_IN_ENV"
    jwt_expire_hours: int = 168

    llm_router_mode: str = "hybrid"


@lru_cache
def get_settings() -> Settings:
    return Settings()

