import asyncio
import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.llm import GeneratedVocabBatch, SimpleVocabExample
from app.services.llm import LLMValidationFailure
from app.workers.content_gen import (
    _generate_personalized,
    _generate_personalized_for_all,
    _generate_shared_pool,
    _run_daily,
)


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


def _user(*, email: str, google_id: str) -> User:
    return User(
        id=uuid.uuid4(),
        email=email,
        google_id=google_id,
        name=email.split("@")[0],
        avatar_url=None,
    )


def _batch(tokens: list[str]) -> GeneratedVocabBatch:
    return GeneratedVocabBatch(
        items=[
            SimpleVocabExample(
                token=t,
                definition=f"A definition for {t} that meets length.",
                example=f"The {t} appeared on the page clearly.",
            )
            for t in tokens
        ]
    )


def test_generate_personalized_skips_when_milestone_already_serviced(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    target_id: uuid.UUID | None = None

    async def _seed() -> None:
        nonlocal target_id
        async with session_factory() as s:
            target = _user(email="t@b.com", google_id="gt")
            target.last_personalized_milestone = 30
            s.add(target)
            await s.flush()
            now = datetime.now(UTC)
            for i in range(30):
                v = VocabItem(
                    id=uuid.uuid4(),
                    token=f"w{i}",
                    language="en",
                    definition="A definition long enough to clear the schema.",
                    example_sentence=f"The w{i} word appears.",
                )
                s.add(v)
                await s.flush()
                s.add(Review(user_id=target.id, vocab_item_id=v.id, last_reviewed_at=now))
            await s.commit()
            target_id = target.id

    asyncio.run(_seed())
    assert target_id is not None

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        result = asyncio.run(_generate_personalized(user_id=str(target_id), count=5))
        mock_cls.assert_not_called()

    assert result["skipped"] == "already_fired_for_milestone"
    assert result["milestone"] == 30


def test_generate_personalized_returns_graceful_failure_on_validation_exhausted(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    target_id: uuid.UUID | None = None

    async def _seed() -> None:
        nonlocal target_id
        async with session_factory() as s:
            t = _user(email="t@b.com", google_id="gt")
            s.add(t)
            await s.commit()
            target_id = t.id

    asyncio.run(_seed())
    assert target_id is not None

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_cls.return_value.complete.side_effect = LLMValidationFailure(
            "fail", attempts=3, last_error=None
        )
        result = asyncio.run(_generate_personalized(user_id=str(target_id), count=5))

    assert result == {"succeeded": 0, "failed": 1, "reason": "validation_exhausted"}


def test_generate_personalized_enrolls_only_target_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    target_id: uuid.UUID | None = None

    async def _seed() -> None:
        nonlocal target_id
        async with session_factory() as s:
            target = _user(email="t@b.com", google_id="gt")
            other = _user(email="o@b.com", google_id="go")
            s.add(target)
            s.add(other)
            await s.commit()
            target_id = target.id

    asyncio.run(_seed())
    assert target_id is not None

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_cls.return_value.complete.return_value = _batch(["apple", "banana"])
        result = asyncio.run(_generate_personalized(user_id=str(target_id), count=2))

    assert result["vocab_created"] == 2
    assert result["reviews_created"] == 2

    async def _check() -> None:
        async with session_factory() as s:
            vocab = (await s.execute(select(VocabItem))).scalars().all()
            assert {v.token for v in vocab} == {"apple", "banana"}
            assert all(v.source == "personalized" for v in vocab)
            reviews = (await s.execute(select(Review))).scalars().all()
            assert {r.user_id for r in reviews} == {target_id}

    asyncio.run(_check())


def test_generate_shared_pool_skips_when_already_ran_today(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            s.add(
                VocabItem(
                    id=uuid.uuid4(),
                    token="already-here",
                    language="en",
                    definition="A definition long enough to clear validation.",
                    example_sentence="The already-here token appears in this example.",
                    source="shared_pool",
                )
            )
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        result = asyncio.run(_generate_shared_pool(count=10))
        mock_cls.assert_not_called()

    assert result == {"skipped": "already_ran_today"}


def test_generate_shared_pool_returns_graceful_failure_on_validation_exhausted(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_cls.return_value.complete.side_effect = LLMValidationFailure(
            "fail", attempts=3, last_error=None
        )
        # Must NOT raise; the task body catches and returns a graceful dict so
        # Celery does not retry on a deterministically broken prompt.
        result = asyncio.run(_generate_shared_pool(count=2))

    assert result == {"succeeded": 0, "failed": 1, "reason": "validation_exhausted"}


def test_generate_shared_pool_inserts_vocab_and_enrolls_all_users(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            s.add(_user(email="a@b.com", google_id="ga"))
            s.add(_user(email="c@d.com", google_id="gc"))
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_cls.return_value.complete.return_value = _batch(["apple", "banana", "cherry"])
        result = asyncio.run(_generate_shared_pool(count=3))

    assert result["vocab_created"] == 3
    assert result["reviews_created"] == 6

    async def _check() -> None:
        async with session_factory() as s:
            vocab = (await s.execute(select(VocabItem))).scalars().all()
            assert {v.token for v in vocab} == {"apple", "banana", "cherry"}
            assert all(v.source == "shared_pool" for v in vocab)
            reviews = (await s.execute(select(Review))).scalars().all()
            assert len(reviews) == 6

    asyncio.run(_check())


def test_generate_personalized_for_all_creates_vocab_for_each_user(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            u1 = User(
                id=uuid.uuid4(),
                email="a@b.com",
                google_id="ga",
                name="a",
                interest_tags=["food"],
            )
            u2 = User(
                id=uuid.uuid4(),
                email="c@d.com",
                google_id="gc",
                name="c",
                interest_tags=["animals"],
            )
            s.add_all([u1, u2])
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        mock_instance = mock_cls.return_value
        mock_instance.complete.side_effect = [
            _batch(["pizza", "pasta"]),
            _batch(["elephant", "giraffe"]),
        ]
        result = asyncio.run(_generate_personalized_for_all(count=2))

    assert result["total_vocab_created"] == 4
    assert result["users_processed"] == 2

    async def _check() -> None:
        async with session_factory() as s:
            vocab = (await s.execute(select(VocabItem))).scalars().all()
            assert len(vocab) == 4
            assert all(v.source == "personalized" for v in vocab)
            reviews = (await s.execute(select(Review))).scalars().all()
            assert len(reviews) == 4
            user_ids = {str(r.user_id) for r in reviews}
            assert len(user_ids) == 2

    asyncio.run(_check())


def test_generate_personalized_for_all_skips_on_same_day_idempotency(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def _seed() -> None:
        async with session_factory() as s:
            u = _user(email="u@b.com", google_id="gu")
            s.add(u)
            await s.commit()
            vocab = VocabItem(
                id=uuid.uuid4(),
                token="already-done",
                language="en",
                definition="A definition long enough to clear validation.",
                example_sentence="The already-done token appears in this example.",
                source="personalized",
            )
            s.add(vocab)
            await s.flush()
            s.add(Review(user_id=u.id, vocab_item_id=vocab.id, due_at=datetime.now(UTC)))
            await s.commit()

    asyncio.run(_seed())

    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        result = asyncio.run(_generate_personalized_for_all(count=2))
        mock_cls.assert_not_called()

    assert result == {"total_vocab_created": 0, "users_processed": 0}


def test_generate_personalized_for_all_handles_no_users(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    with (
        patch("app.workers.content_gen.SessionLocal", session_factory),
        patch("app.workers.content_gen.LLMClient") as mock_cls,
    ):
        result = asyncio.run(_generate_personalized_for_all(count=5))
        mock_cls.assert_not_called()

    assert result == {"total_vocab_created": 0, "users_processed": 0}
