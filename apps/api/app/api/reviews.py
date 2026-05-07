from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.api.deps import SessionDep, UserDep, templates
from app.models.review import Review
from app.schemas.review import ReviewQuality, ReviewState
from app.services.sm2 import compute_next_review

router = APIRouter()


async def _get_review_for_user(
    session: AsyncSession,
    review_id: UUID,
    user_id: UUID,
    *,
    load_vocab: bool = True,
) -> Review | None:
    stmt = select(Review).where(Review.id == review_id, Review.user_id == user_id)
    if load_vocab:
        stmt = stmt.options(joinedload(Review.vocab_item))
    return (await session.execute(stmt)).scalar_one_or_none()


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
    review = await _get_review_for_user(session, review_id, user.id)
    if review is None:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        request,
        "partials/rating.html",
        {"review": review, "vocab": review.vocab_item},
    )


@router.post("/review/{review_id}/rate")
async def review_rate(
    review_id: UUID,
    request: Request,
    session: SessionDep,
    user: UserDep,
    quality: int = Form(...),
) -> Response:
    try:
        quality_enum = ReviewQuality(quality)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="invalid quality") from exc

    review = await _get_review_for_user(session, review_id, user.id, load_vocab=False)
    if review is None:
        raise HTTPException(status_code=404)

    state = ReviewState(
        ease_factor=review.ease_factor,
        interval_days=review.interval_days,
        repetitions=review.repetitions,
    )
    update = compute_next_review(state, quality_enum)
    now = datetime.now(UTC)
    review.ease_factor = update.ease_factor
    review.interval_days = update.interval_days
    review.repetitions = update.repetitions
    review.last_reviewed_at = now
    review.due_at = now + timedelta(days=update.interval_days)
    await session.commit()

    next_review = await _next_due_review(session, user.id, now)
    if next_review is None:
        return templates.TemplateResponse(request, "partials/done.html")
    return templates.TemplateResponse(
        request,
        "partials/card.html",
        {"review": next_review, "vocab": next_review.vocab_item},
    )
