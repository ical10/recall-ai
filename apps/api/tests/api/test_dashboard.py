from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import (
    DEV_USER_EMAIL,
    DEV_USER_GOOGLE_ID,
    DEV_USER_NAME,
    get_current_user,
)
from app.core.db import get_session
from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


@dataclass
class DashboardFixture:
    app: FastAPI
    client: TestClient
    factory: async_sessionmaker[AsyncSession]


@pytest.fixture
def dashboard_app(tmp_path: Path) -> Iterator[DashboardFixture]:
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        await engine.dispose()

    from app.api.dashboard import router

    app = FastAPI(lifespan=lifespan)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.include_router(router)

    with TestClient(app, follow_redirects=False) as client:
        yield DashboardFixture(app=app, client=client, factory=factory)


@pytest.fixture
def dashboard_client(dashboard_app: DashboardFixture) -> TestClient:
    return dashboard_app.client


# ---------------------------------------------------------------------------
# Seeding helpers
# ---------------------------------------------------------------------------


def _make_user(email: str | None = None, google_id: str | None = None) -> User:
    uid = str(uuid.uuid4())
    return User(
        id=uuid.uuid4(),
        email=email or f"u{uid}@test.com",
        google_id=google_id or uid,
        name="Test",
    )


def _make_vocab(token: str, definition: str = "a word") -> VocabItem:
    return VocabItem(id=uuid.uuid4(), token=token, language="en", definition=definition)


async def _seed(
    factory: async_sessionmaker[AsyncSession],
    users: list[User],
    vocabs: list[VocabItem],
    reviews: list[Review],
) -> None:
    """Seed users + vocabs + reviews.

    Users and vocabs are flushed first so their PKs are assigned before
    reviews reference them.  Reviews must be constructed *before* calling
    this helper with already-assigned user.id / vocab_item_id values, OR
    users/vocabs must have explicit UUIDs set at construction time.
    """
    async with factory() as session:
        session.add_all(users)
        session.add_all(vocabs)
        await session.flush()
        session.add_all(reviews)
        await session.commit()


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------


def test_index_redirects_to_dashboard(dashboard_client: TestClient) -> None:
    response = dashboard_client.get("/")
    assert response.status_code == 307
    assert response.headers["location"] == "/dashboard"


def test_dashboard_returns_200(dashboard_client: TestClient) -> None:
    response = dashboard_client.get("/dashboard")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]


def test_dashboard_contains_stats_headings(dashboard_client: TestClient) -> None:
    response = dashboard_client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    assert "Due today" in body
    assert "Total reviews" in body
    assert "Streak" in body


# ---------------------------------------------------------------------------
# New tests
# ---------------------------------------------------------------------------


def test_dashboard_handles_user_with_no_reviews(dashboard_client: TestClient) -> None:
    """Fresh user (no reviews) → 200, 'No reviews yet' copy, at least one >0< stat."""
    response = dashboard_client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    assert "No reviews yet" in body
    assert ">0<" in body


def test_dashboard_renders_due_today_count(dashboard_app: DashboardFixture) -> None:
    """2 due reviews + 1 due tomorrow → 'Due today' card shows exactly 2."""
    now = datetime.now(UTC)
    end_of_today = datetime.combine(now.date(), datetime.max.time(), tzinfo=UTC)

    dev_user = _make_user(email=DEV_USER_EMAIL, google_id=DEV_USER_GOOGLE_ID)
    dev_user.name = DEV_USER_NAME
    vocab_a = _make_vocab("alpha")
    vocab_b = _make_vocab("bravo")
    vocab_c = _make_vocab("charlie")

    asyncio.run(
        _seed(
            dashboard_app.factory,
            users=[dev_user],
            vocabs=[vocab_a, vocab_b, vocab_c],
            reviews=[
                Review(
                    user_id=dev_user.id,
                    vocab_item_id=vocab_a.id,
                    due_at=now - timedelta(hours=2),
                    suspended=False,
                ),
                Review(
                    user_id=dev_user.id,
                    vocab_item_id=vocab_b.id,
                    due_at=end_of_today - timedelta(minutes=1),
                    suspended=False,
                ),
                Review(
                    user_id=dev_user.id,
                    vocab_item_id=vocab_c.id,
                    due_at=now + timedelta(days=1),
                    suspended=False,
                ),
            ],
        )
    )

    response = dashboard_app.client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    assert "Due today" in body
    assert ">2<" in body


def test_dashboard_isolated_per_user(dashboard_app: DashboardFixture) -> None:
    """User B sees only their own 1 due review, not user A's 5."""
    now = datetime.now(UTC)

    user_a = _make_user(email="a@test.com", google_id="ga")
    user_b = _make_user(email="b@test.com", google_id="gb")

    vocabs_a = [_make_vocab(f"word_a{i}") for i in range(5)]
    vocab_b0 = _make_vocab("word_b0")

    reviews_a = [
        Review(
            user_id=user_a.id,
            vocab_item_id=v.id,
            due_at=now - timedelta(hours=i + 1),
            suspended=False,
        )
        for i, v in enumerate(vocabs_a)
    ]
    review_b = Review(
        user_id=user_b.id,
        vocab_item_id=vocab_b0.id,
        due_at=now - timedelta(hours=1),
        suspended=False,
    )

    asyncio.run(
        _seed(
            dashboard_app.factory,
            users=[user_a, user_b],
            vocabs=vocabs_a + [vocab_b0],
            reviews=reviews_a + [review_b],
        )
    )

    async def _return_user_b() -> User:
        return user_b

    dashboard_app.app.dependency_overrides[get_current_user] = _return_user_b

    try:
        response = dashboard_app.client.get("/dashboard")
    finally:
        del dashboard_app.app.dependency_overrides[get_current_user]

    assert response.status_code == 200
    body = response.text
    assert ">1<" in body
    assert ">5<" not in body


def test_dashboard_renders_recent_tokens_in_descending_order(
    dashboard_app: DashboardFixture,
) -> None:
    """Three reviewed vocabs appear newest-first: charlie > bravo > alpha."""
    base_time = datetime(2026, 5, 7, 10, 0, 0, tzinfo=UTC)

    dev_user = _make_user(email=DEV_USER_EMAIL, google_id=DEV_USER_GOOGLE_ID)
    dev_user.name = DEV_USER_NAME
    vocab_alpha = _make_vocab("alpha")
    vocab_bravo = _make_vocab("bravo")
    vocab_charlie = _make_vocab("charlie")

    asyncio.run(
        _seed(
            dashboard_app.factory,
            users=[dev_user],
            vocabs=[vocab_alpha, vocab_bravo, vocab_charlie],
            reviews=[
                Review(
                    user_id=dev_user.id,
                    vocab_item_id=vocab_alpha.id,
                    last_reviewed_at=base_time,
                ),
                Review(
                    user_id=dev_user.id,
                    vocab_item_id=vocab_bravo.id,
                    last_reviewed_at=base_time + timedelta(hours=1),
                ),
                Review(
                    user_id=dev_user.id,
                    vocab_item_id=vocab_charlie.id,
                    last_reviewed_at=base_time + timedelta(hours=2),
                ),
            ],
        )
    )

    response = dashboard_app.client.get("/dashboard")
    assert response.status_code == 200
    body = response.text
    assert "alpha" in body
    assert "bravo" in body
    assert "charlie" in body
    assert body.index("charlie") < body.index("bravo") < body.index("alpha")
