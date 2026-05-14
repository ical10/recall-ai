"""Tests for dashboard routes: GET / redirect and GET /dashboard rendering."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
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
    from app.api.dashboard import router as dashboard_router

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

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.include_router(dashboard_router)
    return app, factory


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
) -> uuid.UUID:
    async with factory() as s:
        vi = VocabItem(token=token, language="en", definition=definition)
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
    last_reviewed_at: datetime | None = None,
    interval_days: int = 1,
    suspended: bool = False,
) -> None:
    async with factory() as s:
        s.add(
            Review(
                user_id=user_id,
                vocab_item_id=vocab_id,
                due_at=due_at,
                last_reviewed_at=last_reviewed_at,
                interval_days=interval_days,
                suspended=suspended,
            )
        )
        await s.commit()


def test_index_redirects_to_dashboard(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app, follow_redirects=False) as c:
        resp = c.get("/")
    assert resp.status_code == 307
    assert resp.headers["location"] == "/dashboard"


def test_dashboard_returns_200(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.get("/dashboard")
    assert resp.status_code == 200


def test_dashboard_renders_due_today_count(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> None:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        future = datetime(2099, 1, 1, tzinfo=UTC)
        vid1 = await _insert_vocab(factory, "due1")
        vid2 = await _insert_vocab(factory, "due2")
        vid3 = await _insert_vocab(factory, "notyet")
        await _insert_review(factory, user.id, vid1, due_at=past)
        await _insert_review(factory, user.id, vid2, due_at=past)
        await _insert_review(factory, user.id, vid3, due_at=future)

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/dashboard")
    assert resp.status_code == 200
    assert "Due today" in resp.text
    assert ">2<" in resp.text


def test_dashboard_isolated_per_user(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user_a = asyncio.run(_insert_user(factory, "a@test.com"))
    user_b = asyncio.run(_insert_user(factory, "b@test.com"))

    async def setup() -> None:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        for i in range(5):
            vid = await _insert_vocab(factory, f"a_word{i}")
            await _insert_review(factory, user_a.id, vid, due_at=past)
        vid_b = await _insert_vocab(factory, "b_word")
        await _insert_review(factory, user_b.id, vid_b, due_at=past)

    asyncio.run(setup())
    app.dependency_overrides[get_current_user] = lambda: user_b
    with TestClient(app) as c:
        resp = c.get("/dashboard")
    assert resp.status_code == 200
    assert ">1<" in resp.text


def test_dashboard_renders_recent_tokens_in_descending_order(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    base = datetime(2026, 5, 10, 12, 0, tzinfo=UTC)

    async def setup() -> None:
        for i, tok in enumerate(["alpha", "beta", "gamma"]):
            vid = await _insert_vocab(factory, tok)
            await _insert_review(factory, user.id, vid, last_reviewed_at=base + timedelta(hours=i))

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/dashboard")
    assert resp.status_code == 200
    text = resp.text
    gamma_pos = text.index("gamma")
    beta_pos = text.index("beta")
    alpha_pos = text.index("alpha")
    assert gamma_pos < beta_pos < alpha_pos


def test_dashboard_handles_user_with_no_reviews(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.get("/dashboard")
    assert resp.status_code == 200
    assert "0" in resp.text
    assert "No reviews yet" in resp.text
