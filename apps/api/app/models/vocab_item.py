import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class VocabItem(Base, TimestampMixin):
    __tablename__ = "vocab_items"
    __table_args__ = (UniqueConstraint("token", "language", name="uq_vocab_items_token_language"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(35), nullable=False)
    part_of_speech: Mapped[str | None] = mapped_column(String(32), nullable=True)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    enrichment_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_enrichment_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
