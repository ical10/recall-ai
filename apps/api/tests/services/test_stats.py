"""Tests for compute_user_stats and _compute_streak.

SQLite is used for the test DB (matching the existing api test pattern).
func.timezone is Postgres-only, so streak tests bypass the DB query by
injecting review_dates directly into compute_user_stats (plan approach b).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.stats import UserStats

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _make_factory(db_path: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _insert_user(
    factory: async_sessionmaker[AsyncSession],
    email: str = "u@test.com",
    tz: str = "UTC",
) -> User:
    async with factory() as s:
        u = User(email=email, google_id=f"gid-{email}", name="Test", timezone=tz)
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _insert_vocab(
    factory: async_sessionmaker[AsyncSession],
    token: str,
    definition: str = "a word",
) -> uuid.UUID:
    async with factory() as s:
        vi = VocabItem(token=token, language="en", definition=definition)
        s.add(vi)
        await s.commit()
        await s.refresh(vi)
        return vi.id


async def _insert_review(
    factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    vocab_id: uuid.UUID,
    *,
    due_at: datetime | None = None,
    suspended: bool = False,
    last_reviewed_at: datetime | None = None,
    interval_days: int = 1,
) -> uuid.UUID:
    async with factory() as s:
        r = Review(
            user_id=user_id,
            vocab_item_id=vocab_id,
            due_at=due_at,
            suspended=suspended,
            last_reviewed_at=last_reviewed_at,
            interval_days=interval_days,
        )
        s.add(r)
        await s.commit()
        await s.refresh(r)
        return r.id


async def _get_stats(
    factory: async_sessionmaker[AsyncSession],
    user: User,
    today: date | None = None,
    review_dates: set[date] | None = None,
) -> UserStats:
    from app.services.stats import compute_user_stats

    async with factory() as s:
        return await compute_user_stats(s, user, today=today, review_dates=review_dates)


# ---------------------------------------------------------------------------
# due_today
# ---------------------------------------------------------------------------


def test_due_today_counts_only_due_and_unsuspended(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    today = date(2026, 5, 14)
    end = datetime(2026, 5, 15, 0, 0, 0, tzinfo=UTC)

    async def setup() -> None:
        vid1 = await _insert_vocab(factory, "word1")
        vid2 = await _insert_vocab(factory, "word2")
        vid3 = await _insert_vocab(factory, "word3")
        await _insert_review(factory, user.id, vid1, due_at=datetime(2026, 5, 13, tzinfo=UTC))
        await _insert_review(factory, user.id, vid2, due_at=end + timedelta(hours=1))
        await _insert_review(
            factory, user.id, vid3, due_at=datetime(2026, 5, 13, tzinfo=UTC), suspended=True
        )

    asyncio.run(setup())
    stats = asyncio.run(_get_stats(factory, user, today=today, review_dates=set()))
    assert stats.due_today == 1


def test_due_today_excludes_unenriched_vocab(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    today = date(2026, 5, 14)

    async def setup() -> None:
        vid_ready = await _insert_vocab(factory, "ready", definition="a word")
        vid_pending = await _insert_vocab(factory, "pending", definition="")
        await _insert_review(factory, user.id, vid_ready, due_at=datetime(2026, 5, 13, tzinfo=UTC))
        await _insert_review(
            factory, user.id, vid_pending, due_at=datetime(2026, 5, 13, tzinfo=UTC)
        )

    asyncio.run(setup())
    stats = asyncio.run(_get_stats(factory, user, today=today, review_dates=set()))
    assert stats.due_today == 1


def test_due_today_null_due_at_not_counted(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    today = date(2026, 5, 14)

    async def setup() -> None:
        vid = await _insert_vocab(factory, "nul")
        await _insert_review(factory, user.id, vid, due_at=None)

    asyncio.run(setup())
    stats = asyncio.run(_get_stats(factory, user, today=today, review_dates=set()))
    assert stats.due_today == 0


# ---------------------------------------------------------------------------
# total_reviews
# ---------------------------------------------------------------------------


def test_total_reviews_counts_only_reviewed(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    today = date(2026, 5, 14)
    reviewed_at = datetime(2026, 5, 13, 10, 0, tzinfo=UTC)

    async def setup() -> None:
        vid1 = await _insert_vocab(factory, "done")
        vid2 = await _insert_vocab(factory, "notdone")
        await _insert_review(factory, user.id, vid1, last_reviewed_at=reviewed_at)
        await _insert_review(factory, user.id, vid2)

    asyncio.run(setup())
    stats = asyncio.run(_get_stats(factory, user, today=today, review_dates=set()))
    assert stats.total_reviews == 1


# ---------------------------------------------------------------------------
# _compute_streak (injected dates — no DB, no func.timezone)
# ---------------------------------------------------------------------------


def test_streak_zero_when_no_reviews() -> None:
    from app.services.stats import _compute_streak

    assert _compute_streak(set(), date(2026, 5, 14)) == 0


def test_streak_one_when_only_today_reviewed() -> None:
    from app.services.stats import _compute_streak

    today = date(2026, 5, 14)
    assert _compute_streak({today}, today) == 1


def test_streak_continues_through_yesterday_when_today_empty() -> None:
    from app.services.stats import _compute_streak

    today = date(2026, 5, 14)
    dates = {today - timedelta(days=1), today - timedelta(days=2)}
    assert _compute_streak(dates, today) == 2


def test_streak_breaks_on_two_day_gap() -> None:
    from app.services.stats import _compute_streak

    today = date(2026, 5, 14)
    dates = {today, today - timedelta(days=3)}
    assert _compute_streak(dates, today) == 1


def test_streak_grace_day_does_not_count_if_two_days_ago_also_empty() -> None:
    from app.services.stats import _compute_streak

    today = date(2026, 5, 14)
    dates = {today - timedelta(days=5)}
    assert _compute_streak(dates, today) == 0


def test_streak_long_consecutive_run() -> None:
    from app.services.stats import _compute_streak

    today = date(2026, 5, 14)
    dates = {today - timedelta(days=i) for i in range(7)}
    assert _compute_streak(dates, today) == 7


# ---------------------------------------------------------------------------
# recent
# ---------------------------------------------------------------------------


def test_recent_returns_last_five_ordered_desc(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    today = date(2026, 5, 14)
    base = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)

    async def setup() -> list[str]:
        tokens = [f"w{i}" for i in range(7)]
        for i, tok in enumerate(tokens):
            vid = await _insert_vocab(factory, tok)
            await _insert_review(
                factory,
                user.id,
                vid,
                last_reviewed_at=base + timedelta(hours=i),
                interval_days=i,
            )
        return tokens

    asyncio.run(setup())
    stats = asyncio.run(_get_stats(factory, user, today=today, review_dates=set()))
    assert len(stats.recent) == 5
    result_tokens = [r.token for r in stats.recent]
    assert result_tokens == ["w6", "w5", "w4", "w3", "w2"]


# ---------------------------------------------------------------------------
# per-user isolation
# ---------------------------------------------------------------------------


def test_compute_user_stats_isolated_per_user(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user_a = asyncio.run(_insert_user(factory, "a@test.com"))
    user_b = asyncio.run(_insert_user(factory, "b@test.com"))
    today = date(2026, 5, 14)
    reviewed_at = datetime(2026, 5, 13, tzinfo=UTC)

    async def setup() -> None:
        for i in range(3):
            vid = await _insert_vocab(factory, f"a_word{i}")
            await _insert_review(
                factory, user_a.id, vid, last_reviewed_at=reviewed_at, due_at=reviewed_at
            )
        vid_b = await _insert_vocab(factory, "b_word")
        await _insert_review(
            factory, user_b.id, vid_b, last_reviewed_at=reviewed_at, due_at=reviewed_at
        )

    asyncio.run(setup())
    stats_a = asyncio.run(_get_stats(factory, user_a, today=today, review_dates=set()))
    stats_b = asyncio.run(_get_stats(factory, user_b, today=today, review_dates=set()))
    assert stats_a.total_reviews == 3
    assert stats_b.total_reviews == 1
    assert len(stats_a.recent) == 3
    assert len(stats_b.recent) == 1


def test_compute_user_stats_handles_user_with_no_reviews(tmp_path: Path) -> None:
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    today = date(2026, 5, 14)
    stats = asyncio.run(_get_stats(factory, user, today=today, review_dates=set()))
    assert stats.due_today == 0
    assert stats.total_reviews == 0
    assert stats.current_streak == 0
    assert stats.recent == []


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_user_stats_rejects_more_than_five_recent() -> None:
    from datetime import datetime

    from app.schemas.stats import RecentRating, UserStats

    ratings = [
        RecentRating(token=f"w{i}", interval_days=1, reviewed_at=datetime(2026, 5, 1, tzinfo=UTC))
        for i in range(6)
    ]
    with pytest.raises(ValidationError):
        UserStats(due_today=0, total_reviews=0, current_streak=0, recent=ratings)


def test_user_stats_rejects_negative_counts() -> None:
    with pytest.raises(ValidationError):
        UserStats(due_today=-1, total_reviews=0, current_streak=0, recent=[])


# ---------------------------------------------------------------------------
# SQLite fallback timezone bucketing (DB-level tests)
# ---------------------------------------------------------------------------


def test_streak_uses_user_timezone_when_reviews_straddle_utc_midnight(
    tmp_path: Path,
) -> None:
    """User in Asia/Jakarta (UTC+7). Two reviews on the same Jakarta-local
    day but on different UTC days. Expect streak=1, not 2.

    Seed 1: last_reviewed_at = 2026-05-13 23:00 UTC = 2026-05-14 06:00 Jakarta
    Seed 2: last_reviewed_at = 2026-05-14 13:00 UTC = 2026-05-14 20:00 Jakarta

    UTC bucketing gives {2026-05-13, 2026-05-14} → streak=2 (wrong).
    Jakarta bucketing gives {2026-05-14} → streak=1 (correct).
    """
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory, tz="Asia/Jakarta"))
    today_jakarta = date(2026, 5, 14)

    async def setup() -> None:
        vid1 = await _insert_vocab(factory, "jakarta1")
        vid2 = await _insert_vocab(factory, "jakarta2")
        await _insert_review(
            factory,
            user.id,
            vid1,
            last_reviewed_at=datetime(2026, 5, 13, 23, 0, tzinfo=UTC),
        )
        await _insert_review(
            factory,
            user.id,
            vid2,
            last_reviewed_at=datetime(2026, 5, 14, 13, 0, tzinfo=UTC),
        )

    asyncio.run(setup())
    stats = asyncio.run(_get_stats(factory, user, today=today_jakarta))
    assert stats.current_streak == 1


def test_streak_uses_user_timezone_for_ny_consecutive_days(
    tmp_path: Path,
) -> None:
    """User in America/New_York (UTC-4 EDT). One review buckets to NY-today and
    one to NY-yesterday, forming a 2-day streak. The second seed's UTC timestamp
    falls in a window where naive-datetime bucketing (buggy) shifts it one extra
    day back to NY-day-before-yesterday, creating a gap and returning streak=1.

    Seed 1: last_reviewed_at = 2026-05-14 15:00 UTC = 2026-05-14 11:00 EDT (NY-today)
    Seed 2: last_reviewed_at = 2026-05-13 06:00 UTC = 2026-05-13 02:00 EDT (NY-yesterday)

    Correct NY bucketing: {2026-05-14, 2026-05-13} → streak=2.
    Buggy (naive treated as local UTC+8): {2026-05-14, 2026-05-12} → gap → streak=1.
    """
    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory, tz="America/New_York"))
    today_ny = date(2026, 5, 14)

    async def setup() -> None:
        vid1 = await _insert_vocab(factory, "ny1")
        vid2 = await _insert_vocab(factory, "ny2")
        # 2026-05-14 15:00 UTC = 2026-05-14 11:00 EDT (NY-today)
        await _insert_review(
            factory,
            user.id,
            vid1,
            last_reviewed_at=datetime(2026, 5, 14, 15, 0, tzinfo=UTC),
        )
        # 2026-05-13 06:00 UTC = 2026-05-13 02:00 EDT (NY-yesterday)
        await _insert_review(
            factory,
            user.id,
            vid2,
            last_reviewed_at=datetime(2026, 5, 13, 6, 0, tzinfo=UTC),
        )

    asyncio.run(setup())
    stats = asyncio.run(_get_stats(factory, user, today=today_ny))
    assert stats.current_streak == 2
