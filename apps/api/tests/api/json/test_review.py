"""Tests for GET /api/review/batch and POST /api/review/ratings — JSON API."""

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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import get_current_user, get_session
from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    from app.api.json.review import router as json_review_router

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

    app.include_router(json_review_router, prefix="/api")

    @app.exception_handler(401)
    async def unauthenticated_handler(request, _exc) -> Response:
        if request.url.path.startswith("/api"):
            return JSONResponse({"detail": "Not authenticated"}, status_code=401)
        return Response(status_code=401)

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
    suspended: bool = False,
) -> uuid.UUID:
    async with factory() as s:
        r = Review(
            user_id=user_id,
            vocab_item_id=vocab_id,
            due_at=due_at,
            suspended=suspended,
        )
        s.add(r)
        await s.commit()
        await s.refresh(r)
        return r.id


# --- GET /api/review/batch ---


def test_review_batch_returns_daily_batch_shape(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> None:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        vid = await _insert_vocab(factory, "hello")
        await _insert_review(factory, user.id, vid, due_at=past)

    asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.get("/api/review/batch")
    assert resp.status_code == 200
    data = resp.json()
    assert "cards" in data
    assert len(data["cards"]) == 1
    card = data["cards"][0]
    assert card["token"] == "hello"
    assert card["ease_factor"] == 2.5
    assert card["review_id"]
    assert card["vocab_item_id"]


def test_review_batch_unauth_returns_json_401(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    asyncio.run(_insert_user(factory))
    with TestClient(app) as c:
        resp = c.get("/api/review/batch")
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"] == "Not authenticated"


def test_review_batch_empty_for_no_due_cards(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.get("/api/review/batch")
    assert resp.status_code == 200
    data = resp.json()
    assert data["cards"] == []


# --- POST /api/review/ratings ---


def test_post_ratings_updates_review_and_returns_sync_result(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        vid = await _insert_vocab(factory, "testword")
        rid = await _insert_review(factory, user.id, vid, due_at=past)
        return rid

    review_id = asyncio.run(setup())

    rating_id = str(uuid.uuid4())
    payload = {
        "ratings": [
            {
                "rating_id": rating_id,
                "card_id": str(review_id),
                "grade": 4,
                "rated_at": datetime.now(UTC).isoformat(),
            }
        ]
    }
    with TestClient(app) as c:
        resp = c.post("/api/review/ratings", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["applied"] == 1
    assert data["skipped"] == 0

    async def check() -> int:
        async with factory() as s:
            r = (await s.execute(select(Review).where(Review.id == review_id))).scalar_one()
            return r.repetitions

    assert asyncio.run(check()) == 1


def test_post_ratings_idempotent_on_same_rating_id(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        past = datetime(2020, 1, 1, tzinfo=UTC)
        vid = await _insert_vocab(factory, "testword")
        rid = await _insert_review(factory, user.id, vid, due_at=past)
        return rid

    review_id = asyncio.run(setup())

    rating_id = str(uuid.uuid4())
    payload = {
        "ratings": [
            {
                "rating_id": rating_id,
                "card_id": str(review_id),
                "grade": 4,
                "rated_at": datetime.now(UTC).isoformat(),
            }
        ]
    }
    with TestClient(app) as c:
        c.post("/api/review/ratings", json=payload)
        resp2 = c.post("/api/review/ratings", json=payload)

    assert resp2.status_code == 200
    data = resp2.json()
    assert data["applied"] == 0
    assert data["skipped"] == 1


def test_post_ratings_unauth_returns_json_401(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    asyncio.run(_insert_user(factory))
    with TestClient(app) as c:
        resp = c.post("/api/review/ratings", json={"ratings": []})
    assert resp.status_code == 401
    data = resp.json()
    assert data["detail"] == "Not authenticated"
