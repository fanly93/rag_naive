from datetime import datetime
from typing import Literal
from typing import Optional

from pydantic import BaseModel, Field


class KBFile(BaseModel):
    id: str
    filename: str
    size: Optional[int] = None
    mime_type: Optional[str] = None
    status: Literal["uploaded", "indexing", "ready", "failed"] = "uploaded"
    uploaded_at: datetime


class KnowledgeBase(BaseModel):
    id: str
    name: str
    chunk_size: int = Field(ge=256, le=4096)
    chunk_overlap: int = Field(ge=0, le=512)
    status: Literal["empty", "building", "ready", "failed"] = "building"
    files: list[KBFile]
    created_at: datetime
    updated_at: datetime


class KnowledgeBaseCreateAcceptedData(BaseModel):
    knowledge_base_id: str
    task_id: str
    status: Literal["building"] = "building"


class KnowledgeBaseFileAppendData(BaseModel):
    knowledge_base_id: str
    task_id: str
    status: Literal["building"] = "building"


class KnowledgeBaseDeleteData(BaseModel):
    knowledge_base_id: str


class KnowledgeBaseFileDeleteData(BaseModel):
    knowledge_base_id: str
    file_id: str
    remaining_file_count: int
