from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import get_current_user, templates
from app.core.db import get_session
from app.models.review import Review
from app.models.user import User

router = APIRouter()

_SessionDep = Annotated[AsyncSession, Depends(get_session)]
_UserDep = Annotated[User, Depends(get_current_user)]


@router.get("/review")
async def review_page(
    request: Request,
    session: _SessionDep,
    user: _UserDep,
) -> Response:
    now = datetime.now(UTC)
    review = await _next_due_review(session, user.id, now)
    if review is None:
        return templates.TemplateResponse(request, "partials/done.html")
    return templates.TemplateResponse(
        request,
        "pages/review.html",
        {"review": review, "vocab": review.vocab_item},
    )


async def _next_due_review(session: AsyncSession, user_id: UUID, now: datetime) -> Review | None:
    stmt = (
        select(Review)
        .options(joinedload(Review.vocab_item))
        .where(
            Review.user_id == user_id,
            Review.suspended.is_(False),
            or_(Review.due_at.is_(None), Review.due_at <= now),
        )
        .order_by(Review.due_at.asc().nulls_first(), Review.created_at.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()
