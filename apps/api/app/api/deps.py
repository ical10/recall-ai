from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.tokens import verify_bearer_token
from app.models.user import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# --- authentication adapters -------------------------------------------------
# Current-user resolution is a seam: each adapter resolves the User for a request
# under one scheme (or None). `_resolve_user` tries them in order. New schemes slot
# in here without touching any handler — every endpoint keeps using UserDep.


async def _user_from_bearer(request: Request, session: AsyncSession) -> User | None:
    """Extension scheme: a signed bearer token in the Authorization header."""
    header = request.headers.get("authorization")
    if header is None or not header.lower().startswith("bearer "):
        return None
    user_id = verify_bearer_token(header[7:].strip())
    if user_id is None:
        return None
    return await session.get(User, user_id)


async def _user_from_session(request: Request, session: AsyncSession) -> User | None:
    """Web scheme: the signed session cookie."""
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    try:
        parsed = UUID(str(user_id))
    except (ValueError, TypeError):
        return None
    return await session.get(User, parsed)


async def _resolve_user(request: Request, session: AsyncSession) -> User | None:
    for adapter in (_user_from_bearer, _user_from_session):
        user = await adapter(request, session)
        if user is not None:
            return user
    return None


async def get_current_user(request: Request, session: SessionDep) -> User:
    user = await _resolve_user(request, session)
    if user is None:
        raise HTTPException(status_code=401)
    return user


async def get_optional_user(request: Request, session: SessionDep) -> User | None:
    return await _resolve_user(request, session)


UserDep = Annotated[User, Depends(get_current_user)]
OptionalUserDep = Annotated[User | None, Depends(get_optional_user)]
