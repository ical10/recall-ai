from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_
from sqlalchemy.sql import ColumnElement

from app.models.review import Review
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
