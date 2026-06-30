from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.api.deps import SessionDep
from app.models.user import User
from app.schemas.me import MeResponse

router = APIRouter()


async def _optional_user(request: Request, session: SessionDep) -> User | None:
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return await session.get(User, UUID(user_id))


OptionalUserDep = Annotated[User | None, Depends(_optional_user)]


@router.get("/me")
async def api_me(user: OptionalUserDep) -> MeResponse | None:
    if user is None:
        return None
    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar_url=user.avatar_url,
    )
