from __future__ import annotations

from pydantic import BaseModel, Field


class InterestTagsUpdate(BaseModel):
    tags: list[str] = Field(default_factory=list)


class UserSettings(BaseModel):
    interest_tags: list[str]
    all_tags: list[str]
