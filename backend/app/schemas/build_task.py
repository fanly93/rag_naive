from datetime import datetime
from typing import Literal
from typing import Optional

from pydantic import BaseModel, Field


BuildStage = Literal["uploaded", "chunking", "indexing", "vectorizing", "done", "failed"]


class BuildTask(BaseModel):
    task_id: str
    knowledge_base_id: str
    stage: BuildStage
    progress: int = Field(ge=0, le=100)
    error_message: Optional[str] = None
    updated_at: datetime


class BuildTaskRetryData(BaseModel):
    task_id: str
    stage: BuildStage
    progress: int = Field(ge=0, le=100)
