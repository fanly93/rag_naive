from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChatTurnCitationModel(Base):
    __tablename__ = "chat_turn_citations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    turn_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("chat_turns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage: Mapped[str] = mapped_column(String(16), nullable=False, index=True)  # initial | final
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    hit_mode: Mapped[str] = mapped_column(String(128), nullable=False)
