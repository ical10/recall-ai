import uuid

from sqlalchemy import JSON, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

DEFAULT_INTEREST_TAGS: list[str] = ["animals", "family", "food"]


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    google_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default="UTC")
    interest_tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: list(DEFAULT_INTEREST_TAGS),
        server_default='["animals","family","food"]',
    )
    last_personalized_milestone: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    last_milestone_seen: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
