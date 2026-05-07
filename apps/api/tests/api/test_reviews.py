import asyncio
import inspect as stdlib_inspect
from collections.abc import AsyncIterator, Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.inspection import inspect


def test_review_has_vocab_item_relationship() -> None:
    from app.models.review import Review

    rel = inspect(Review).relationships.get("vocab_item")
    assert rel is not None, "Review.vocab_item relationship missing"
    assert rel.lazy == "raise", "expected lazy='raise' to surface accidental N+1"


def test_next_due_review_helper_exists() -> None:
    from app.api.reviews import _next_due_review

    sig = stdlib_inspect.signature(_next_due_review)
    params = list(sig.parameters)
    assert params == ["session", "user_id", "now"], (
        f"_next_due_review signature mismatch: got {params}"
    )


def test_next_due_review_returns_due_review(in_memory_session_factory: Any) -> None:
    from datetime import UTC, datetime

    from app.api.reviews import _next_due_review
    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    async def run() -> None:
        factory = in_memory_session_factory

        async with factory() as session:
            user = User(email="test@example.com", google_id="gid-1", name="Test")
            session.add(user)
            await session.flush()

            vocab = VocabItem(
                token="apple",
                language="en",
                definition="a fruit",
            )
            session.add(vocab)
            await session.flush()

            now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
            review = Review(
                user_id=user.id,
                vocab_item_id=vocab.id,
                due_at=datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC),
            )
            session.add(review)
            await session.commit()

        async with factory() as session:
            result = await _next_due_review(session, user.id, now)
            assert result is not None, "_next_due_review returned None for a due review"
            assert result.id == review.id

    asyncio.run(run())


def test_get_review_for_user_scopes_by_owner(in_memory_session_factory: Any) -> None:
    """The helper must return None when the review id belongs to a different user."""
    from app.api.reviews import _get_review_for_user
    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    async def run() -> None:
        async with in_memory_session_factory() as session:
            owner = User(email="owner@test.com", google_id="g-owner", name="Owner")
            other = User(email="other@test.com", google_id="g-other", name="Other")
            session.add_all([owner, other])
            await session.flush()
            vocab = VocabItem(token="x", language="en", definition="d")
            session.add(vocab)
            await session.flush()
            review = Review(user_id=owner.id, vocab_item_id=vocab.id)
            session.add(review)
            await session.commit()

            owner_view = await _get_review_for_user(session, review.id, owner.id)
            other_view = await _get_review_for_user(session, review.id, other.id)
            assert owner_view is not None and owner_view.id == review.id
            assert other_view is None

    asyncio.run(run())


# ---------------------------------------------------------------------------
# Fixtures for GET /review endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def reviews_app(
    in_memory_session_factory: async_sessionmaker[AsyncSession],
) -> Iterator[FastAPI]:
    from sqlalchemy import select

    from app.api.deps import get_current_user
    from app.api.reviews import router as reviews_router
    from app.core.db import get_session
    from app.models.user import User

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with in_memory_session_factory() as session:
            yield session

    async def override_get_current_user() -> User:
        async with in_memory_session_factory() as session:
            result = await session.execute(select(User).where(User.email == "reviewer@test.com"))
            existing = result.scalar_one_or_none()
            if existing is not None:
                return existing
            new_user = User(
                email="reviewer@test.com",
                google_id="gid-rev",
                name="Reviewer",
            )
            session.add(new_user)
            await session.commit()
            result2 = await session.execute(select(User).where(User.email == "reviewer@test.com"))
            return result2.scalar_one()

    app = FastAPI()
    app.include_router(reviews_router)
    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user

    yield app


@pytest.fixture
def reviews_client(reviews_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(reviews_app, raise_server_exceptions=True) as client:
        yield client


# ---------------------------------------------------------------------------
# Test 1: no due reviews → done partial
# ---------------------------------------------------------------------------


def test_get_review_renders_done_when_no_due_reviews(
    reviews_client: TestClient,
    in_memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.models.user import User

    async def seed() -> None:
        from sqlalchemy import select

        async with in_memory_session_factory() as session:
            result = await session.execute(select(User).where(User.email == "reviewer@test.com"))
            if result.scalar_one_or_none() is None:
                session.add(User(email="reviewer@test.com", google_id="gid-rev", name="Reviewer"))
                await session.commit()

    asyncio.run(seed())

    resp = reviews_client.get("/review")
    assert resp.status_code == 200
    assert "All caught up" in resp.text


# ---------------------------------------------------------------------------
# Test 2: oldest due card is shown first
# ---------------------------------------------------------------------------


def test_get_review_returns_oldest_due_card_for_user(
    reviews_client: TestClient,
    in_memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime

    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    async def seed() -> None:
        from sqlalchemy import select

        async with in_memory_session_factory() as session:
            result = await session.execute(select(User).where(User.email == "reviewer@test.com"))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(email="reviewer@test.com", google_id="gid-rev", name="Reviewer")
                session.add(user)
                await session.flush()

            vocab_older = VocabItem(token="older-word", language="en", definition="older def")
            vocab_newer = VocabItem(token="newer-word", language="en", definition="newer def")
            session.add(vocab_older)
            session.add(vocab_newer)
            await session.flush()

            session.add(
                Review(
                    user_id=user.id,
                    vocab_item_id=vocab_older.id,
                    due_at=datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC),
                )
            )
            session.add(
                Review(
                    user_id=user.id,
                    vocab_item_id=vocab_newer.id,
                    due_at=datetime(2026, 1, 1, 11, 0, 0, tzinfo=UTC),
                )
            )
            await session.commit()

    asyncio.run(seed())

    resp = reviews_client.get("/review")
    assert resp.status_code == 200
    assert "older-word" in resp.text
    assert "newer-word" not in resp.text


# ---------------------------------------------------------------------------
# Test 3: suspended reviews are excluded
# ---------------------------------------------------------------------------


def test_get_review_excludes_suspended_reviews(
    reviews_client: TestClient,
    in_memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime

    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    async def seed() -> None:
        from sqlalchemy import select

        async with in_memory_session_factory() as session:
            result = await session.execute(select(User).where(User.email == "reviewer@test.com"))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(email="reviewer@test.com", google_id="gid-rev", name="Reviewer")
                session.add(user)
                await session.flush()

            vocab = VocabItem(token="suspended-word", language="en", definition="def")
            session.add(vocab)
            await session.flush()

            session.add(
                Review(
                    user_id=user.id,
                    vocab_item_id=vocab.id,
                    due_at=datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC),
                    suspended=True,
                )
            )
            await session.commit()

    asyncio.run(seed())

    resp = reviews_client.get("/review")
    assert resp.status_code == 200
    assert "All caught up" in resp.text
    assert "suspended-word" not in resp.text


# ---------------------------------------------------------------------------
# Test 4: reviews belonging to a different user are not shown
# ---------------------------------------------------------------------------


def test_get_review_excludes_other_users_reviews(
    reviews_client: TestClient,
    in_memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from datetime import UTC, datetime

    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    async def seed() -> None:
        async with in_memory_session_factory() as session:
            other_user = User(email="other@test.com", google_id="gid-other", name="Other")
            session.add(other_user)
            await session.flush()

            vocab = VocabItem(token="other-word", language="en", definition="def")
            session.add(vocab)
            await session.flush()

            session.add(
                Review(
                    user_id=other_user.id,
                    vocab_item_id=vocab.id,
                    due_at=datetime(2026, 1, 1, 9, 0, 0, tzinfo=UTC),
                )
            )
            await session.commit()

    asyncio.run(seed())

    resp = reviews_client.get("/review")
    assert resp.status_code == 200
    assert "All caught up" in resp.text
    assert "other-word" not in resp.text


# ---------------------------------------------------------------------------
# Tests for GET /review/{id}/reveal
# ---------------------------------------------------------------------------


def test_reveal_returns_partial_with_definition(
    reviews_client: TestClient,
    in_memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    review_id: Any = None

    async def seed() -> None:
        nonlocal review_id
        from sqlalchemy import select

        async with in_memory_session_factory() as session:
            result = await session.execute(select(User).where(User.email == "reviewer@test.com"))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(email="reviewer@test.com", google_id="gid-rev", name="Reviewer")
                session.add(user)
                await session.flush()

            vocab = VocabItem(
                token="banana",
                language="en",
                definition="a yellow fruit",
                example_sentence="I eat a banana every morning.",
            )
            session.add(vocab)
            await session.flush()

            review = Review(user_id=user.id, vocab_item_id=vocab.id)
            session.add(review)
            await session.commit()
            review_id = review.id

    asyncio.run(seed())

    resp = reviews_client.get(f"/review/{review_id}/reveal")
    assert resp.status_code == 200
    assert "a yellow fruit" in resp.text
    assert "Again" in resp.text
    assert "Hard" in resp.text
    assert "Good" in resp.text
    assert "Easy" in resp.text
    assert "Reveal definition" not in resp.text


def test_reveal_404_when_not_owner(
    reviews_client: TestClient,
    in_memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    review_id: Any = None

    async def seed() -> None:
        nonlocal review_id
        async with in_memory_session_factory() as session:
            other_user = User(email="other2@test.com", google_id="gid-other2", name="Other2")
            session.add(other_user)
            await session.flush()

            vocab = VocabItem(token="cherry", language="en", definition="a red fruit")
            session.add(vocab)
            await session.flush()

            review = Review(user_id=other_user.id, vocab_item_id=vocab.id)
            session.add(review)
            await session.commit()
            review_id = review.id

    asyncio.run(seed())

    resp = reviews_client.get(f"/review/{review_id}/reveal")
    assert resp.status_code == 404


def test_reveal_404_when_not_found(
    reviews_client: TestClient,
) -> None:
    import uuid

    random_id = uuid.uuid4()
    resp = reviews_client.get(f"/review/{random_id}/reveal")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 5: null due_at is treated as immediately due
# ---------------------------------------------------------------------------


def test_get_review_treats_null_due_at_as_due(
    reviews_client: TestClient,
    in_memory_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    from app.models.review import Review
    from app.models.user import User
    from app.models.vocab_item import VocabItem

    async def seed() -> None:
        from sqlalchemy import select

        async with in_memory_session_factory() as session:
            result = await session.execute(select(User).where(User.email == "reviewer@test.com"))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(email="reviewer@test.com", google_id="gid-rev", name="Reviewer")
                session.add(user)
                await session.flush()

            vocab = VocabItem(token="null-due-word", language="en", definition="def")
            session.add(vocab)
            await session.flush()

            session.add(
                Review(
                    user_id=user.id,
                    vocab_item_id=vocab.id,
                    due_at=None,
                )
            )
            await session.commit()

    asyncio.run(seed())

    resp = reviews_client.get("/review")
    assert resp.status_code == 200
    assert "null-due-word" in resp.text
