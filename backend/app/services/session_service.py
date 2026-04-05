from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from app.schemas.session import Session, SessionCreateRequest


class SessionService:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def list_sessions(self) -> list[Session]:
        return sorted(self._sessions.values(), key=lambda x: x.updated_at, reverse=True)

    def create_session(self, payload: SessionCreateRequest) -> Session:
        now = datetime.now(timezone.utc)
        session = Session(
            id=f"sess_{uuid4().hex[:8]}",
            title=payload.title,
            updated_at=now,
            is_draft=payload.is_draft,
            knowledge_base_id=None,
        )
        self._sessions[session.id] = session
        return session

    def delete_session(self, session_id: str) -> bool:
        if session_id not in self._sessions:
            return False
        del self._sessions[session_id]
        return True

    def get_session(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def session_exists(self, session_id: str) -> bool:
        return session_id in self._sessions

    def bind_knowledge_base(self, session_id: str, knowledge_base_id: Optional[str]) -> bool:
        target = self._sessions.get(session_id)
        if not target:
            return False
        target.knowledge_base_id = knowledge_base_id
        target.updated_at = datetime.now(timezone.utc)
        self._sessions[session_id] = target
        return True


session_service = SessionService()
