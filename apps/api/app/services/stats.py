from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.stats import RecentRating, UserStats


async def _fetch_review_dates(
    session: AsyncSession,
    user: User,
    user_tz: ZoneInfo,
) -> set[date]:
    """Return the set of local dates on which the user has at least one review.

    Uses func.timezone (Postgres) when available; falls back to Python-side
    timezone conversion for SQLite (tests).
    """
    engine = session.get_bind()
    dialect = engine.dialect.name if engine is not None else "postgresql"

    if dialect == "sqlite":
        raw_timestamps = (
            (
                await session.execute(
                    select(Review.last_reviewed_at).where(
                        Review.user_id == user.id,
                        Review.last_reviewed_at.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        # aiosqlite strips tzinfo; astimezone on a naive datetime treats it as local
        # system time instead of UTC, so we must explicitly mark it as UTC first.
        return {
            ts.replace(tzinfo=UTC).astimezone(user_tz).date()
            for ts in raw_timestamps
            if ts is not None
        }

    local_review_date = func.date(func.timezone(user.timezone, Review.last_reviewed_at))
    raw_dates = (
        (
            await session.execute(
                select(local_review_date)
                .where(Review.user_id == user.id, Review.last_reviewed_at.is_not(None))
                .group_by(local_review_date)
                .order_by(local_review_date.desc())
            )
        )
        .scalars()
        .all()
    )
    return {d if isinstance(d, date) else date.fromisoformat(str(d)) for d in raw_dates}


async def compute_user_stats(
    session: AsyncSession,
    user: User,
    *,
    today: date | None = None,
    review_dates: set[date] | None = None,
) -> UserStats:
    user_tz = ZoneInfo(user.timezone)
    today = today or datetime.now(user_tz).date()
    start_of_today_local = datetime.combine(today, datetime.min.time(), tzinfo=user_tz)
    end_of_today_local = start_of_today_local + timedelta(days=1)

    due_today = (
        await session.execute(
            select(func.count(Review.id))
            .join(VocabItem, Review.vocab_item_id == VocabItem.id)
            .where(
                Review.user_id == user.id,
                Review.suspended.is_(False),
                Review.due_at < end_of_today_local,
                VocabItem.definition != "",
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
        review_dates = await _fetch_review_dates(session, user, user_tz)

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
    """Walk back from today counting consecutive review days.

    Allows a 1-day grace when today has no review yet.
    """
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
