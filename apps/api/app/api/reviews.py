from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy import or_, select
from sqlalchemy.orm import contains_eager

from app.api.deps import SessionDep, UserDep, templates
from app.models.review import Review, ReviewQuality
from app.models.vocab_item import VocabItem
from app.schemas.review import ReviewState
from app.services.sm2 import compute_next_review

router = APIRouter()

AGAIN_REQUEUE_MINUTES = 10
AGAIN_QUEUE_KEY = "again_queue"


async def _next_due_review(session: SessionDep, user_id: UUID, now: datetime) -> Review | None:
    stmt = (
        select(Review)
        .join(Review.vocab_item)
        .options(contains_eager(Review.vocab_item))
        .where(
            Review.user_id == user_id,
            Review.suspended.is_(False),
            VocabItem.definition != "",
            or_(Review.due_at.is_(None), Review.due_at <= now),
        )
        .order_by(Review.due_at.asc().nulls_first(), Review.created_at.asc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _pick_next_review(
    session: SessionDep,
    user_id: UUID,
    now: datetime,
    again_queue: list[dict[str, str]],
) -> tuple[Review | None, list[dict[str, str]]]:
    ready = [e for e in again_queue if datetime.fromisoformat(e["after"]) <= now]
    pending = [e for e in again_queue if datetime.fromisoformat(e["after"]) > now]
    if ready:
        ready.sort(key=lambda e: e["after"])
        picked = ready[0]
        stmt = (
            select(Review)
            .join(Review.vocab_item)
            .options(contains_eager(Review.vocab_item))
            .where(Review.id == UUID(picked["id"]), Review.user_id == user_id)
        )
        review = (await session.execute(stmt)).scalar_one_or_none()
        if review is not None:
            return review, ready[1:] + pending
        return await _next_due_review(session, user_id, now), ready[1:] + pending
    return await _next_due_review(session, user_id, now), pending


@router.get("/review")
async def review_page(
    request: Request,
    session: SessionDep,
    user: UserDep,
) -> Response:
    now = datetime.now(UTC)
    again_queue: list[dict[str, str]] = request.session.get(AGAIN_QUEUE_KEY, [])
    review, again_queue = await _pick_next_review(session, user.id, now, again_queue)
    request.session[AGAIN_QUEUE_KEY] = again_queue
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
        .join(Review.vocab_item)
        .options(contains_eager(Review.vocab_item))
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

    review = (
        await session.execute(
            select(Review).where(Review.id == review_id, Review.user_id == user.id)
        )
    ).scalar_one_or_none()
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

    again_queue: list[dict[str, str]] = request.session.get(AGAIN_QUEUE_KEY, [])
    again_queue = [e for e in again_queue if e["id"] != str(review_id)]
    if quality_enum == ReviewQuality.AGAIN:
        again_queue.append(
            {
                "id": str(review_id),
                "after": (now + timedelta(minutes=AGAIN_REQUEUE_MINUTES)).isoformat(),
            }
        )

    next_review, again_queue = await _pick_next_review(session, user.id, now, again_queue)
    request.session[AGAIN_QUEUE_KEY] = again_queue
    if next_review is None:
        return templates.TemplateResponse(request, "partials/done.html")
    return templates.TemplateResponse(
        request,
        "partials/card.html",
        {"review": next_review, "vocab": next_review.vocab_item},
    )
