from fastapi import APIRouter, HTTPException, status

from app.schemas.build_task import BuildTask
from app.schemas.build_task import BuildTaskRetryData
from app.schemas.common import ApiResponse
from app.services.build_orchestrator_service import build_orchestrator_service

router = APIRouter(prefix="/build-tasks", tags=["build-tasks"])


@router.get("/{task_id}", response_model=ApiResponse[BuildTask])
def get_build_task(task_id: str) -> ApiResponse[BuildTask]:
    task = build_orchestrator_service.get_task(task_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "build task not found", "data": {"task_id": task_id}},
        )
    return ApiResponse(data=task)


@router.post("/{task_id}/retry", response_model=ApiResponse[BuildTaskRetryData])
def retry_build_task(task_id: str) -> ApiResponse[BuildTaskRetryData]:
    try:
        task = build_orchestrator_service.retry_task(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": 1003, "message": "task is not in failed state", "data": {"task_id": task_id}},
        )
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "build task not found", "data": {"task_id": task_id}},
        )

    return ApiResponse(
        message="accepted",
        data=BuildTaskRetryData(task_id=task.task_id, stage=task.stage, progress=task.progress),
    )
