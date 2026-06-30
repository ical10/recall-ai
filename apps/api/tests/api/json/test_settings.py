"""Tests for GET /api/settings and PUT /api/settings/interests — JSON API."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import get_current_user, get_session
from app.models import Base
from app.models.user import User


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    from app.api.json.settings import router as json_settings_router

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
    app.include_router(json_settings_router, prefix="/api")

    @app.exception_handler(401)
    async def unauthenticated_handler(request, _exc) -> Response:
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        return Response(status_code=401)

    return app, factory


async def _insert_user(
    factory: async_sessionmaker[AsyncSession],
    email: str = "u@test.com",
    interest_tags: tuple[str, ...] = (),
) -> User:
    async with factory() as s:
        u = User(
            email=email,
            google_id=f"gid-{email}",
            name="Test",
            timezone="UTC",
            interest_tags=list(interest_tags),
        )
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


def test_get_settings_returns_tags(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory, interest_tags=("food", "sports")))
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.get("/api/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "interest_tags" in data
    assert "food" in data["interest_tags"]
    assert "sports" in data["interest_tags"]
    assert "all_tags" in data
    assert "food" in data["all_tags"]


def test_get_settings_unauth_returns_json_401(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    asyncio.run(_insert_user(factory))
    with TestClient(app) as c:
        resp = c.get("/api/settings")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"


def test_put_interests_updates_and_returns_settings(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.put(
            "/api/settings/interests",
            json={"tags": ["animals", "colors"]},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["interest_tags"]) == {"animals", "colors"}


def test_put_interests_rejects_invalid_tags(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.put(
            "/api/settings/interests",
            json={"tags": ["invalid_tag_xyz"]},
        )
    assert resp.status_code == 422
