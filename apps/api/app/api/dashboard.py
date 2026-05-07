from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, templates
from app.core.db import get_session
from app.models.user import User
from app.services.stats import compute_user_stats

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UserDep = Annotated[User, Depends(get_current_user)]


@router.get("/")
async def index() -> RedirectResponse:
    return RedirectResponse(url="/dashboard", status_code=307)


@router.get("/dashboard")
async def dashboard(
    request: Request,
    session: SessionDep,
    user: UserDep,
) -> Response:
    stats = await compute_user_stats(session, user.id)
    return templates.TemplateResponse(
        request,
        "pages/dashboard.html",
        {"stats": stats, "user": user},
    )
