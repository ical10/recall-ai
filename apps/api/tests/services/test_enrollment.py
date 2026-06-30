"""Tests for Enrollment: persist new shared Vocab Items + create per-user Reviews."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample
from app.services.enrollment import enroll_new_vocab


@pytest.fixture()
def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())
    return async_sessionmaker(engine, expire_on_commit=False)


def _example(token: str) -> SimpleVocabExample:
    return SimpleVocabExample(
        token=token,
        definition=f"A clear test definition for {token} that is long enough.",
        example=f"Here is the word {token} used in a sentence.",
    )


async def _add_users(factory: async_sessionmaker[AsyncSession], n: int) -> list[User]:
    async with factory() as s:
        users = [User(email=f"u{i}@t.com", google_id=f"gid-{i}", name=f"U{i}") for i in range(n)]
        s.add_all(users)
        await s.commit()
        for u in users:
            await s.refresh(u)
        return users


def test_enroll_creates_vocab_and_one_review_per_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    users = asyncio.run(_add_users(session_factory, 2))
    user_ids = [u.id for u in users]

    async def go() -> tuple[int, int]:
        async with session_factory() as s:
            result = await enroll_new_vocab(
                s, [_example("alpha"), _example("beta")], source="shared_pool", user_ids=user_ids
            )
            await s.commit()
            return result

    vocab_created, reviews_created = asyncio.run(go())
    assert vocab_created == 2
    assert reviews_created == 4  # 2 vocab x 2 users

    async def counts() -> tuple[int, int]:
        async with session_factory() as s:
            v = (await s.execute(select(func.count(VocabItem.id)))).scalar_one()
            r = (await s.execute(select(func.count(Review.id)))).scalar_one()
            return int(v), int(r)

    assert asyncio.run(counts()) == (2, 4)


def test_enroll_dedupes_existing_token(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    users = asyncio.run(_add_users(session_factory, 1))
    user_ids = [u.id for u in users]

    async def seed_existing() -> None:
        async with session_factory() as s:
            s.add(VocabItem(token="dup", language="en", definition="already here", source="user"))
            await s.commit()

    asyncio.run(seed_existing())

    async def go() -> tuple[int, int]:
        async with session_factory() as s:
            result = await enroll_new_vocab(
                s, [_example("dup"), _example("fresh")], source="shared_pool", user_ids=user_ids
            )
            await s.commit()
            return result

    vocab_created, reviews_created = asyncio.run(go())
    assert vocab_created == 1  # only "fresh"; "dup" hit the unique constraint
    assert reviews_created == 1
