from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.user import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


async def get_current_user(request: Request, session: SessionDep) -> User:
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401)
    user = await session.get(User, UUID(user_id))
    if user is None:
        raise HTTPException(status_code=401)
    return user


UserDep = Annotated[User, Depends(get_current_user)]
