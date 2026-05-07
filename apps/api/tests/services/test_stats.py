"""Tests for compute_user_stats and supporting helpers in app.services.stats."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.stats import UserStats
from app.services.stats import compute_user_stats


def _engine(tmp_path: Path):
    return create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}", future=True)


async def _create_tables(engine) -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def _factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def _user(**kwargs) -> User:
    defaults = dict(email=f"u{uuid.uuid4()}@test.com", google_id=str(uuid.uuid4()), name="Test")
    return User(**{**defaults, **kwargs})


def _vocab(token: str = "word", language: str = "en", definition: str = "a word") -> VocabItem:
    return VocabItem(token=token, language=language, definition=definition)


TODAY = date(2026, 5, 7)
START_OF_TODAY = datetime(2026, 5, 7, 0, 0, 0, tzinfo=UTC)
YESTERDAY = datetime(2026, 5, 6, 12, 0, 0, tzinfo=UTC)
TWO_DAYS_AGO = datetime(2026, 5, 5, 12, 0, 0, tzinfo=UTC)
THREE_DAYS_AGO = datetime(2026, 5, 4, 12, 0, 0, tzinfo=UTC)


def test_due_today_counts_only_due_and_unsuspended(tmp_path: Path) -> None:
    """Only unsuspended reviews with due_at < end-of-today should count."""

    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        async with factory() as session:
            user = _user()
            session.add(user)
            vocab_past = _vocab("past", definition="past due")
            vocab_future = _vocab("future", definition="future due")
            vocab_suspended = _vocab("suspended", definition="suspended item")
            session.add_all([vocab_past, vocab_future, vocab_suspended])
            await session.flush()

            r_past = Review(
                user_id=user.id,
                vocab_item_id=vocab_past.id,
                due_at=START_OF_TODAY - timedelta(hours=1),
                suspended=False,
            )
            r_future = Review(
                user_id=user.id,
                vocab_item_id=vocab_future.id,
                due_at=START_OF_TODAY + timedelta(days=1, hours=1),
                suspended=False,
            )
            r_suspended = Review(
                user_id=user.id,
                vocab_item_id=vocab_suspended.id,
                due_at=START_OF_TODAY - timedelta(hours=2),
                suspended=True,
            )
            session.add_all([r_past, r_future, r_suspended])
            await session.commit()

        async with factory() as session:
            stats = await compute_user_stats(session, user.id, today=TODAY)

        assert stats.due_today == 1
        await engine.dispose()

    asyncio.run(_run())


def test_total_reviews_counts_only_reviewed(tmp_path: Path) -> None:
    """Reviews with last_reviewed_at IS NOT NULL should be counted; others ignored."""

    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        async with factory() as session:
            user = _user()
            session.add(user)
            v1 = _vocab("reviewed", definition="reviewed item")
            v2 = _vocab("unreviewed", definition="unreviewed item")
            session.add_all([v1, v2])
            await session.flush()

            r_reviewed = Review(
                user_id=user.id,
                vocab_item_id=v1.id,
                last_reviewed_at=YESTERDAY,
            )
            r_unreviewed = Review(
                user_id=user.id,
                vocab_item_id=v2.id,
                last_reviewed_at=None,
            )
            session.add_all([r_reviewed, r_unreviewed])
            await session.commit()

        async with factory() as session:
            stats = await compute_user_stats(session, user.id, today=TODAY)

        assert stats.total_reviews == 1
        await engine.dispose()

    asyncio.run(_run())


def test_streak_zero_when_no_reviews(tmp_path: Path) -> None:
    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        async with factory() as session:
            user = _user()
            session.add(user)
            await session.commit()

        async with factory() as session:
            stats = await compute_user_stats(session, user.id, today=TODAY)

        assert stats.current_streak == 0
        await engine.dispose()

    asyncio.run(_run())


def test_streak_one_when_only_today_reviewed(tmp_path: Path) -> None:
    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        async with factory() as session:
            user = _user()
            session.add(user)
            v = _vocab("tok", definition="a token")
            session.add(v)
            await session.flush()

            r = Review(
                user_id=user.id,
                vocab_item_id=v.id,
                last_reviewed_at=START_OF_TODAY + timedelta(hours=1),
            )
            session.add(r)
            await session.commit()

        async with factory() as session:
            stats = await compute_user_stats(session, user.id, today=TODAY)

        assert stats.current_streak == 1
        await engine.dispose()

    asyncio.run(_run())


def test_recent_returns_last_five_ordered_desc(tmp_path: Path) -> None:
    """Insert 7 reviews; the returned 5 must be the newest, ordered newest-first."""

    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        base_time = datetime(2026, 5, 7, 10, 0, 0, tzinfo=UTC)

        async with factory() as session:
            user = _user()
            session.add(user)
            vocabs = [_vocab(f"tok{i}", definition=f"definition {i}") for i in range(7)]
            session.add_all(vocabs)
            await session.flush()

            reviews = [
                Review(
                    user_id=user.id,
                    vocab_item_id=vocabs[i].id,
                    last_reviewed_at=base_time + timedelta(hours=i),
                    interval_days=i,
                )
                for i in range(7)
            ]
            session.add_all(reviews)
            await session.commit()

        async with factory() as session:
            stats = await compute_user_stats(session, user.id, today=TODAY)

        assert len(stats.recent) == 5
        assert [r.token for r in stats.recent] == [f"tok{i}" for i in range(6, 1, -1)]
        await engine.dispose()

    asyncio.run(_run())


def test_streak_continues_through_yesterday_when_today_empty(tmp_path: Path) -> None:
    """Yesterday + day-before reviewed, today empty → streak=2 (grace day)."""

    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        async with factory() as session:
            user = _user()
            session.add(user)
            v1 = _vocab("a", definition="word a")
            v2 = _vocab("b", definition="word b")
            session.add_all([v1, v2])
            await session.flush()

            r1 = Review(
                user_id=user.id,
                vocab_item_id=v1.id,
                last_reviewed_at=YESTERDAY,
            )
            r2 = Review(
                user_id=user.id,
                vocab_item_id=v2.id,
                last_reviewed_at=TWO_DAYS_AGO,
            )
            session.add_all([r1, r2])
            await session.commit()

        async with factory() as session:
            stats = await compute_user_stats(session, user.id, today=TODAY)

        assert stats.current_streak == 2
        await engine.dispose()

    asyncio.run(_run())


def test_streak_breaks_on_two_day_gap(tmp_path: Path) -> None:
    """Reviewed today + 3 days ago (gap of 2 days in between) → streak=1."""

    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        async with factory() as session:
            user = _user()
            session.add(user)
            v1 = _vocab("x", definition="word x")
            v2 = _vocab("y", definition="word y")
            session.add_all([v1, v2])
            await session.flush()

            r1 = Review(
                user_id=user.id,
                vocab_item_id=v1.id,
                last_reviewed_at=START_OF_TODAY + timedelta(hours=1),
            )
            r2 = Review(
                user_id=user.id,
                vocab_item_id=v2.id,
                last_reviewed_at=THREE_DAYS_AGO,
            )
            session.add_all([r1, r2])
            await session.commit()

        async with factory() as session:
            stats = await compute_user_stats(session, user.id, today=TODAY)

        assert stats.current_streak == 1
        await engine.dispose()

    asyncio.run(_run())


def test_compute_user_stats_isolated_per_user(tmp_path: Path) -> None:
    """Two users; each only sees their own counts."""

    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        async with factory() as session:
            user_a = _user(email="a@test.com", google_id="ga")
            user_b = _user(email="b@test.com", google_id="gb")
            session.add_all([user_a, user_b])
            v1 = _vocab("va", definition="word va")
            v2 = _vocab("vb", definition="word vb")
            session.add_all([v1, v2])
            await session.flush()

            r = Review(
                user_id=user_a.id,
                vocab_item_id=v1.id,
                last_reviewed_at=YESTERDAY,
                due_at=START_OF_TODAY - timedelta(hours=1),
            )
            session.add(r)
            await session.commit()

        async with factory() as session:
            stats_a = await compute_user_stats(session, user_a.id, today=TODAY)
            stats_b = await compute_user_stats(session, user_b.id, today=TODAY)

        assert stats_a.total_reviews == 1
        assert stats_a.due_today == 1
        assert stats_b.total_reviews == 0
        assert stats_b.due_today == 0
        await engine.dispose()

    asyncio.run(_run())


def test_compute_user_stats_handles_user_with_no_reviews(tmp_path: Path) -> None:
    """A brand-new user should get all zeros and an empty recent list."""

    async def _run() -> None:
        engine = _engine(tmp_path)
        await _create_tables(engine)
        factory = _factory(engine)

        async with factory() as session:
            user = _user()
            session.add(user)
            await session.commit()

        async with factory() as session:
            stats = await compute_user_stats(session, user.id, today=TODAY)

        assert stats.due_today == 0
        assert stats.total_reviews == 0
        assert stats.current_streak == 0
        assert stats.recent == []
        await engine.dispose()

    asyncio.run(_run())


def test_user_stats_schema_rejects_negative_due_today() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UserStats(due_today=-1, total_reviews=0, current_streak=0, recent=[])


def test_user_stats_schema_rejects_recent_longer_than_five() -> None:

    import pytest
    from pydantic import ValidationError

    from app.schemas.stats import RecentRating

    entries = [
        RecentRating(
            token=f"tok{i}",
            interval_days=i,
            reviewed_at=datetime(2026, 5, 7, tzinfo=UTC),
        )
        for i in range(6)
    ]
    with pytest.raises(ValidationError):
        UserStats(due_today=0, total_reviews=0, current_streak=0, recent=entries)
