from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.stats import RecentRating, UserStats
from app.services.due import due_today_conditions, reviewed_local_dates


async def compute_user_stats(
    session: AsyncSession,
    user: User,
    *,
    today: date | None = None,
    review_dates: set[date] | None = None,
) -> UserStats:
    user_tz = ZoneInfo(user.timezone)
    today = today or datetime.now(user_tz).date()

    due_today = (
        await session.execute(
            select(func.count(Review.id))
            .join(VocabItem, Review.vocab_item_id == VocabItem.id)
            .where(
                Review.user_id == user.id,
                and_(*due_today_conditions(user.timezone, today=today)),
            )
        )
    ).scalar_one()

    total_reviews = (
        await session.execute(
            select(func.count(Review.id)).where(
                Review.user_id == user.id,
                Review.last_reviewed_at.is_not(None),
            )
        )
    ).scalar_one()

    if review_dates is None:
        review_dates = await reviewed_local_dates(session, user)

    streak = _compute_streak(review_dates, today)

    recent_rows = (
        await session.execute(
            select(VocabItem.token, Review.interval_days, Review.last_reviewed_at)
            .join(VocabItem, Review.vocab_item_id == VocabItem.id)
            .where(Review.user_id == user.id, Review.last_reviewed_at.is_not(None))
            .order_by(Review.last_reviewed_at.desc())
            .limit(5)
        )
    ).all()
    recent = [RecentRating(token=t, interval_days=i, reviewed_at=r) for (t, i, r) in recent_rows]

    unseen_milestone = (
        user.last_personalized_milestone
        if user.last_personalized_milestone > user.last_milestone_seen
        else None
    )

    return UserStats(
        due_today=int(due_today),
        total_reviews=int(total_reviews),
        current_streak=streak,
        recent=recent,
        unseen_milestone=unseen_milestone,
    )


def _compute_streak(dates_with_reviews: set[date], today: date) -> int:
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
