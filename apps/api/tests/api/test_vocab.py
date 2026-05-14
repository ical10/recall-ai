"""Tests for Vocab CRUD endpoints and DELETE /reviews/{vocab_id}.

Endpoint contract:
- GET  /vocab                    -> paginated VocabListResponse (JSON)
- POST /vocab                    -> 201 on create, 200 on existing (token, language) pair
- PATCH /vocab/{id}/suspend      -> toggle Review.suspended for caller; 404 when no Review
- DELETE /reviews/{vocab_id}     -> 204, removes only caller's Review; 404 if missing
- DELETE /vocab/{id}             -> must NOT exist (404 or 405)
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    """Create a FastAPI app + session factory backed by a SQLite DB at db_path.

    Schema is created eagerly so helper functions (_insert_user etc.) can be
    called before entering the TestClient context manager.
    """
    from app.api.vocab import router as vocab_router

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
    app.include_router(vocab_router)
    return app, factory


async def _insert_vocab(
    factory: async_sessionmaker[AsyncSession], token: str, language: str = "en"
) -> uuid.UUID:
    async with factory() as s:
        vi = VocabItem(token=token, language=language, definition="")
        s.add(vi)
        await s.commit()
        await s.refresh(vi)
        return vi.id


async def _insert_user(
    factory: async_sessionmaker[AsyncSession], email: str = "user@test.com"
) -> User:
    async with factory() as s:
        u = User(email=email, google_id=f"gid-{email}", name="Test")
        s.add(u)
        await s.commit()
        await s.refresh(u)
        return u


async def _insert_review(
    factory: async_sessionmaker[AsyncSession], user_id: uuid.UUID, vocab_id: uuid.UUID
) -> None:
    async with factory() as s:
        s.add(Review(user_id=user_id, vocab_item_id=vocab_id, due_at=datetime.now(UTC)))
        await s.commit()


async def _count(factory: async_sessionmaker[AsyncSession], model: type) -> int:
    async with factory() as s:
        return int((await s.execute(select(func.count()).select_from(model))).scalar_one())


# ---------------------------------------------------------------------------
# GET /vocab
# ---------------------------------------------------------------------------


def test_get_vocab_requires_authentication(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    async def auth_required() -> User:
        raise HTTPException(status_code=401, detail="Unauthorized")

    app.dependency_overrides[get_current_user] = auth_required
    with TestClient(app) as c:
        resp = c.get("/vocab")
    assert resp.status_code == 401


def test_get_vocab_returns_empty_list(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.get("/vocab")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["page"] == 1
    assert data["page_size"] == 20


def test_get_vocab_paginates_and_returns_correct_total(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        for i in range(25):
            c.post("/vocab", json={"token": f"word{i}", "language": "en"})
        resp = c.get("/vocab?page=2&page_size=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 25
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert len(data["items"]) == 10


# ---------------------------------------------------------------------------
# POST /vocab
# ---------------------------------------------------------------------------


def test_post_vocab_creates_item_and_review_row(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.post("/vocab", json={"token": "ephemeral", "language": "en"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["token"] == "ephemeral"
    assert data["language"] == "en"
    assert data["definition"] == ""
    assert asyncio.run(_count(factory, Review)) == 1


def test_post_vocab_is_idempotent_on_token_language(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    body = {"token": "ubiquitous", "language": "en"}
    with TestClient(app) as c:
        r1 = c.post("/vocab", json=body)
        r2 = c.post("/vocab", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


def test_post_vocab_idempotent_creates_only_one_vocab_item(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    body = {"token": "serendipity", "language": "en"}
    with TestClient(app) as c:
        c.post("/vocab", json=body)
        c.post("/vocab", json=body)
    assert asyncio.run(_count(factory, VocabItem)) == 1


def test_post_vocab_idempotent_creates_only_one_review_for_user(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    body = {"token": "nuance", "language": "en"}
    with TestClient(app) as c:
        c.post("/vocab", json=body)
        c.post("/vocab", json=body)
    assert asyncio.run(_count(factory, Review)) == 1


def test_post_vocab_creates_review_for_existing_vocab_when_user_has_none(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    asyncio.run(_insert_vocab(factory, "preseed"))
    with TestClient(app) as c:
        resp = c.post("/vocab", json={"token": "preseed", "language": "en"})
    assert resp.status_code == 200
    assert asyncio.run(_count(factory, Review)) == 1


def test_post_vocab_rejects_empty_token(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.post("/vocab", json={"token": "", "language": "en"})
    assert resp.status_code == 422


def test_post_vocab_rejects_short_language(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.post("/vocab", json={"token": "word", "language": "x"})
    assert resp.status_code == 422


def test_post_vocab_rejects_oversized_token(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.post("/vocab", json={"token": "x" * 256, "language": "en"})
    assert resp.status_code == 422


def test_post_vocab_rejects_oversized_language(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with TestClient(app) as c:
        resp = c.post("/vocab", json={"token": "ephemeral", "language": "x" * 36})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /vocab/{vocab_id}/suspend
# ---------------------------------------------------------------------------


def test_patch_vocab_suspend_toggles_suspended_flag(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vid = await _insert_vocab(factory, "toggle")
        await _insert_review(factory, user.id, vid)
        return vid

    vid = asyncio.run(setup())
    with TestClient(app) as c:
        r1 = c.patch(f"/vocab/{vid}/suspend")
        assert r1.status_code == 200
        assert r1.json()["suspended"] is True
        r2 = c.patch(f"/vocab/{vid}/suspend")
        assert r2.status_code == 200
        assert r2.json()["suspended"] is False


def test_patch_vocab_suspend_404_when_no_review_for_user(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    vid = asyncio.run(_insert_vocab(factory, "orphan"))
    with TestClient(app) as c:
        resp = c.patch(f"/vocab/{vid}/suspend")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /reviews/{vocab_id}
# ---------------------------------------------------------------------------


def test_delete_review_removes_only_callers_review(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    async def setup() -> tuple[User, User, uuid.UUID]:
        u_a = await _insert_user(factory, "user_a@test.com")
        u_b = await _insert_user(factory, "user_b@test.com")
        vid = await _insert_vocab(factory, "shared")
        await _insert_review(factory, u_a.id, vid)
        await _insert_review(factory, u_b.id, vid)
        return u_a, u_b, vid

    user_a, user_b, vocab_id = asyncio.run(setup())
    app.dependency_overrides[get_current_user] = lambda: user_a

    with TestClient(app) as c:
        resp = c.delete(f"/reviews/{vocab_id}")
    assert resp.status_code == 204

    async def check() -> tuple[int, int, int]:
        async with factory() as s:
            ra = int(
                (
                    await s.execute(
                        select(func.count(Review.id)).where(
                            Review.user_id == user_a.id, Review.vocab_item_id == vocab_id
                        )
                    )
                ).scalar_one()
            )
            rb = int(
                (
                    await s.execute(
                        select(func.count(Review.id)).where(
                            Review.user_id == user_b.id, Review.vocab_item_id == vocab_id
                        )
                    )
                ).scalar_one()
            )
            vi = int(
                (
                    await s.execute(
                        select(func.count(VocabItem.id)).where(VocabItem.id == vocab_id)
                    )
                ).scalar_one()
            )
            return ra, rb, vi

    a_count, b_count, vi_count = asyncio.run(check())
    assert a_count == 0, "caller's Review must be deleted"
    assert b_count == 1, "other user's Review must remain"
    assert vi_count == 1, "Vocab Item must not be deleted"


def test_delete_review_404_when_caller_has_no_review(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    vid = asyncio.run(_insert_vocab(factory, "norev"))
    with TestClient(app) as c:
        resp = c.delete(f"/reviews/{vid}")
    assert resp.status_code == 404


def test_delete_review_does_not_delete_vocab_item(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user = asyncio.run(_insert_user(factory))
    app.dependency_overrides[get_current_user] = lambda: user

    async def setup() -> uuid.UUID:
        vid = await _insert_vocab(factory, "keepme")
        await _insert_review(factory, user.id, vid)
        return vid

    vid = asyncio.run(setup())
    with TestClient(app) as c:
        resp = c.delete(f"/reviews/{vid}")
    assert resp.status_code == 204
    assert asyncio.run(_count(factory, VocabItem)) == 1


def test_no_delete_vocab_endpoint_exposed(tmp_path: Path) -> None:
    """DELETE /vocab/{id} must not exist — see ADR-0008.
    FastAPI returns 404 when no path matches; 405 would require the path to exist
    with only the method unregistered. Either way the endpoint does not exist."""
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        resp = c.delete(f"/vocab/{uuid.uuid4()}")
    assert resp.status_code in (404, 405)
