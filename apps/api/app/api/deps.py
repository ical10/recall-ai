from pathlib import Path
from typing import Annotated

from fastapi import Depends
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.user import User

SessionDep = Annotated[AsyncSession, Depends(get_session)]

DEV_USER_EMAIL = "dev@local"
DEV_USER_GOOGLE_ID = "dev-local"
DEV_USER_NAME = "Dev"

BASE_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


async def get_current_user(session: SessionDep) -> User:
    stmt = select(User).where(User.email == DEV_USER_EMAIL)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        email=DEV_USER_EMAIL,
        google_id=DEV_USER_GOOGLE_ID,
        name=DEV_USER_NAME,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
