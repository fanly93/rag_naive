from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import desc, select

from app.db import SessionLocal
from app.models import SessionModel
from app.schemas.session import Session, SessionCreateRequest


class SessionService:
    def _truncate_title_from_query(self, query: str) -> str:
        normalized = " ".join(query.split()).strip()
        return f"{normalized[:20]}..." if len(normalized) > 20 else normalized

    def _to_schema(self, row: SessionModel) -> Session:
        updated_at = row.updated_at
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        return Session(
            id=row.id,
            title=row.title,
            updated_at=updated_at,
            is_draft=row.is_draft,
            knowledge_base_id=row.knowledge_base_id,
        )

    def list_sessions(self) -> list[Session]:
        with SessionLocal() as db:
            rows = db.scalars(select(SessionModel).order_by(desc(SessionModel.updated_at))).all()
            return [self._to_schema(item) for item in rows]

    def create_session(self, payload: SessionCreateRequest) -> Session:
        now = datetime.now(timezone.utc)
        row = SessionModel(
            id=f"sess_{uuid4().hex[:8]}",
            title=payload.title,
            updated_at=now,
            is_draft=payload.is_draft,
            knowledge_base_id=None,
        )
        with SessionLocal() as db:
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_schema(row)

    def delete_session(self, session_id: str) -> bool:
        with SessionLocal() as db:
            row = db.get(SessionModel, session_id)
            if row is None:
                return False
            db.delete(row)
            db.commit()
            return True

    def get_session(self, session_id: str) -> Optional[Session]:
        with SessionLocal() as db:
            row = db.get(SessionModel, session_id)
            if row is None:
                return None
            return self._to_schema(row)

    def session_exists(self, session_id: str) -> bool:
        with SessionLocal() as db:
            row = db.get(SessionModel, session_id)
            return row is not None

    def bind_knowledge_base(self, session_id: str, knowledge_base_id: Optional[str]) -> bool:
        with SessionLocal() as db:
            row = db.get(SessionModel, session_id)
            if row is None:
                return False
            row.knowledge_base_id = knowledge_base_id
            row.updated_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            return True

    def touch_by_query(self, session_id: str, query: str) -> bool:
        with SessionLocal() as db:
            row = db.get(SessionModel, session_id)
            if row is None:
                return False
            if row.is_draft:
                row.title = self._truncate_title_from_query(query) or row.title
                row.is_draft = False
            row.updated_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            return True


session_service = SessionService()
