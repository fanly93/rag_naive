from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.common import ApiResponse
from app.schemas.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseCreateAcceptedData,
    KnowledgeBaseDeleteData,
    KnowledgeBaseFileAppendData,
    KnowledgeBaseFileDeleteData,
)
from app.schemas.retrieval import RetrieveTestData
from app.schemas.retrieval import RetrieveTestRequest
from app.services.build_orchestrator_service import build_orchestrator_service
from app.services.knowledge_base_service import knowledge_base_service
from app.services.rag_ingest_service import rag_ingest_service
from app.services.retrieval_service import retrieval_service
from app.services.session_service import session_service

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])

ALLOWED_FILE_SUFFIXES = {".txt", ".md", ".pdf"}


def _validate_file(file: UploadFile) -> None:
    filename = file.filename or ""
    if "." not in filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 2001, "message": "file extension is required", "data": {"filename": filename}},
        )
    suffix = f".{filename.rsplit('.', 1)[1].lower()}"
    if suffix not in ALLOWED_FILE_SUFFIXES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 2001, "message": "unsupported file type", "data": {"filename": filename}},
        )


@router.post("", response_model=ApiResponse[KnowledgeBaseCreateAcceptedData], status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    session_id: str = Form(...),
    name: str = Form(...),
    chunk_size: int = Form(...),
    chunk_overlap: int = Form(...),
    file: UploadFile = File(...),
) -> ApiResponse[KnowledgeBaseCreateAcceptedData]:
    if not session_service.session_exists(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "session not found", "data": {"session_id": session_id}},
        )
    if not (2 <= len(name.strip()) <= 50):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 1001, "message": "name must be 2-50 chars", "data": {"name": name}},
        )
    if not (256 <= chunk_size <= 4096):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 1001, "message": "invalid chunk_size", "data": {"chunk_size": chunk_size}},
        )
    if not (0 <= chunk_overlap <= 512 and chunk_overlap < chunk_size):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": 1001,
                "message": "invalid chunk_overlap",
                "data": {"chunk_overlap": chunk_overlap, "chunk_size": chunk_size},
            },
        )

    _validate_file(file)
    file_content = await file.read()
    kb = knowledge_base_service.create_knowledge_base(
        name=name.strip(),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        file_name=file.filename or "unknown",
        file_size=len(file_content),
        mime_type=file.content_type,
    )
    file_id = kb.files[0].id
    file_path = rag_ingest_service.save_file(
        session_id=session_id,
        knowledge_base_id=kb.id,
        file_id=file_id,
        filename=file.filename or "unknown",
        content=file_content,
    )
    knowledge_base_service.set_file_path(file_id=file_id, file_path=str(file_path))
    task = build_orchestrator_service.enqueue_create_build(
        session_id=session_id,
        knowledge_base_id=kb.id,
        file_id=file_id,
        should_fail=("fail" in (file.filename or "").lower() or "失败" in (file.filename or "")),
    )

    return ApiResponse(
        message="accepted",
        data=KnowledgeBaseCreateAcceptedData(knowledge_base_id=kb.id, task_id=task.task_id),
    )


@router.post("/{knowledge_base_id}/files", response_model=ApiResponse[KnowledgeBaseFileAppendData])
async def append_file(
    knowledge_base_id: str,
    file: UploadFile = File(...),
) -> ApiResponse[KnowledgeBaseFileAppendData]:
    _validate_file(file)
    file_content = await file.read()

    file_id = knowledge_base_service.append_file(
        knowledge_base_id=knowledge_base_id,
        file_name=file.filename or "unknown",
        file_size=len(file_content),
        mime_type=file.content_type,
    )
    if file_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "knowledge base not found", "data": {"knowledge_base_id": knowledge_base_id}},
        )

    kb = knowledge_base_service.get_knowledge_base(knowledge_base_id)
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "knowledge base not found", "data": {"knowledge_base_id": knowledge_base_id}},
        )
    session_candidates = [item.id for item in session_service.list_sessions() if item.knowledge_base_id == knowledge_base_id]
    session_id = session_candidates[0] if session_candidates else "unknown_session"

    file_path = rag_ingest_service.save_file(
        session_id=session_id,
        knowledge_base_id=knowledge_base_id,
        file_id=file_id,
        filename=file.filename or "unknown",
        content=file_content,
    )
    knowledge_base_service.set_file_path(file_id=file_id, file_path=str(file_path))
    task = build_orchestrator_service.enqueue_append_build(
        knowledge_base_id=knowledge_base_id,
        file_id=file_id,
        should_fail=("fail" in (file.filename or "").lower() or "失败" in (file.filename or "")),
    )

    return ApiResponse(
        data=KnowledgeBaseFileAppendData(knowledge_base_id=knowledge_base_id, task_id=task.task_id),
    )


@router.delete("/{knowledge_base_id}", response_model=ApiResponse[KnowledgeBaseDeleteData])
def delete_knowledge_base(knowledge_base_id: str) -> ApiResponse[KnowledgeBaseDeleteData]:
    deleted = knowledge_base_service.delete_knowledge_base(knowledge_base_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "knowledge base not found", "data": {"knowledge_base_id": knowledge_base_id}},
        )

    # Unbind from any session using this knowledge base.
    for session in session_service.list_sessions():
        if session.knowledge_base_id == knowledge_base_id:
            session_service.bind_knowledge_base(session_id=session.id, knowledge_base_id=None)

    return ApiResponse(message="deleted", data=KnowledgeBaseDeleteData(knowledge_base_id=knowledge_base_id))


@router.delete("/{knowledge_base_id}/files/{file_id}", response_model=ApiResponse[KnowledgeBaseFileDeleteData])
def delete_file(knowledge_base_id: str, file_id: str) -> ApiResponse[KnowledgeBaseFileDeleteData]:
    remaining = knowledge_base_service.delete_file(knowledge_base_id=knowledge_base_id, file_id=file_id)
    if remaining is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 1002,
                "message": "knowledge base or file not found",
                "data": {"knowledge_base_id": knowledge_base_id, "file_id": file_id},
            },
        )

    return ApiResponse(
        message="deleted",
        data=KnowledgeBaseFileDeleteData(
            knowledge_base_id=knowledge_base_id,
            file_id=file_id,
            remaining_file_count=remaining,
        ),
    )


@router.get("/{knowledge_base_id}", response_model=ApiResponse[KnowledgeBase])
def get_knowledge_base(knowledge_base_id: str) -> ApiResponse[KnowledgeBase]:
    kb = knowledge_base_service.get_knowledge_base(knowledge_base_id)
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "knowledge base not found", "data": {"knowledge_base_id": knowledge_base_id}},
        )
    return ApiResponse(data=kb)


@router.post("/{knowledge_base_id}/retrieve-test", response_model=ApiResponse[RetrieveTestData])
def retrieve_test(knowledge_base_id: str, payload: RetrieveTestRequest) -> ApiResponse[RetrieveTestData]:
    kb = knowledge_base_service.get_knowledge_base(knowledge_base_id)
    if kb is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "knowledge base not found", "data": {"knowledge_base_id": knowledge_base_id}},
        )
    if payload.top_k > payload.top_n:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 1001, "message": "top_k must be <= top_n", "data": {"top_n": payload.top_n, "top_k": payload.top_k}},
        )

    try:
        file_paths = knowledge_base_service.get_file_paths(knowledge_base_id)
        initial, final, all_chunks = retrieval_service.retrieve(
            kb=kb,
            file_paths=file_paths,
            query=payload.query,
            mode=payload.mode,
            top_n=payload.top_n,
            top_k=payload.top_k,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 3001, "message": "retrieve test failed", "data": {"error": str(exc)}},
        )

    # Persist detail cache for both right panel and middle citation popups.
    knowledge_base_service.set_chunk_details(knowledge_base_id=knowledge_base_id, chunks=all_chunks)

    return ApiResponse(data=RetrieveTestData(query=payload.query, initial_results=initial, final_results=final))
