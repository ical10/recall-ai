from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import ColumnElement

from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


def due_today_conditions(
    user_timezone: str,
    *,
    today: date | None = None,
) -> list[ColumnElement[bool]]:
    user_tz = ZoneInfo(user_timezone)
    today = today or datetime.now(user_tz).date()
    start_of_today_local = datetime.combine(today, datetime.min.time(), tzinfo=user_tz)
    end_of_today_local = start_of_today_local + timedelta(days=1)

    return [
        Review.suspended.is_(False),
        VocabItem.definition != "",
        or_(
            Review.due_at.is_(None),
            Review.due_at < end_of_today_local,
        ),
    ]


def not_reviewed_today_condition(
    user_timezone: str,
    *,
    today: date | None = None,
) -> ColumnElement[bool]:
    user_tz = ZoneInfo(user_timezone)
    today = today or datetime.now(user_tz).date()
    start_of_today_local = datetime.combine(today, datetime.min.time(), tzinfo=user_tz)

    return or_(
        Review.last_reviewed_at.is_(None),
        Review.last_reviewed_at < start_of_today_local,
    )


async def reviewed_local_dates(session: AsyncSession, user: User) -> set[date]:
    """Every local calendar date on which the user reviewed at least one card.

    The single home for "reviewed-on-a-local-day": handles the SQLite (convert
    client-side) vs Postgres (`func.timezone` in SQL) split so callers — e.g. streak
    computation — never reimplement the timezone bucketing.
    """
    user_tz = ZoneInfo(user.timezone)
    engine = session.get_bind()
    dialect = engine.dialect.name if engine is not None else "postgresql"

    if dialect == "sqlite":
        raw = (
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
        return {ts.replace(tzinfo=UTC).astimezone(user_tz).date() for ts in raw if ts is not None}

    local_date = func.date(func.timezone(user.timezone, Review.last_reviewed_at))
    raw_dates = (
        (
            await session.execute(
                select(local_date)
                .where(Review.user_id == user.id, Review.last_reviewed_at.is_not(None))
                .group_by(local_date)
                .order_by(local_date.desc())
            )
        )
        .scalars()
        .all()
    )
    return {d if isinstance(d, date) else date.fromisoformat(str(d)) for d in raw_dates}
