import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.vocab_item import VocabItem
from app.services.selection import (
    COOLDOWN_DAYS,
    MAX_ATTEMPTS_BEFORE_COOLDOWN,
    select_unenriched,
)


@pytest.fixture()
def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _setup() -> AsyncSession:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        return maker()

    return asyncio.run(_setup())


def _item(
    *,
    token: str = "word",
    language: str = "id",
    definition: str = "",
    example_sentence: str | None = None,
    enrichment_attempts: int = 0,
    last_enrichment_attempted_at: datetime | None = None,
    created_at: datetime | None = None,
) -> VocabItem:
    now = datetime.now(UTC)
    item = VocabItem(
        id=uuid.uuid4(),
        token=token,
        language=language,
        definition=definition,
        example_sentence=example_sentence,
        enrichment_attempts=enrichment_attempts,
        last_enrichment_attempted_at=last_enrichment_attempted_at,
    )
    item.created_at = created_at or now
    item.updated_at = now
    return item


def test_select_unenriched_returns_only_items_missing_definition_or_example(
    session: AsyncSession,
) -> None:
    async def _run() -> None:
        async with session:
            unenriched = _item(token="missing_def", definition="", example_sentence=None)
            enriched = _item(
                token="has_def",
                definition="A real definition here.",
                example_sentence="Has example.",
            )
            session.add(unenriched)
            session.add(enriched)
            await session.commit()

            results = await select_unenriched(session, limit=10)
            tokens = {r.token for r in results}
            assert "missing_def" in tokens
            assert "has_def" not in tokens

    asyncio.run(_run())


def test_select_unenriched_returns_item_with_definition_but_no_example(
    session: AsyncSession,
) -> None:
    async def _run() -> None:
        async with session:
            item = _item(
                token="needs_example",
                definition="A valid definition.",
                example_sentence=None,
            )
            session.add(item)
            await session.commit()

            results = await select_unenriched(session, limit=10)
            assert any(r.token == "needs_example" for r in results)

    asyncio.run(_run())


def test_select_unenriched_respects_limit_and_orders_by_created_at(
    session: AsyncSession,
) -> None:
    async def _run() -> None:
        async with session:
            now = datetime.now(UTC)
            older = _item(token="older", created_at=now - timedelta(hours=2))
            newer = _item(token="newer", created_at=now)
            newest = _item(token="newest", created_at=now + timedelta(hours=1))
            session.add_all([newer, newest, older])
            await session.commit()

            results = await select_unenriched(session, limit=2)
            assert len(results) == 2
            assert results[0].token == "older"
            assert results[1].token == "newer"

    asyncio.run(_run())


def test_select_unenriched_returns_empty_list_when_limit_zero(
    session: AsyncSession,
) -> None:
    async def _run() -> None:
        async with session:
            session.add(_item(token="word"))
            await session.commit()
            results = await select_unenriched(session, limit=0)
            assert results == []

    asyncio.run(_run())


def test_select_unenriched_returns_empty_list_when_all_enriched(
    session: AsyncSession,
) -> None:
    async def _run() -> None:
        async with session:
            session.add(
                _item(
                    token="rich",
                    definition="Full definition here.",
                    example_sentence="Has example.",
                )
            )
            await session.commit()
            results = await select_unenriched(session, limit=10)
            assert results == []

    asyncio.run(_run())


def test_select_unenriched_skips_items_in_cooldown(
    session: AsyncSession,
) -> None:
    async def _run() -> None:
        async with session:
            now = datetime.now(UTC)
            cooldown_item = _item(
                token="cooldown",
                enrichment_attempts=MAX_ATTEMPTS_BEFORE_COOLDOWN,
                last_enrichment_attempted_at=now - timedelta(days=1),
            )
            session.add(cooldown_item)
            await session.commit()

            results = await select_unenriched(session, limit=10)
            assert not any(r.token == "cooldown" for r in results)

    asyncio.run(_run())


def test_select_unenriched_returns_item_after_cooldown_expires(
    session: AsyncSession,
) -> None:
    async def _run() -> None:
        async with session:
            now = datetime.now(UTC)
            expired = _item(
                token="expired_cooldown",
                enrichment_attempts=MAX_ATTEMPTS_BEFORE_COOLDOWN,
                last_enrichment_attempted_at=now - timedelta(days=COOLDOWN_DAYS + 1),
            )
            session.add(expired)
            await session.commit()

            results = await select_unenriched(session, limit=10)
            assert any(r.token == "expired_cooldown" for r in results)

    asyncio.run(_run())


def test_select_unenriched_returns_never_attempted_item_regardless_of_attempts_field(
    session: AsyncSession,
) -> None:
    async def _run() -> None:
        async with session:
            item = _item(
                token="seed_item",
                enrichment_attempts=0,
                last_enrichment_attempted_at=None,
            )
            session.add(item)
            await session.commit()

            results = await select_unenriched(session, limit=10)
            assert any(r.token == "seed_item" for r in results)

    asyncio.run(_run())
