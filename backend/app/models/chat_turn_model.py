from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatTurnModel(Base):
    __tablename__ = "chat_turns"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_message_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assistant_message_id: Mapped[str | None] = mapped_column(
        String(32),
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    knowledge_base_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    top_n: Mapped[int] = mapped_column(Integer, nullable=False)
    top_k: Mapped[int] = mapped_column(Integer, nullable=False)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    answer_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_error: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
