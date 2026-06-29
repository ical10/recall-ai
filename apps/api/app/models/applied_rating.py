import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AppliedRating(Base):
    __tablename__ = "applied_ratings"

    rating_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    review_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    grade: Mapped[int] = mapped_column(Integer, nullable=False)
    rated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
