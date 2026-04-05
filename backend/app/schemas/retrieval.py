from typing import Literal

from pydantic import BaseModel, Field


RetrieveMode = Literal["vector", "hybrid", "hybrid_rerank"]
RetrieveChannel = Literal["vector", "bm25", "rerank"]


class RetrievalChunk(BaseModel):
    chunk_id: str
    title: str
    source: str
    score: float
    content: str
    channel: RetrieveChannel
    hit_mode: str


class RetrieveTestRequest(BaseModel):
    query: str = Field(min_length=1)
    mode: RetrieveMode
    top_n: int = Field(ge=1)
    top_k: int = Field(ge=1)


class RetrieveTestData(BaseModel):
    query: str
    initial_results: list[RetrievalChunk]
    final_results: list[RetrievalChunk]
