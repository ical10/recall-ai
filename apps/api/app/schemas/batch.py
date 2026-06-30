from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.review import ReviewQuality


class Card(BaseModel):
    review_id: UUID
    vocab_item_id: UUID
    token: str
    definition: str
    example_sentence: str | None = None
    ease_factor: float = Field(ge=1.3)
    interval_days: int = Field(ge=0)
    repetitions: int = Field(ge=0)
    due_at: datetime
    word_audio_url: str | None = None
    example_audio_url: str | None = None


class DailyBatch(BaseModel):
    cards: list[Card]


class RatingIn(BaseModel):
    rating_id: UUID
    card_id: UUID
    grade: ReviewQuality
    rated_at: datetime


class RatingsBody(BaseModel):
    ratings: list[RatingIn]


class SyncResult(BaseModel):
    applied: int = Field(ge=0)
    skipped: int = Field(ge=0)
