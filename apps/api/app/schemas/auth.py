from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.me import MeResponse


class ExtensionAuthIn(BaseModel):
    id_token: str = Field(min_length=1)


class ExtensionAuthOut(BaseModel):
    token: str
    user: MeResponse
