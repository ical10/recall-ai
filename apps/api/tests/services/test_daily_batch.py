"""Tests for build_daily_batch — due Review + VocabItem denormalized query."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


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
    example_sentence: str | None = None,
) -> uuid.UUID:
    async with factory() as s:
        vi = VocabItem(
            token=token,
            language="en",
            definition=definition,
            example_sentence=example_sentence,
        )
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
    ease_factor: float = 2.5,
    interval_days: int = 1,
    repetitions: int = 0,
    suspended: bool = False,
) -> None:
    async with factory() as s:
        s.add(
            Review(
                user_id=user_id,
                vocab_item_id=vocab_id,
                due_at=due_at,
                ease_factor=ease_factor,
                interval_days=interval_days,
                repetitions=repetitions,
                suspended=suspended,
            )
        )
        await s.commit()


def test_build_daily_batch_returns_correct_shape(tmp_path: Path) -> None:
    from app.schemas.batch import DailyBatch
    from app.services.daily_batch import build_daily_batch

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    past = datetime(2020, 1, 1, tzinfo=UTC)
    vid = asyncio.run(_insert_vocab(factory, "test", "a test word", "example here"))

    async def go() -> None:
        await _insert_review(factory, user.id, vid, due_at=past)

    asyncio.run(go())

    async def query() -> DailyBatch:
        async with factory() as s:
            return await build_daily_batch(s, user)

    batch = asyncio.run(query())
    assert len(batch.cards) == 1
    card = batch.cards[0]
    assert card.token == "test"
    assert card.definition == "a test word"
    assert card.example_sentence == "example here"
    assert card.ease_factor == 2.5
    assert card.interval_days == 1
    assert card.repetitions == 0
    assert card.word_audio_url is None
    assert card.example_audio_url is None


def test_build_daily_batch_excludes_future_due(tmp_path: Path) -> None:
    from app.schemas.batch import DailyBatch
    from app.services.daily_batch import build_daily_batch

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    past = datetime(2020, 1, 1, tzinfo=UTC)
    future = datetime(2099, 1, 1, tzinfo=UTC)

    async def go() -> None:
        vid1 = await _insert_vocab(factory, "due")
        vid2 = await _insert_vocab(factory, "notyet")
        await _insert_review(factory, user.id, vid1, due_at=past)
        await _insert_review(factory, user.id, vid2, due_at=future)

    asyncio.run(go())

    async def query() -> DailyBatch:
        async with factory() as s:
            return await build_daily_batch(s, user)

    batch = asyncio.run(query())
    assert len(batch.cards) == 1
    assert batch.cards[0].token == "due"


def test_build_daily_batch_excludes_suspended(tmp_path: Path) -> None:
    from app.schemas.batch import DailyBatch
    from app.services.daily_batch import build_daily_batch

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    past = datetime(2020, 1, 1, tzinfo=UTC)

    async def go() -> None:
        vid1 = await _insert_vocab(factory, "active")
        vid2 = await _insert_vocab(factory, "suspended")
        await _insert_review(factory, user.id, vid1, due_at=past)
        await _insert_review(factory, user.id, vid2, due_at=past, suspended=True)

    asyncio.run(go())

    async def query() -> DailyBatch:
        async with factory() as s:
            return await build_daily_batch(s, user)

    batch = asyncio.run(query())
    assert len(batch.cards) == 1
    assert batch.cards[0].token == "active"


def test_build_daily_batch_excludes_empty_definition(tmp_path: Path) -> None:
    from app.schemas.batch import DailyBatch
    from app.services.daily_batch import build_daily_batch

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    past = datetime(2020, 1, 1, tzinfo=UTC)

    async def go() -> None:
        vid1 = await _insert_vocab(factory, "defined", "has def")
        vid2 = await _insert_vocab(factory, "empty", "")
        await _insert_review(factory, user.id, vid1, due_at=past)
        await _insert_review(factory, user.id, vid2, due_at=past)

    asyncio.run(go())

    async def query() -> DailyBatch:
        async with factory() as s:
            return await build_daily_batch(s, user)

    batch = asyncio.run(query())
    assert len(batch.cards) == 1
    assert batch.cards[0].token == "defined"


def test_build_daily_batch_isolated_per_user(tmp_path: Path) -> None:
    from app.schemas.batch import DailyBatch
    from app.services.daily_batch import build_daily_batch

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user_a = asyncio.run(_insert_user(factory, "a@test.com"))
    user_b = asyncio.run(_insert_user(factory, "b@test.com"))
    past = datetime(2020, 1, 1, tzinfo=UTC)

    async def go() -> None:
        vid_a = await _insert_vocab(factory, "token_a")
        vid_b = await _insert_vocab(factory, "token_b")
        await _insert_review(factory, user_a.id, vid_a, due_at=past)
        await _insert_review(factory, user_b.id, vid_b, due_at=past)

    asyncio.run(go())

    async def query(user: User) -> DailyBatch:
        async with factory() as s:
            return await build_daily_batch(s, user)

    batch_a = asyncio.run(query(user_a))
    batch_b = asyncio.run(query(user_b))
    assert len(batch_a.cards) == 1
    assert batch_a.cards[0].token == "token_a"
    assert len(batch_b.cards) == 1
    assert batch_b.cards[0].token == "token_b"


def test_build_daily_batch_returns_empty_for_no_due_cards(tmp_path: Path) -> None:
    from app.schemas.batch import DailyBatch
    from app.services.daily_batch import build_daily_batch

    factory = _make_factory(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))

    async def query() -> DailyBatch:
        async with factory() as s:
            return await build_daily_batch(s, user)

    batch = asyncio.run(query())
    assert batch.cards == []
