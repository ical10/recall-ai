from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import get_current_user, get_session
from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem
from app.schemas.pronunciation import PronunciationVerdict


def _make_app(db_path: str) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    from app.api.json.pronunciation import router as pronunciation_router

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

    app.include_router(pronunciation_router, prefix="/api")

    return app, factory


async def _seed(
    factory: async_sessionmaker[AsyncSession],
) -> tuple[User, VocabItem, Review]:
    async with factory() as s:
        u = User(
            email="u@t.com",
            google_id=f"g{uuid4().hex[:8]}",
            name="Test",
            interest_tags=["food"],
        )
        s.add(u)
        v = VocabItem(
            token="hello",
            language="en",
            definition="a greeting",
            example_sentence="Say hello.",
        )
        s.add(v)
        await s.flush()
        r = Review(user_id=u.id, vocab_item_id=v.id)
        s.add(r)
        await s.commit()
        await s.refresh(r)
        return u, v, r


_passed = PronunciationVerdict(
    said_target=True, heard="hello", confidence=0.95, feedback="Great job!"
)


def test_pronunciation_returns_verdict(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user, _, review = asyncio.run(_seed(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with (
        patch(
            "app.api.json.pronunciation.evaluate_pronunciation",
            return_value=_passed,
        ),
        patch("app.api.json.pronunciation.get_settings") as mock_settings,
    ):
        mock_settings.return_value.stt_provider = "gemini"
        with TestClient(app) as c:
            resp = c.post(
                f"/api/review/pronunciation?vocab_item_id={review.vocab_item_id}",
                files={"audio": ("test.webm", b"fake", "audio/webm")},
            )
    assert resp.status_code == 200
    data = resp.json()
    assert data["said_target"] is True
    assert data["heard"] == "hello"


def test_pronunciation_rejects_unsupported_mime(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user, v, _ = asyncio.run(_seed(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with patch("app.api.json.pronunciation.get_settings") as mock_settings:
        mock_settings.return_value.stt_provider = "gemini"
        with TestClient(app) as c:
            resp = c.post(
                f"/api/review/pronunciation?vocab_item_id={v.id}",
                files={"audio": ("test.mp3", b"fake", "audio/mpeg")},
            )
    assert resp.status_code == 400


def test_pronunciation_404_not_owner(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    _, v, _ = asyncio.run(_seed(factory))

    async def _another() -> User:
        async with factory() as s:
            u2 = User(
                email="u2@t.com",
                google_id=f"g{uuid4().hex[:8]}",
                name="Other",
                interest_tags=["food"],
            )
            s.add(u2)
            await s.commit()
            return u2

    app.dependency_overrides[get_current_user] = lambda: asyncio.run(_another())
    with patch("app.api.json.pronunciation.get_settings") as mock_settings:
        mock_settings.return_value.stt_provider = "gemini"
        with TestClient(app) as c:
            resp = c.post(
                f"/api/review/pronunciation?vocab_item_id={v.id}",
                files={"audio": ("test.webm", b"fake", "audio/webm")},
            )
    assert resp.status_code == 404


def test_pronunciation_unset_provider_returns_503(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    user, v, _ = asyncio.run(_seed(factory))
    app.dependency_overrides[get_current_user] = lambda: user
    with patch("app.api.json.pronunciation.get_settings") as mock_settings:
        mock_settings.return_value.stt_provider = ""
        with TestClient(app) as c:
            resp = c.post(
                f"/api/review/pronunciation?vocab_item_id={v.id}",
                files={"audio": ("test.webm", b"fake", "audio/webm")},
            )
    assert resp.status_code == 503


def test_pronunciation_401_unauth(tmp_path: Path) -> None:
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    _, v, _ = asyncio.run(_seed(factory))
    with TestClient(app) as c:
        resp = c.post(
            f"/api/review/pronunciation?vocab_item_id={v.id}",
            files={"audio": ("test.webm", b"fake", "audio/webm")},
        )
    assert resp.status_code == 401
