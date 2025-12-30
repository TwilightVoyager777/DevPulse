from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://devpulse:devpulse@localhost:5432/devpulse"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_group_id: str = "ai-worker"
    kafka_auto_offset_reset: str = "earliest"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_max_tokens: int = 1024

    # Embedding
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384

    # Chunking
    chunk_size_tokens: int = 512
    chunk_overlap_tokens: int = 64
    chunk_min_chars: int = 100

    # Retrieval
    retrieval_top_k: int = 5
    bm25_candidate_k: int = 20
    vector_candidate_k: int = 20
    rrf_k: int = 60

    # App
    log_level: str = "INFO"
    workers: int = 1

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
