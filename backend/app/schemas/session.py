from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Session(BaseModel):
    id: str
    title: str
    updated_at: datetime
    is_draft: bool
    knowledge_base_id: Optional[str] = None


class SessionCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    is_draft: bool = True


class SessionListData(BaseModel):
    items: list[Session]


class SessionDeleteData(BaseModel):
    session_id: str


class SessionKnowledgeBaseBindData(BaseModel):
    session_id: str
    knowledge_base_id: Optional[str]
