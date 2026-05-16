"""Tests for the /settings interest-tags route."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models import Base
from app.models.user import User


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    from app.api.settings import router as settings_router

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
    app.include_router(settings_router)
    return app, factory


async def _insert_user(
    factory: async_sessionmaker[AsyncSession],
    *,
    interest_tags: list[str] | None = None,
) -> User:
    async with factory() as s:
        u = User(
            id=uuid.uuid4(),
            email="settings@test.com",
            google_id="gid-settings",
            name="Settings User",
        )
        if interest_tags is not None:
            u.interest_tags = interest_tags
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


def test_get_settings_renders_page_with_current_tags_checked(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory, interest_tags=["animals", "sports"]))
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.get("/settings")

    assert resp.status_code == 200
    # Both currently-selected tags should appear as checked
    assert 'value="animals"' in resp.text
    assert 'value="sports"' in resp.text
    assert "checked" in resp.text


def test_post_settings_persists_valid_tags(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory, interest_tags=["animals"]))
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.post("/settings/interests", data={"tags": ["animals", "food"]})

    assert resp.status_code == 200

    async def fetch() -> User:
        async with factory() as s:
            return (await s.execute(select(User).where(User.id == user.id))).scalar_one()

    fresh = asyncio.run(fetch())
    assert sorted(fresh.interest_tags) == ["animals", "food"]


def test_post_settings_rejects_unknown_tag_with_422(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory, interest_tags=["animals"]))
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.post("/settings/interests", data={"tags": ["animals", "cryptocurrency"]})

    assert resp.status_code == 422

    async def fetch() -> User:
        async with factory() as s:
            return (await s.execute(select(User).where(User.id == user.id))).scalar_one()

    fresh = asyncio.run(fetch())
    # Unchanged on rejection
    assert fresh.interest_tags == ["animals"]


def test_post_milestones_seen_updates_user_and_redirects(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))

    async def bump() -> None:
        async with factory() as s:
            from sqlalchemy import update as _update

            await s.execute(
                _update(User).where(User.id == user.id).values(last_personalized_milestone=60)
            )
            await s.commit()

    asyncio.run(bump())

    async def fresh_user() -> User:
        async with factory() as s:
            return (await s.execute(select(User).where(User.id == user.id))).scalar_one()

    user = asyncio.run(fresh_user())
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.post("/milestones/seen", follow_redirects=False)

    assert resp.status_code == 200
    assert resp.headers.get("hx-redirect") == "/review"

    after = asyncio.run(fresh_user())
    assert after.last_milestone_seen == 60
