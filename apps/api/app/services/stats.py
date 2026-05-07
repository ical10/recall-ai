from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.vocab_item import VocabItem
from app.schemas.stats import RecentRating, UserStats


def _to_date(value: date | str) -> date:
    # sqlite returns func.date() as an ISO string; postgres returns a date object.
    return date.fromisoformat(value) if isinstance(value, str) else value


async def compute_user_stats(
    session: AsyncSession,
    user_id: UUID,
    *,
    today: date | None = None,
) -> UserStats:
    today = today or datetime.now(UTC).date()
    start_of_today = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    end_of_today = start_of_today + timedelta(days=1)

    due_today = (
        await session.execute(
            select(func.count(Review.id)).where(
                Review.user_id == user_id,
                Review.suspended.is_(False),
                Review.due_at < end_of_today,
            )
        )
    ).scalar_one()

    total_reviews = (
        await session.execute(
            select(func.count(Review.id)).where(
                Review.user_id == user_id, Review.last_reviewed_at.is_not(None)
            )
        )
    ).scalar_one()

    review_dates = (
        (
            await session.execute(
                select(func.date(Review.last_reviewed_at))
                .where(Review.user_id == user_id, Review.last_reviewed_at.is_not(None))
                .group_by(func.date(Review.last_reviewed_at))
                .order_by(func.date(Review.last_reviewed_at).desc())
            )
        )
        .scalars()
        .all()
    )

    streak = _compute_streak({_to_date(d) for d in review_dates}, today)

    recent_rows = (
        await session.execute(
            select(VocabItem.token, Review.interval_days, Review.last_reviewed_at)
            .join(VocabItem, Review.vocab_item_id == VocabItem.id)
            .where(Review.user_id == user_id, Review.last_reviewed_at.is_not(None))
            .order_by(Review.last_reviewed_at.desc())
            .limit(5)
        )
    ).all()
    recent = [RecentRating(token=t, interval_days=i, reviewed_at=r) for (t, i, r) in recent_rows]

    return UserStats(
        due_today=int(due_today),
        total_reviews=int(total_reviews),
        current_streak=streak,
        recent=recent,
    )


def _compute_streak(dates_with_reviews: set[date], today: date) -> int:
    """Walk back from `today` (with a 1-day grace if today is empty)
    counting consecutive days that have at least one review."""
    if not dates_with_reviews:
        return 0
    cursor = today if today in dates_with_reviews else today - timedelta(days=1)
    if cursor not in dates_with_reviews:
        return 0
    streak = 0
    while cursor in dates_with_reviews:
        streak += 1
        cursor = cursor - timedelta(days=1)
    return streak
