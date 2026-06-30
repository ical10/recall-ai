from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import get_session
from app.models import Base
from app.models.user import User


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    from app.api.json.me import router as me_router

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
    app.add_middleware(SessionMiddleware, secret_key="test")

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    app.include_router(me_router, prefix="/api")

    return app, factory


async def _insert_user(
    factory: async_sessionmaker[AsyncSession],
    email: str = "u@test.com",
    name: str = "Test User",
    avatar_url: str | None = "https://example.com/avatar.png",
) -> User:
    async with factory() as s:
        u = User(
            email=email,
            google_id=f"gid-{email}",
            name=name,
            avatar_url=avatar_url,
        )
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


def test_me_returns_user_profile(tmp_path: Path) -> None:
    from app.api.json.me import _optional_user

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory, name="Alice", avatar_url="https://img.com/a.jpg"))
    app.dependency_overrides[_optional_user] = lambda: user
    with TestClient(app) as c:
        resp = c.get("/api/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(user.id)
    assert data["email"] == "u@test.com"
    assert data["name"] == "Alice"
    assert data["avatar_url"] == "https://img.com/a.jpg"


def test_me_handles_null_avatar(tmp_path: Path) -> None:
    from app.api.json.me import _optional_user

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory, avatar_url=None))
    app.dependency_overrides[_optional_user] = lambda: user
    with TestClient(app) as c:
        resp = c.get("/api/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["avatar_url"] is None


def test_me_returns_none_when_unauthenticated(tmp_path: Path) -> None:
    from app.api.json.me import _optional_user

    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    asyncio.run(_insert_user(factory))
    app.dependency_overrides[_optional_user] = lambda: None
    with TestClient(app) as c:
        resp = c.get("/api/me")
    assert resp.status_code == 200
    assert resp.json() is None
