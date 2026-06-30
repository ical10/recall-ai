"""Tests for apply_ratings — idempotent SM-2 rating sync."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.review import Review, ReviewQuality
from app.models.user import User
from app.models.vocab_item import VocabItem


def _make_factory(db_path: str) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)

    async def _create() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def _insert_user(factory: async_sessionmaker[AsyncSession]) -> User:
    async with factory() as s:
        u = User(email="u@test.com", google_id="gid", name="Tester", timezone="UTC")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _insert_vocab_with_review(
    factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    token: str = "test",
) -> tuple[uuid.UUID, uuid.UUID]:
    async with factory() as s:
        vi = VocabItem(token=token, language="en", definition="a word")
        s.add(vi)
        await s.flush()
        past = datetime(2020, 1, 1, tzinfo=UTC)
        r = Review(
            user_id=user_id,
            vocab_item_id=vi.id,
            due_at=past,
            ease_factor=2.5,
            interval_days=1,
            repetitions=3,
        )
        s.add(r)
        await s.commit()
        await s.refresh(vi)
        await s.refresh(r)
        return vi.id, r.id


async def _get_review(
    factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    review_id: uuid.UUID,
) -> Review:
    async with factory() as s:
        result = await s.execute(
            select(Review).where(
                Review.user_id == user_id,
                Review.id == review_id,
            )
        )
        return result.scalar_one()


def test_apply_ratings_updates_review_state(tmp_path: Path) -> None:
    from app.schemas.batch import RatingIn
    from app.services.rating_sync import apply_ratings

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    _, review_id = asyncio.run(_insert_vocab_with_review(factory, user.id))

    rating_id = uuid.uuid4()
    rating = RatingIn(
        rating_id=rating_id,
        card_id=review_id,
        grade=ReviewQuality.GOOD,
        rated_at=datetime.now(UTC),
    )

    async def go() -> None:
        async with factory() as s:
            await apply_ratings(s, user, [rating])

    asyncio.run(go())

    review = asyncio.run(_get_review(factory, user.id, review_id))
    assert review.repetitions == 4  # was 3, +1 for GOOD
    assert review.last_reviewed_at is not None


def test_apply_ratings_skips_duplicate_rating_id(tmp_path: Path) -> None:
    from app.schemas.batch import RatingIn
    from app.services.rating_sync import apply_ratings

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    _, review_id = asyncio.run(_insert_vocab_with_review(factory, user.id))

    rating_id = uuid.uuid4()
    rating = RatingIn(
        rating_id=rating_id,
        card_id=review_id,
        grade=ReviewQuality.GOOD,
        rated_at=datetime.now(UTC),
    )

    async def apply(r: RatingIn) -> None:
        async with factory() as s:
            await apply_ratings(s, user, [r])

    asyncio.run(apply(rating))
    asyncio.run(apply(rating))  # same rating_id again

    review = asyncio.run(_get_review(factory, user.id, review_id))
    assert review.repetitions == 4  # only incremented once


def test_apply_ratings_returns_applied_and_skipped_counts(tmp_path: Path) -> None:
    from app.schemas.batch import RatingIn, SyncResult
    from app.services.rating_sync import apply_ratings

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    _, review_id = asyncio.run(_insert_vocab_with_review(factory, user.id))

    new_id = uuid.uuid4()
    dup_id = uuid.uuid4()
    new_rating = RatingIn(
        rating_id=new_id,
        card_id=review_id,
        grade=ReviewQuality.HARD,
        rated_at=datetime.now(UTC),
    )
    dup_rating = RatingIn(
        rating_id=dup_id,
        card_id=review_id,
        grade=ReviewQuality.GOOD,
        rated_at=datetime.now(UTC),
    )

    async def go() -> SyncResult:
        async with factory() as s:
            await apply_ratings(s, user, [dup_rating])
            result = await apply_ratings(s, user, [new_rating, dup_rating])
            return result

    result = asyncio.run(go())
    assert result.applied == 1
    assert result.skipped == 1


def test_apply_ratings_reconciles_out_of_order_by_rated_at(tmp_path: Path) -> None:
    from app.schemas.batch import RatingIn
    from app.services.rating_sync import apply_ratings

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    _, review_id = asyncio.run(_insert_vocab_with_review(factory, user.id))

    early = datetime(2026, 1, 1, tzinfo=UTC)
    late = datetime(2026, 1, 2, tzinfo=UTC)

    r1 = RatingIn(
        rating_id=uuid.uuid4(),
        card_id=review_id,
        grade=ReviewQuality.GOOD,
        rated_at=late,
    )
    r2 = RatingIn(
        rating_id=uuid.uuid4(),
        card_id=review_id,
        grade=ReviewQuality.AGAIN,
        rated_at=early,
    )

    async def apply(ratings: list[RatingIn]) -> None:
        async with factory() as s:
            await apply_ratings(s, user, ratings)

    asyncio.run(apply([r1, r2]))  # submitted out of order; service sorts by rated_at

    review = asyncio.run(_get_review(factory, user.id, review_id))
    assert review.repetitions == 1  # AGAIN resets to 0, then GOOD increments to 1
    assert review.interval_days == 1  # GOOD on first rep gives interval 1


def test_apply_ratings_handles_empty_list(tmp_path: Path) -> None:
    from app.schemas.batch import SyncResult
    from app.services.rating_sync import apply_ratings

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))

    async def go() -> SyncResult:
        async with factory() as s:
            return await apply_ratings(s, user, [])

    result = asyncio.run(go())
    assert result.applied == 0
    assert result.skipped == 0
