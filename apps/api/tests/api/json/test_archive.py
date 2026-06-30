"""Tests for GET /api/archive — paginated user vocab list."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import get_current_user, get_session
from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    from app.api.json.archive import router as json_archive_router

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
    app.include_router(json_archive_router, prefix="/api")

    @app.exception_handler(401)
    async def unauthenticated_handler(request, _exc) -> Response:
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        return Response(status_code=401)

    return app, factory


async def _insert_user(
    factory: async_sessionmaker[AsyncSession],
    email: str = "u@test.com",
) -> User:
    async with factory() as s:
        u = User(email=email, google_id=f"gid-{email}", name="Test", timezone="UTC")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _insert_vocab_with_review(
    factory: async_sessionmaker[AsyncSession],
    user_id: uuid.UUID,
    token: str,
    definition: str = "a word",
) -> None:
    async with factory() as s:
        vi = VocabItem(token=token, language="en", definition=definition)
        s.add(vi)
        await s.flush()
        r = Review(
            user_id=user_id,
            vocab_item_id=vi.id,
            due_at=datetime.now(UTC),
        )
        s.add(r)
        await s.commit()


def test_archive_returns_user_vocab_only(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user_a = asyncio.run(_insert_user(factory))
    user_b = asyncio.run(_insert_user(factory, email="b@test.com"))
    app.dependency_overrides[get_current_user] = lambda: user_a

    async def setup() -> None:
        for token in ["alpha", "beta", "gamma"]:
            await _insert_vocab_with_review(factory, user_a.id, token)
        await _insert_vocab_with_review(factory, user_b.id, "delta")

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/api/archive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3
    assert len(data["items"]) == 3
    tokens = {item["token"] for item in data["items"]}
    assert tokens == {"alpha", "beta", "gamma"}


def test_archive_respects_pagination(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> None:
        for i in range(5):
            await _insert_vocab_with_review(factory, user.id, f"word{i}")

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/api/archive?page=1&page_size=2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total"] == 5
    assert len(data["items"]) == 2


def test_archive_empty_for_user_with_no_reviews(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        resp = c.get("/api/archive")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_archive_unauth_returns_json_401(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    asyncio.run(_insert_user(factory))
    with TestClient(app) as c:
        resp = c.get("/api/archive")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Not authenticated"
