from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class VocabCreate(BaseModel):
    token: str = Field(min_length=1, max_length=255)
    language: str = Field(min_length=2, max_length=35)


class VocabRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    token: str
    language: str
    part_of_speech: str | None = None
    definition: str
    example_sentence: str | None = None


class VocabListResponse(BaseModel):
    items: list[VocabRead]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
