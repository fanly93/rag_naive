from fastapi import APIRouter, HTTPException, status

from app.schemas.common import ApiResponse
from app.schemas.retrieval import RetrievalChunk
from app.services.knowledge_base_service import knowledge_base_service

router = APIRouter(tags=["chunks"])


def _to_retrieval_chunk(raw: dict[str, str | float]) -> RetrievalChunk:
    return RetrievalChunk(
        chunk_id=str(raw["chunk_id"]),
        title=str(raw["title"]),
        source=str(raw["source"]),
        score=float(raw["hybrid_score"]),
        content=str(raw["content"]),
        channel="vector",
        hit_mode="vector",
    )


@router.get("/chunks/{chunk_id}", response_model=ApiResponse[RetrievalChunk])
def get_chunk(chunk_id: str) -> ApiResponse[RetrievalChunk]:
    chunk = knowledge_base_service.get_chunk_detail(chunk_id)
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "chunk not found", "data": {"chunk_id": chunk_id}},
        )
    return ApiResponse(data=_to_retrieval_chunk(chunk))


@router.get("/knowledge-bases/{knowledge_base_id}/chunks/{chunk_id}", response_model=ApiResponse[RetrievalChunk])
def get_chunk_in_kb(knowledge_base_id: str, chunk_id: str) -> ApiResponse[RetrievalChunk]:
    chunk = knowledge_base_service.get_chunk_detail_in_kb(knowledge_base_id=knowledge_base_id, chunk_id=chunk_id)
    if chunk is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": 1002,
                "message": "chunk not found in knowledge base",
                "data": {"knowledge_base_id": knowledge_base_id, "chunk_id": chunk_id},
            },
        )
    return ApiResponse(data=_to_retrieval_chunk(chunk))
