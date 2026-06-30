"""Tests for the current-user resolution seam (bearer + session adapters)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import OptionalUserDep, UserDep, get_session
from app.core.tokens import sign_bearer_token
from app.models import Base
from app.models.user import User


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-session")

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    @app.get("/protected")
    async def protected(user: UserDep) -> dict[str, str]:
        return {"id": str(user.id)}

    @app.get("/optional")
    async def optional(user: OptionalUserDep) -> dict[str, str | None]:
        return {"id": str(user.id) if user is not None else None}

    return app, factory


async def _insert_user(factory: async_sessionmaker[AsyncSession]) -> User:
    async with factory() as s:
        u = User(email="u@test.com", google_id="gid-u", name="U")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


def test_valid_bearer_resolves_user(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    token = sign_bearer_token(user.id)
    with TestClient(app) as c:
        resp = c.get("/protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["id"] == str(user.id)


def test_invalid_bearer_is_unauthorized(tmp_path: Path) -> None:
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        resp = c.get("/protected", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


def test_no_credentials_is_unauthorized(tmp_path: Path) -> None:
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        resp = c.get("/protected")
    assert resp.status_code == 401


def test_optional_user_is_none_without_credentials(tmp_path: Path) -> None:
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        resp = c.get("/optional")
    assert resp.status_code == 200
    assert resp.json()["id"] is None


def test_optional_user_resolves_from_bearer(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    token = sign_bearer_token(user.id)
    with TestClient(app) as c:
        resp = c.get("/optional", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["id"] == str(user.id)
