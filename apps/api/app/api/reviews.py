from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import SessionDep, UserDep, templates
from app.models.review import Review

router = APIRouter()


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


@router.get("/review")
async def review_page(
    request: Request,
    session: SessionDep,
    user: UserDep,
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


@router.get("/review/{review_id}/reveal")
async def review_reveal(
    review_id: UUID,
    request: Request,
    session: SessionDep,
    user: UserDep,
) -> Response:
    stmt = (
        select(Review)
        .options(joinedload(Review.vocab_item))
        .where(Review.id == review_id, Review.user_id == user.id)
    )
    review = (await session.execute(stmt)).scalar_one_or_none()
    if review is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request,
        "partials/rating.html",
        {"review": review, "vocab": review.vocab_item},
    )
