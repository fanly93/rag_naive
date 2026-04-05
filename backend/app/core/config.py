from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Agentic RAG Backend"
    api_prefix: str = "/api/v1"
    upload_root: str = str(Path(__file__).resolve().parents[2] / "data" / "uploads")
    milvus_url: str = str(Path(__file__).resolve().parents[2] / "data" / "milvus.db")
    embedding_dim: int = 1024
    dashscope_api_key: str = ""
    embedding_model_name: str = "text-embedding-v4"
    rerank_model_name: str = "qwen3-rerank"
    rrf_k: int = Field(default=60, ge=1, le=1000)
    rrf_vector_weight: float = Field(default=0.5, gt=0.0, lt=1.0)
    rrf_bm25_weight: float = Field(default=0.5, gt=0.0, lt=1.0)
    # JSON string, e.g. {".pdf":{"vector":0.35,"bm25":0.65},".md":{"vector":0.7,"bm25":0.3}}
    rrf_file_type_weights_json: str = ""
    # Phase4 used simulation for state-machine verification; default to real build now.
    task_simulate_build: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
