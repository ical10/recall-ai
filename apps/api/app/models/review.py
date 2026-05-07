import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.vocab_item import VocabItem


class ReviewQuality(enum.IntEnum):
    AGAIN = 0
    HARD = 2
    GOOD = 4
    EASY = 5


class Review(Base, TimestampMixin):
    __tablename__ = "reviews"
    __table_args__ = (
        UniqueConstraint("user_id", "vocab_item_id", name="uq_reviews_user_id_vocab_item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vocab_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vocab_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ease_factor: Mapped[float] = mapped_column(Float, default=2.5, nullable=False)
    interval_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    repetitions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    suspended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vocab_item: Mapped["VocabItem"] = relationship("VocabItem", lazy="raise")
