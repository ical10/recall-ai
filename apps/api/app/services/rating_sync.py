from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.applied_rating import AppliedRating
from app.models.review import Review
from app.models.user import User
from app.schemas.batch import RatingIn, SyncResult
from app.schemas.review import ReviewState
from app.services.sm2 import compute_next_review


async def apply_ratings(
    session: AsyncSession,
    user: User,
    ratings: list[RatingIn],
) -> SyncResult:
    sorted_ratings = sorted(ratings, key=lambda r: r.rated_at)

    existing_ids = {
        row[0]
        for row in (
            await session.execute(
                select(AppliedRating.rating_id).where(
                    AppliedRating.rating_id.in_([r.rating_id for r in sorted_ratings])
                )
            )
        ).all()
    }

    applied = 0
    skipped = 0
    now = datetime.now(UTC)

    for rating in sorted_ratings:
        if rating.rating_id in existing_ids:
            skipped += 1
            continue

        review = (
            await session.execute(
                select(Review).where(
                    Review.id == rating.card_id,
                    Review.user_id == user.id,
                )
            )
        ).scalar_one_or_none()

        if review is None:
            skipped += 1
            continue

        state = ReviewState(
            ease_factor=review.ease_factor,
            interval_days=review.interval_days,
            repetitions=review.repetitions,
        )
        update_result = compute_next_review(state, rating.grade)

        new_due_at = now + timedelta(days=update_result.interval_days)

        await session.execute(
            update(Review)
            .where(Review.id == review.id)
            .values(
                ease_factor=update_result.ease_factor,
                interval_days=update_result.interval_days,
                repetitions=update_result.repetitions,
                last_reviewed_at=now,
                due_at=new_due_at,
            )
        )

        await session.execute(
            insert(AppliedRating).values(
                rating_id=rating.rating_id,
                review_id=review.id,
                user_id=user.id,
                grade=int(rating.grade),
                rated_at=rating.rated_at,
            )
        )

        existing_ids.add(rating.rating_id)
        applied += 1

    await session.flush()
    await session.commit()
    return SyncResult(applied=applied, skipped=skipped)
