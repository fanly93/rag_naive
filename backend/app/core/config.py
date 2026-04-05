from functools import lru_cache
from pathlib import Path

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
    embedding_dim: int = 256
    # Phase4 used simulation for state-machine verification; default to real build now.
    task_simulate_build: bool = False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
