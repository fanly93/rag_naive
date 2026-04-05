from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalChunk
from app.schemas.retrieval import RetrieveMode

ChatProvider = Literal["deepseek", "openai", "dashscope"]


class ChatCompletionRequest(BaseModel):
    session_id: str
    query: str = Field(min_length=1)
    mode: RetrieveMode | Literal["none"] = "hybrid_rerank"
    top_n: int = Field(default=20, ge=1)
    top_k: int = Field(default=3, ge=1)
    knowledge_base_id: str | None = None
    provider: ChatProvider | None = None
    model: str | None = None


class ChatCompletionData(BaseModel):
    answer: str
    provider: ChatProvider
    model: str
    mode: RetrieveMode | Literal["none"]
    top_n: int
    top_k: int
    initial_results: list[RetrievalChunk]
    final_results: list[RetrievalChunk]
