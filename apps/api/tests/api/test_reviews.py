"""Tests for the review session endpoints (Slice B)."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    from starlette.middleware.sessions import SessionMiddleware

    from app.api.reviews import router as reviews_router

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await engine.dispose()

    app = FastAPI(lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key="test-secret",
        session_cookie="recallai_session",
        max_age=3600,
        same_site="lax",
        https_only=False,
    )

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.include_router(reviews_router)
    return app, factory


async def _insert_user(
    factory: async_sessionmaker[AsyncSession], email: str = "user@test.com"
) -> User:
    async with factory() as s:
        u = User(email=email, google_id=f"gid-{email}", name="Test")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _insert_vocab(
    factory: async_sessionmaker[AsyncSession],
    token: str,
    definition: str = "a test word",
) -> VocabItem:
    async with factory() as s:
        vi = VocabItem(token=token, language="en", definition=definition)
        s.add(vi)
        await s.commit()
        await s.refresh(vi)
        return vi


async def _insert_review(
    factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    vocab_id: uuid.UUID,
    *,
    due_at: datetime | None = None,
    suspended: bool = False,
    ease_factor: float = 2.5,
    interval_days: int = 0,
    repetitions: int = 0,
) -> Review:
    async with factory() as s:
        r = Review(
            user_id=user_id,
            vocab_item_id=vocab_id,
            due_at=due_at,
            suspended=suspended,
            ease_factor=ease_factor,
            interval_days=interval_days,
            repetitions=repetitions,
        )
        s.add(r)
        await s.commit()
        await s.refresh(r)
        return r


def test_get_review_returns_oldest_due_card_for_user(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> None:
        vi = await _insert_vocab(factory, "ephemeral")
        await _insert_review(factory, user.id, vi.id, due_at=datetime.now(UTC))

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/review")
    assert resp.status_code == 200
    assert "ephemeral" in resp.text


def test_get_review_renders_done_when_no_due_reviews(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.get("/review")
    assert resp.status_code == 200
    assert "All caught up" in resp.text


def test_get_review_excludes_suspended_reviews(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> None:
        vi = await _insert_vocab(factory, "suspended_word")
        await _insert_review(factory, user.id, vi.id, due_at=datetime.now(UTC), suspended=True)

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/review")
    assert "All caught up" in resp.text


def test_get_review_treats_null_due_at_as_due(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> None:
        vi = await _insert_vocab(factory, "never_reviewed")
        await _insert_review(factory, user.id, vi.id, due_at=None)

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/review")
    assert "never_reviewed" in resp.text


def test_get_review_excludes_other_users_reviews(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user_a = asyncio.run(_insert_user(factory, "a@test.com"))
    user_b = asyncio.run(_insert_user(factory, "b@test.com"))
    app.dependency_overrides[get_current_user] = lambda: user_a

    async def setup() -> None:
        vi = await _insert_vocab(factory, "other_user_word")
        await _insert_review(factory, user_b.id, vi.id, due_at=datetime.now(UTC))

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/review")
    assert "All caught up" in resp.text


def test_get_review_skips_vocab_with_empty_definition(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> None:
        vi = await _insert_vocab(factory, "pending_word", definition="")
        await _insert_review(factory, user.id, vi.id, due_at=datetime.now(UTC))

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/review")
    assert "All caught up" in resp.text


def test_reveal_returns_partial_with_definition(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "serendipity", definition="happy accident")
        r = await _insert_review(factory, user.id, vi.id, due_at=datetime.now(UTC))
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get(f"/review/{review_id}/reveal")
    assert resp.status_code == 200
    assert "happy accident" in resp.text
    assert "serendipity" in resp.text


def test_reveal_404_when_not_owner(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user_a = asyncio.run(_insert_user(factory, "a@test.com"))
    user_b = asyncio.run(_insert_user(factory, "b@test.com"))
    app.dependency_overrides[get_current_user] = lambda: user_a

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "not_mine")
        r = await _insert_review(factory, user_b.id, vi.id, due_at=datetime.now(UTC))
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get(f"/review/{review_id}/reveal")
    assert resp.status_code == 404


def test_rate_updates_review_with_sm2_output(tmp_path: Path) -> None:
    from app.models.review import ReviewQuality
    from app.schemas.review import ReviewState
    from app.services.sm2 import compute_next_review

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "good_word")
        r = await _insert_review(
            factory,
            user.id,
            vi.id,
            due_at=datetime.now(UTC),
            ease_factor=2.5,
            interval_days=0,
            repetitions=0,
        )
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.post(f"/review/{review_id}/rate", data={"quality": 4})
    assert resp.status_code == 200

    async def fetch() -> Review:
        from sqlalchemy import select

        async with factory() as s:
            return (await s.execute(select(Review).where(Review.id == review_id))).scalar_one()

    updated = asyncio.run(fetch())
    expected = compute_next_review(
        ReviewState(ease_factor=2.5, interval_days=0, repetitions=0),
        ReviewQuality.GOOD,
    )
    assert abs(updated.ease_factor - expected.ease_factor) < 0.001
    assert updated.interval_days == expected.interval_days
    assert updated.repetitions == expected.repetitions


def test_rate_quality_again_resets_repetitions(tmp_path: Path) -> None:
    from sqlalchemy import select

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "again_word")
        r = await _insert_review(
            factory,
            user.id,
            vi.id,
            due_at=datetime.now(UTC),
            repetitions=3,
            interval_days=12,
        )
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        c.post(f"/review/{review_id}/rate", data={"quality": 0})

    async def fetch() -> Review:
        async with factory() as s:
            return (await s.execute(select(Review).where(Review.id == review_id))).scalar_one()

    updated = asyncio.run(fetch())
    assert updated.repetitions == 0
    assert updated.interval_days == 1


def test_rate_quality_hard_keeps_repetition_progression(tmp_path: Path) -> None:
    from sqlalchemy import select

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "hard_word")
        r = await _insert_review(
            factory,
            user.id,
            vi.id,
            due_at=datetime.now(UTC),
            repetitions=3,
            interval_days=12,
        )
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        c.post(f"/review/{review_id}/rate", data={"quality": 2})

    async def fetch() -> Review:
        async with factory() as s:
            return (await s.execute(select(Review).where(Review.id == review_id))).scalar_one()

    updated = asyncio.run(fetch())
    assert updated.repetitions == 4
    assert updated.interval_days == round(12 * 1.2)


def test_rate_advances_to_next_due_card_in_response(tmp_path: Path) -> None:
    from datetime import timedelta

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi1 = await _insert_vocab(factory, "first_word")
        vi2 = await _insert_vocab(factory, "second_word")
        now = datetime.now(UTC)
        r1 = await _insert_review(factory, user.id, vi1.id, due_at=now - timedelta(seconds=2))
        await _insert_review(factory, user.id, vi2.id, due_at=now - timedelta(seconds=1))
        return r1.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.post(f"/review/{review_id}/rate", data={"quality": 4})
    assert resp.status_code == 200
    assert "second_word" in resp.text


def test_rate_returns_done_partial_when_no_more_due(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "only_word")
        r = await _insert_review(factory, user.id, vi.id, due_at=datetime.now(UTC))
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.post(f"/review/{review_id}/rate", data={"quality": 4})
    assert "All caught up" in resp.text


def test_rate_again_does_not_requeue_before_delay_elapses(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "only_again")
        r = await _insert_review(factory, user.id, vi.id, due_at=datetime.now(UTC))
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        resp1 = c.post(f"/review/{review_id}/rate", data={"quality": 0})
        assert "All caught up" in resp1.text
        resp2 = c.get("/review")
        assert "All caught up" in resp2.text


def test_rate_other_qualities_do_not_requeue(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "good_again_word")
        r = await _insert_review(factory, user.id, vi.id, due_at=datetime.now(UTC))
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        c.post(f"/review/{review_id}/rate", data={"quality": 4})
        resp = c.get("/review")
    assert "All caught up" in resp.text


def test_rate_rejects_invalid_quality_value(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "invalid_q_word")
        r = await _insert_review(factory, user.id, vi.id, due_at=datetime.now(UTC))
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.post(f"/review/{review_id}/rate", data={"quality": 3})
    assert resp.status_code == 422


def test_rate_404_when_not_owner(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user_a = asyncio.run(_insert_user(factory, "a@test.com"))
    user_b = asyncio.run(_insert_user(factory, "b@test.com"))
    app.dependency_overrides[get_current_user] = lambda: user_a

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "not_mine_rate")
        r = await _insert_review(factory, user_b.id, vi.id, due_at=datetime.now(UTC))
        return r.id

    review_id = asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.post(f"/review/{review_id}/rate", data={"quality": 4})
    assert resp.status_code == 404


def test_rate_sets_last_reviewed_at_and_due_at(tmp_path: Path) -> None:
    from datetime import timedelta

    from sqlalchemy import select

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vi = await _insert_vocab(factory, "timestamp_word")
        r = await _insert_review(
            factory,
            user.id,
            vi.id,
            due_at=datetime.now(UTC),
            interval_days=5,
        )
        return r.id

    review_id = asyncio.run(setup())
    before = datetime.now(UTC)
    with TestClient(app) as c:
        c.post(f"/review/{review_id}/rate", data={"quality": 4})
    after = datetime.now(UTC)

    async def fetch() -> Review:
        async with factory() as s:
            return (await s.execute(select(Review).where(Review.id == review_id))).scalar_one()

    updated = asyncio.run(fetch())
    assert updated.last_reviewed_at is not None
    last_reviewed = updated.last_reviewed_at.replace(tzinfo=UTC)
    assert before <= last_reviewed <= after
    expected_due = last_reviewed + timedelta(days=updated.interval_days)
    assert abs((updated.due_at.replace(tzinfo=UTC) - expected_due).total_seconds()) < 2


def test_rate_again_requeues_card_after_delay_elapses(tmp_path: Path) -> None:
    """Rate first card Again → second card shown. After AGAIN_REQUEUE_MINUTES elapses
    (simulated via time-mock), GET /review returns the first card from again_queue."""
    from datetime import timedelta
    from unittest.mock import patch

    from app.api.reviews import AGAIN_REQUEUE_MINUTES

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    t0 = datetime.now(UTC)

    async def setup() -> uuid.UUID:
        vi1 = await _insert_vocab(factory, "first_requeue")
        vi2 = await _insert_vocab(factory, "second_requeue")
        r1 = await _insert_review(factory, user.id, vi1.id, due_at=t0 - timedelta(seconds=2))
        await _insert_review(factory, user.id, vi2.id, due_at=t0 - timedelta(seconds=1))
        return r1.id

    r1_id = asyncio.run(setup())

    with TestClient(app) as c:
        with patch("app.api.reviews.datetime") as mock_dt:
            mock_dt.now.return_value = t0
            mock_dt.fromisoformat = datetime.fromisoformat
            resp1 = c.post(f"/review/{r1_id}/rate", data={"quality": 0})
        assert resp1.status_code == 200
        assert "second_requeue" in resp1.text

        t1 = t0 + timedelta(minutes=AGAIN_REQUEUE_MINUTES + 1)
        with patch("app.api.reviews.datetime") as mock_dt:
            mock_dt.now.return_value = t1
            mock_dt.fromisoformat = datetime.fromisoformat
            resp2 = c.get("/review")
        assert "first_requeue" in resp2.text


def test_pick_next_skips_resuspended_card(tmp_path: Path) -> None:
    """Rating a card 'Again' enqueues it. If the Review is suspended before
    the requeue delay elapses, the cookie path must not surface it.
    Without the filter fix, the suspended card would be served from the cookie."""
    from datetime import timedelta
    from unittest.mock import patch

    from sqlalchemy import update

    from app.api.reviews import AGAIN_REQUEUE_MINUTES

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    t0 = datetime.now(UTC)

    async def setup() -> tuple[uuid.UUID, uuid.UUID]:
        vi1 = await _insert_vocab(factory, "again_card")
        vi2 = await _insert_vocab(factory, "fallback_card")
        r1 = await _insert_review(factory, user.id, vi1.id, due_at=t0 - timedelta(seconds=2))
        r2 = await _insert_review(factory, user.id, vi2.id, due_at=t0 - timedelta(seconds=1))
        return r1.id, r2.id

    r1_id, r2_id = asyncio.run(setup())

    with TestClient(app) as c:
        with patch("app.api.reviews.datetime") as mock_dt:
            mock_dt.now.return_value = t0
            mock_dt.fromisoformat = datetime.fromisoformat
            resp1 = c.post(f"/review/{r1_id}/rate", data={"quality": 0})
        assert resp1.status_code == 200
        assert "fallback_card" in resp1.text

        with patch("app.api.reviews.datetime") as mock_dt:
            mock_dt.now.return_value = t0
            mock_dt.fromisoformat = datetime.fromisoformat
            resp1b = c.post(f"/review/{r2_id}/rate", data={"quality": 4})
        assert resp1b.status_code == 200

        async def suspend_review() -> None:
            async with factory() as s:
                await s.execute(update(Review).where(Review.id == r1_id).values(suspended=True))
                await s.commit()

        asyncio.run(suspend_review())

        t1 = t0 + timedelta(minutes=AGAIN_REQUEUE_MINUTES + 1)
        with patch("app.api.reviews.datetime") as mock_dt:
            mock_dt.now.return_value = t1
            mock_dt.fromisoformat = datetime.fromisoformat
            resp2 = c.get("/review")
        assert "All caught up" in resp2.text


def test_pick_next_skips_empty_definition_card(tmp_path: Path) -> None:
    """Rating a card 'Again' enqueues it. If the VocabItem definition becomes empty
    (Pending state) before the requeue delay elapses, the cookie path must not surface it.
    Without the filter fix, the pending card would be served from the cookie."""
    from datetime import timedelta
    from unittest.mock import patch

    from sqlalchemy import select, update

    from app.api.reviews import AGAIN_REQUEUE_MINUTES

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    t0 = datetime.now(UTC)

    async def setup() -> tuple[uuid.UUID, uuid.UUID]:
        vi1 = await _insert_vocab(factory, "pending_card", definition="original definition")
        vi2 = await _insert_vocab(factory, "fallback_card2")
        r1 = await _insert_review(factory, user.id, vi1.id, due_at=t0 - timedelta(seconds=2))
        r2 = await _insert_review(factory, user.id, vi2.id, due_at=t0 - timedelta(seconds=1))
        return r1.id, r2.id

    r1_id, r2_id = asyncio.run(setup())

    with TestClient(app) as c:
        with patch("app.api.reviews.datetime") as mock_dt:
            mock_dt.now.return_value = t0
            mock_dt.fromisoformat = datetime.fromisoformat
            resp1 = c.post(f"/review/{r1_id}/rate", data={"quality": 0})
        assert resp1.status_code == 200
        assert "fallback_card2" in resp1.text

        with patch("app.api.reviews.datetime") as mock_dt:
            mock_dt.now.return_value = t0
            mock_dt.fromisoformat = datetime.fromisoformat
            resp1b = c.post(f"/review/{r2_id}/rate", data={"quality": 4})
        assert resp1b.status_code == 200

        async def clear_definition() -> None:
            async with factory() as s:
                r = (await s.execute(select(Review).where(Review.id == r1_id))).scalar_one()
                await s.execute(
                    update(VocabItem).where(VocabItem.id == r.vocab_item_id).values(definition="")
                )
                await s.commit()

        asyncio.run(clear_definition())

        t1 = t0 + timedelta(minutes=AGAIN_REQUEUE_MINUTES + 1)
        with patch("app.api.reviews.datetime") as mock_dt:
            mock_dt.now.return_value = t1
            mock_dt.fromisoformat = datetime.fromisoformat
            resp2 = c.get("/review")
        assert "All caught up" in resp2.text


def test_rate_enqueues_personalized_at_30th_completed_review(tmp_path: Path) -> None:
    from unittest.mock import patch as _patch

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        now = datetime.now(UTC)
        async with factory() as s:
            for i in range(29):
                v = VocabItem(
                    token=f"prior{i}",
                    language="en",
                    definition=f"definition long enough for prior{i} validation.",
                    example_sentence=f"The prior{i} word appears here.",
                )
                s.add(v)
                await s.flush()
                s.add(
                    Review(
                        user_id=user.id,
                        vocab_item_id=v.id,
                        last_reviewed_at=now,
                    )
                )
            target_vocab = VocabItem(
                token="target",
                language="en",
                definition="The 30th completed-review trigger word.",
                example_sentence="The target word appears here.",
            )
            s.add(target_vocab)
            await s.flush()
            r = Review(user_id=user.id, vocab_item_id=target_vocab.id, due_at=now)
            s.add(r)
            await s.commit()
            await s.refresh(r)
            return r.id

    review_id = asyncio.run(setup())

    with (
        _patch("app.api.reviews.celery_app.send_task") as mock_send,
        TestClient(app) as c,
    ):
        resp = c.post(f"/review/{review_id}/rate", data={"quality": 4})

    assert resp.status_code == 200
    mock_send.assert_called_once()
    _, kwargs = mock_send.call_args
    assert kwargs["kwargs"]["user_id"] == str(user.id)


def test_rate_does_not_enqueue_personalized_at_non_milestone(tmp_path: Path) -> None:
    from unittest.mock import patch as _patch

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        now = datetime.now(UTC)
        async with factory() as s:
            for i in range(28):
                v = VocabItem(
                    token=f"non{i}",
                    language="en",
                    definition=f"long-enough definition for non{i} validation.",
                    example_sentence=f"The non{i} word appears here.",
                )
                s.add(v)
                await s.flush()
                s.add(Review(user_id=user.id, vocab_item_id=v.id, last_reviewed_at=now))
            target_vocab = VocabItem(
                token="non_target",
                language="en",
                definition="A definition long enough to clear validation.",
                example_sentence="The non_target word appears here.",
            )
            s.add(target_vocab)
            await s.flush()
            r = Review(user_id=user.id, vocab_item_id=target_vocab.id, due_at=now)
            s.add(r)
            await s.commit()
            await s.refresh(r)
            return r.id

    review_id = asyncio.run(setup())

    with (
        _patch("app.api.reviews.celery_app.send_task") as mock_send,
        TestClient(app) as c,
    ):
        resp = c.post(f"/review/{review_id}/rate", data={"quality": 4})

    assert resp.status_code == 200
    mock_send.assert_not_called()


def test_rate_swallows_enqueue_failure_to_keep_response_200(tmp_path: Path) -> None:
    from unittest.mock import patch as _patch

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        now = datetime.now(UTC)
        async with factory() as s:
            for i in range(29):
                v = VocabItem(
                    token=f"sf{i}",
                    language="en",
                    definition=f"long-enough definition for sf{i} validation.",
                    example_sentence=f"The sf{i} word appears here.",
                )
                s.add(v)
                await s.flush()
                s.add(Review(user_id=user.id, vocab_item_id=v.id, last_reviewed_at=now))
            target_vocab = VocabItem(
                token="sf_target",
                language="en",
                definition="A definition long enough to clear validation.",
                example_sentence="The sf_target word appears here.",
            )
            s.add(target_vocab)
            await s.flush()
            r = Review(user_id=user.id, vocab_item_id=target_vocab.id, due_at=now)
            s.add(r)
            await s.commit()
            await s.refresh(r)
            return r.id

    review_id = asyncio.run(setup())

    with (
        _patch(
            "app.api.reviews.celery_app.send_task",
            side_effect=RuntimeError("redis down"),
        ),
        TestClient(app) as c,
    ):
        resp = c.post(f"/review/{review_id}/rate", data={"quality": 4})

    assert resp.status_code == 200
