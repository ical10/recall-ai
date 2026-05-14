import asyncio
import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.vocab_item import VocabItem
from app.schemas.llm import SimpleVocabExample
from app.services.llm import LLMValidationFailure
from app.workers.content_gen import _run_daily


@pytest.fixture()
def session_factory() -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)

    async def _setup() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_setup())
    return async_sessionmaker(engine, expire_on_commit=False)


def _item(
    *,
    token: str = "word",
    language: str = "id",
    definition: str = "",
    example_sentence: str | None = None,
    enrichment_attempts: int = 0,
) -> VocabItem:
    now = datetime.now(UTC)
    item = VocabItem(
        id=uuid.uuid4(),
        token=token,
        language=language,
        definition=definition,
        example_sentence=example_sentence,
        enrichment_attempts=enrichment_attempts,
    )
    item.created_at = now
    item.updated_at = now
    return item


def _canned_result(token: str) -> SimpleVocabExample:
    return SimpleVocabExample(
        token=token,
        definition="A word meaning something interesting and worth knowing.",
        example=f"The {token} was clearly visible from afar.",
    )


def test_run_daily_persists_definition_and_example_to_vocab_item(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            s.add_all([_item(token="word1"), _item(token="word2")])
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_llm = mock_cls.return_value
        mock_llm.complete.side_effect = lambda prompt, schema: _canned_result(
            "word1" if "word1" in prompt else "word2"
        )
        result = asyncio.run(_run_daily(batch_size=2))

    assert result == {"succeeded": 2, "failed": 0}

    async def _check() -> None:
        async with session_factory() as s:
            rows = (await s.execute(select(VocabItem))).scalars().all()
            for row in rows:
                assert row.definition != ""
                assert row.example_sentence is not None

    asyncio.run(_check())


def test_run_daily_returns_zero_counts_when_no_unenriched(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            s.add(
                _item(
                    token="done",
                    definition="A word fully enriched already.",
                    example_sentence="This word is done.",
                )
            )
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        result = asyncio.run(_run_daily(batch_size=25))
        mock_cls.assert_not_called()

    assert result == {"succeeded": 0, "failed": 0}


def test_run_daily_skips_failed_items_and_continues_batch(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            s.add_all([_item(token="w1"), _item(token="w2"), _item(token="w3")])
            await s.commit()

    asyncio.run(_seed())

    call_count = 0

    def side_effect(prompt: str, schema: object) -> SimpleVocabExample:
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise LLMValidationFailure("fail", attempts=3, last_error=None)
        token = "w1" if call_count == 1 else "w3"
        return _canned_result(token)

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_cls.return_value.complete.side_effect = side_effect
        result = asyncio.run(_run_daily(batch_size=3))

    assert result == {"succeeded": 2, "failed": 1}


def test_run_daily_respects_batch_size(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            s.add_all([_item(token=f"word{i}") for i in range(10)])
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_cls.return_value.complete.side_effect = lambda prompt, schema: _canned_result(
            next(t for t in [f"word{i}" for i in range(10)] if t in prompt)
        )
        result = asyncio.run(_run_daily(batch_size=3))

    assert mock_cls.return_value.complete.call_count == 3
    assert result["succeeded"] == 3


def test_run_daily_increments_attempts_on_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            s.add(_item(token="failword", enrichment_attempts=0))
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_cls.return_value.complete.side_effect = LLMValidationFailure(
            "fail", attempts=3, last_error=None
        )
        asyncio.run(_run_daily(batch_size=1))

    async def _check() -> None:
        async with session_factory() as s:
            row = (
                await s.execute(select(VocabItem).where(VocabItem.token == "failword"))
            ).scalar_one()
            assert row.enrichment_attempts == 1
            assert row.last_enrichment_attempted_at is not None

    asyncio.run(_check())


def test_run_daily_resets_attempts_on_success(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            s.add(_item(token="recover", enrichment_attempts=2))
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_cls.return_value.complete.return_value = _canned_result("recover")
        asyncio.run(_run_daily(batch_size=1))

    async def _check() -> None:
        async with session_factory() as s:
            row = (
                await s.execute(select(VocabItem).where(VocabItem.token == "recover"))
            ).scalar_one()
            assert row.enrichment_attempts == 0
            assert row.definition != ""

    asyncio.run(_check())


def test_run_daily_logs_content_gen_item_failed_on_failure(
    session_factory: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
) -> None:
    item_id: str | None = None

    async def _seed() -> None:
        nonlocal item_id
        async with session_factory() as s:
            item = _item(token="failword", enrichment_attempts=0)
            item_id = str(item.id)
            s.add(item)
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
        caplog.at_level(logging.WARNING, logger="app.workers.content_gen"),
    ):
        mock_cls.return_value.complete.side_effect = LLMValidationFailure(
            "fail", attempts=3, last_error=None
        )
        asyncio.run(_run_daily(batch_size=1))

    failed_records = [r for r in caplog.records if r.message == "content_gen_item_failed"]
    assert len(failed_records) == 1
    r = failed_records[0]
    assert getattr(r, "vocab_item_id", None) == item_id
    assert getattr(r, "attempts", None) == 3
    assert getattr(r, "total_attempts", None) == 1
