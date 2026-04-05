import json
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatCompletionData
from app.schemas.chat import ChatCompletionRequest
from app.schemas.common import ApiResponse
from app.services.chat_service import chat_service
from app.services.knowledge_base_service import knowledge_base_service
from app.services.retrieval_service import retrieval_service
from app.services.session_service import session_service

router = APIRouter(prefix="/chat", tags=["chat"])


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/completions", response_model=ApiResponse[ChatCompletionData])
def chat_completions(payload: ChatCompletionRequest) -> ApiResponse[ChatCompletionData]:
    if not session_service.session_exists(payload.session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "session not found", "data": {"session_id": payload.session_id}},
        )
    if payload.top_k > payload.top_n:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 1001, "message": "top_k must be <= top_n", "data": {"top_n": payload.top_n, "top_k": payload.top_k}},
        )

    initial = []
    final = []
    context_chunks: list[tuple[int, str]] = []
    if payload.mode != "none":
        kb_id = payload.knowledge_base_id or session_service.get_session(payload.session_id).knowledge_base_id
        if not kb_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 1001, "message": "knowledge base is required when mode is not none", "data": {}},
            )
        kb = knowledge_base_service.get_knowledge_base(kb_id)
        if kb is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 1002, "message": "knowledge base not found", "data": {"knowledge_base_id": kb_id}},
            )
        try:
            file_paths = knowledge_base_service.get_file_paths(kb_id)
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
                detail={"code": 3001, "message": "chat retrieval failed", "data": {"error": str(exc)}},
            )

        detail_by_id: dict[str, dict[str, str | float]] = {}
        raw_by_id = {str(item["chunk_id"]): item for item in all_chunks}
        for result in initial + final:
            raw = raw_by_id.get(result.chunk_id)
            if raw is None:
                continue
            detail_by_id[result.chunk_id] = {
                "chunk_id": result.chunk_id,
                "title": result.title,
                "source": result.source,
                "score": result.score,
                "content": result.content,
                "channel": result.channel,
                "hit_mode": result.hit_mode,
                "vector_score": float(raw["vector_score"]),
                "bm25_score": float(raw["bm25_score"]),
                "hybrid_score": float(raw["hybrid_score"]),
            }
        knowledge_base_service.set_chunk_details(knowledge_base_id=kb_id, chunks=list(detail_by_id.values()))
        context_chunks = [(index + 1, item.content) for index, item in enumerate(final)]

    try:
        answer, provider, model = chat_service.complete(
            query=payload.query,
            context_chunks=context_chunks,
            provider=payload.provider,
            model=payload.model,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 4001, "message": "chat completion failed", "data": {"error": str(exc)}},
        )

    return ApiResponse(
        data=ChatCompletionData(
            answer=answer,
            provider=provider,
            model=model,
            mode=payload.mode,
            top_n=payload.top_n,
            top_k=payload.top_k,
            initial_results=initial,
            final_results=final,
        )
    )


@router.post("/completions/stream")
def chat_completions_stream(payload: ChatCompletionRequest) -> StreamingResponse:
    if not session_service.session_exists(payload.session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": 1002, "message": "session not found", "data": {"session_id": payload.session_id}},
        )
    if payload.top_k > payload.top_n:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 1001, "message": "top_k must be <= top_n", "data": {"top_n": payload.top_n, "top_k": payload.top_k}},
        )

    initial = []
    final = []
    context_chunks: list[tuple[int, str]] = []
    if payload.mode != "none":
        session = session_service.get_session(payload.session_id)
        kb_id = payload.knowledge_base_id or (session.knowledge_base_id if session else None)
        if not kb_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": 1001, "message": "knowledge base is required when mode is not none", "data": {}},
            )
        kb = knowledge_base_service.get_knowledge_base(kb_id)
        if kb is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": 1002, "message": "knowledge base not found", "data": {"knowledge_base_id": kb_id}},
            )
        try:
            file_paths = knowledge_base_service.get_file_paths(kb_id)
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
                detail={"code": 3001, "message": "chat retrieval failed", "data": {"error": str(exc)}},
            )

        detail_by_id: dict[str, dict[str, str | float]] = {}
        raw_by_id = {str(item["chunk_id"]): item for item in all_chunks}
        for result in initial + final:
            raw = raw_by_id.get(result.chunk_id)
            if raw is None:
                continue
            detail_by_id[result.chunk_id] = {
                "chunk_id": result.chunk_id,
                "title": result.title,
                "source": result.source,
                "score": result.score,
                "content": result.content,
                "channel": result.channel,
                "hit_mode": result.hit_mode,
                "vector_score": float(raw["vector_score"]),
                "bm25_score": float(raw["bm25_score"]),
                "hybrid_score": float(raw["hybrid_score"]),
            }
        knowledge_base_service.set_chunk_details(knowledge_base_id=kb_id, chunks=list(detail_by_id.values()))
        context_chunks = [(index + 1, item.content) for index, item in enumerate(final)]

    try:
        stream_iter, provider, model = chat_service.stream_complete(
            query=payload.query,
            context_chunks=context_chunks,
            provider=payload.provider,
            model=payload.model,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": 4001, "message": "chat completion failed", "data": {"error": str(exc)}},
        )

    def event_stream() -> Iterator[str]:
        full_answer = ""
        yield _sse_event(
            "meta",
            {
                "provider": provider,
                "model": model,
                "mode": payload.mode,
                "top_n": payload.top_n,
                "top_k": payload.top_k,
                "initial_results": [item.model_dump() for item in initial],
                "final_results": [item.model_dump() for item in final],
            },
        )
        try:
            for token in stream_iter:
                full_answer += token
                yield _sse_event("delta", {"content": token})
            yield _sse_event("done", {"answer": full_answer})
        except Exception as exc:
            yield _sse_event("error", {"message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
