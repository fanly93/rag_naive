from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import asc

from app.db import SessionLocal
from app.models import ChatTurnCitationModel, ChatTurnModel
from app.schemas.retrieval import RetrievalChunk


class ChatTurnService:
    def persist_turn(
        self,
        session_id: str,
        user_message_id: str,
        assistant_message_id: str | None,
        query_text: str,
        answer_text: str,
        mode: str,
        top_n: int,
        top_k: int,
        provider: str | None,
        model: str | None,
        knowledge_base_id: str | None,
        initial_results: list[RetrievalChunk],
        final_results: list[RetrievalChunk],
        is_error: bool = False,
    ) -> str:
        turn_id = f"turn_{uuid4().hex[:8]}"
        turn = ChatTurnModel(
            id=turn_id,
            session_id=session_id,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            knowledge_base_id=knowledge_base_id,
            mode=mode,
            top_n=top_n,
            top_k=top_k,
            provider=provider,
            model=model,
            query_text=query_text,
            answer_text=answer_text,
            is_error=is_error,
            created_at=datetime.now(timezone.utc),
        )
        with SessionLocal() as db:
            db.add(turn)
            db.flush()
            citation_rows: list[ChatTurnCitationModel] = []
            for index, item in enumerate(initial_results):
                citation_rows.append(
                    ChatTurnCitationModel(
                        id=f"cit_{uuid4().hex[:8]}",
                        turn_id=turn_id,
                        stage="initial",
                        rank=index + 1,
                        chunk_id=item.chunk_id,
                        title=item.title,
                        source=item.source,
                        score=item.score,
                        content=item.content,
                        channel=item.channel,
                        hit_mode=item.hit_mode,
                    )
                )
            for index, item in enumerate(final_results):
                citation_rows.append(
                    ChatTurnCitationModel(
                        id=f"cit_{uuid4().hex[:8]}",
                        turn_id=turn_id,
                        stage="final",
                        rank=index + 1,
                        chunk_id=item.chunk_id,
                        title=item.title,
                        source=item.source,
                        score=item.score,
                        content=item.content,
                        channel=item.channel,
                        hit_mode=item.hit_mode,
                    )
                )
            if citation_rows:
                db.add_all(citation_rows)
            db.commit()
        return turn_id

    def list_citations_by_assistant_message(
        self,
        session_id: str,
    ) -> dict[str, tuple[list[RetrievalChunk], list[RetrievalChunk]]]:
        with SessionLocal() as db:
            turns = db.query(ChatTurnModel).filter(ChatTurnModel.session_id == session_id).all()
            if not turns:
                return {}
            turn_ids = [item.id for item in turns]
            citations = (
                db.query(ChatTurnCitationModel)
                .filter(ChatTurnCitationModel.turn_id.in_(turn_ids))
                .order_by(asc(ChatTurnCitationModel.rank))
                .all()
            )

        turn_by_assistant: dict[str, str] = {}
        for item in turns:
            if item.assistant_message_id:
                turn_by_assistant[item.assistant_message_id] = item.id
        initial_by_turn: dict[str, list[RetrievalChunk]] = {}
        final_by_turn: dict[str, list[RetrievalChunk]] = {}
        for row in citations:
            chunk = RetrievalChunk(
                chunk_id=row.chunk_id,
                title=row.title,
                source=row.source,
                score=row.score,
                content=row.content,
                channel=row.channel,  # type: ignore[arg-type]
                hit_mode=row.hit_mode,
            )
            if row.stage == "final":
                final_by_turn.setdefault(row.turn_id, []).append(chunk)
            else:
                initial_by_turn.setdefault(row.turn_id, []).append(chunk)

        out: dict[str, tuple[list[RetrievalChunk], list[RetrievalChunk]]] = {}
        for msg_id, turn_id in turn_by_assistant.items():
            out[msg_id] = (
                initial_by_turn.get(turn_id, []),
                final_by_turn.get(turn_id, []),
            )
        return out


chat_turn_service = ChatTurnService()
