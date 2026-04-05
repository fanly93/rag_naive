from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalChunk


class SessionMessage(BaseModel):
    id: str
    session_id: str
    role: Literal["user", "assistant"]
    content: str
    is_error: bool = False
    created_at: datetime
    top_n_citations: list[RetrievalChunk] = Field(default_factory=list)
    top_k_citations: list[RetrievalChunk] = Field(default_factory=list)


class SessionMessageListData(BaseModel):
    items: list[SessionMessage]
