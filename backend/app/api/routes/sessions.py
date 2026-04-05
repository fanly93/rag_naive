from typing import Optional

from fastapi import APIRouter, HTTPException, status

from app.schemas.common import ApiResponse
from app.schemas.knowledge_base import KnowledgeBase
from app.schemas.message import SessionMessageListData
from app.schemas.session import Session, SessionCreateRequest, SessionDeleteData, SessionListData
from app.services.knowledge_base_service import knowledge_base_service
from app.services.message_service import message_service
from app.services.session_service import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=ApiResponse[SessionListData])
def list_sessions() -> ApiResponse[SessionListData]:
    items = session_service.list_sessions()
    return ApiResponse(data=SessionListData(items=items))


@router.post("", response_model=ApiResponse[Session], status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreateRequest) -> ApiResponse[Session]:
    created = session_service.create_session(payload)
    return ApiResponse(data=created)


@router.delete("/{session_id}", response_model=ApiResponse[SessionDeleteData])
def delete_session(session_id: str) -> ApiResponse[SessionDeleteData]:
    deleted = session_service.delete_session(session_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "session not found", "data": {"session_id": session_id}},
        )
    return ApiResponse(data=SessionDeleteData(session_id=session_id), message="deleted")


@router.get("/{session_id}/knowledge-base", response_model=ApiResponse[Optional[KnowledgeBase]])
def get_session_knowledge_base(session_id: str) -> ApiResponse[Optional[KnowledgeBase]]:
    session = session_service.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "session not found", "data": {"session_id": session_id}},
        )

    if not session.knowledge_base_id:
        return ApiResponse(data=None)

    kb = knowledge_base_service.get_knowledge_base(session.knowledge_base_id)
    if kb is None:
        return ApiResponse(data=None)
    return ApiResponse(data=kb)


@router.get("/{session_id}/messages", response_model=ApiResponse[SessionMessageListData])
def list_session_messages(session_id: str) -> ApiResponse[SessionMessageListData]:
    if not session_service.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "session not found", "data": {"session_id": session_id}},
        )
    items = message_service.list_messages(session_id=session_id)
    return ApiResponse(data=SessionMessageListData(items=items))
