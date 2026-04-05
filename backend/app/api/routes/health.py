from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.common import ApiResponse

router = APIRouter(prefix="/health", tags=["health"])


class HealthData(BaseModel):
    status: Literal["ok"] = "ok"


@router.get("", response_model=ApiResponse[HealthData])
def health_check() -> ApiResponse[HealthData]:
    return ApiResponse(data=HealthData())
