from datetime import datetime

from pydantic import BaseModel, Field


class RecentRating(BaseModel):
    token: str
    interval_days: int
    reviewed_at: datetime


class UserStats(BaseModel):
    due_today: int = Field(ge=0)
    total_reviews: int = Field(ge=0)
    current_streak: int = Field(ge=0)
    recent: list[RecentRating] = Field(max_length=5)
