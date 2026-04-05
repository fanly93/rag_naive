from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Agentic RAG Backend"
    api_prefix: str = "/api/v1"
    default_chat_provider: str = "deepseek"
    model: str = "deepseek-chat"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_chat_model: str = "deepseek-chat"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    upload_root: str = str(Path(__file__).resolve().parents[2] / "data" / "uploads")
    milvus_url: str = str(Path(__file__).resolve().parents[2] / "data" / "milvus.db")
    embedding_dim: int = 1024
    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    dashscope_chat_model: str = "qwen-plus"
    embedding_model_name: str = "text-embedding-v4"
    rerank_model_name: str = "qwen3-rerank"
    rrf_k: int = Field(default=60, ge=1, le=1000)
    rrf_vector_weight: float = Field(default=0.5, gt=0.0, lt=1.0)
    rrf_bm25_weight: float = Field(default=0.5, gt=0.0, lt=1.0)
    # JSON string, e.g. {".pdf":{"vector":0.35,"bm25":0.65},".md":{"vector":0.7,"bm25":0.3}}
    rrf_file_type_weights_json: str = ""
    # MySQL config for session persistence migration.
    # Prefer MYSQL_* variables; keep legacy host/user/password/database compatibility.
    mysql_host: str = Field(default="127.0.0.1", validation_alias=AliasChoices("MYSQL_HOST", "host"))
    mysql_port: int = Field(default=3306, validation_alias=AliasChoices("MYSQL_PORT", "port"))
    mysql_user: str = Field(default="root", validation_alias=AliasChoices("MYSQL_USER", "user"))
    mysql_password: str = Field(default="", validation_alias=AliasChoices("MYSQL_PASSWORD", "password"))
    mysql_database: str = Field(default="agentic_rag", validation_alias=AliasChoices("MYSQL_DATABASE", "database"))
    mysql_charset: str = Field(default="utf8mb4", validation_alias=AliasChoices("MYSQL_CHARSET"))
    # Phase4 used simulation for state-machine verification; default to real build now.
    task_simulate_build: bool = False

    @property
    def mysql_sqlalchemy_url(self) -> str:
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset={self.mysql_charset}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
