from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class MeResponse(BaseModel):
    id: UUID
    email: str
    name: str
    avatar_url: str | None
