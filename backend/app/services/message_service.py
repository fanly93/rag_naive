from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import asc, case, select

from app.db import SessionLocal
from app.models import ChatMessageModel
from app.schemas.message import SessionMessage
from app.services.chat_turn_service import chat_turn_service


class MessageService:
    def _to_schema(self, row: ChatMessageModel) -> SessionMessage:
        created_at = row.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        role = "assistant" if row.role == "assistant" else "user"
        return SessionMessage(
            id=row.id,
            session_id=row.session_id,
            role=role,
            content=row.content,
            is_error=row.is_error,
            created_at=created_at,
        )

    def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        is_error: bool = False,
    ) -> SessionMessage:
        row = ChatMessageModel(
            id=f"msg_{uuid4().hex[:8]}",
            session_id=session_id,
            role=role if role in {"user", "assistant"} else "user",
            content=content,
            is_error=is_error,
            created_at=datetime.now(timezone.utc),
        )
        with SessionLocal() as db:
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_schema(row)

    def list_messages(self, session_id: str) -> list[SessionMessage]:
        citations_map = chat_turn_service.list_citations_by_assistant_message(session_id=session_id)
        with SessionLocal() as db:
            rows = db.scalars(
                select(ChatMessageModel)
                .where(ChatMessageModel.session_id == session_id)
                .order_by(
                    asc(ChatMessageModel.created_at),
                    asc(case((ChatMessageModel.role == "user", 0), else_=1)),
                )
            ).all()
            items = [self._to_schema(item) for item in rows]
            for item in items:
                if item.role != "assistant":
                    continue
                refs = citations_map.get(item.id)
                if refs is None:
                    continue
                initial, final = refs
                item.top_n_citations = initial
                item.top_k_citations = final
            return items


message_service = MessageService()
