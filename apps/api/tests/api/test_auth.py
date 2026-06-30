"""Tests for auth routes: login, callback, logout."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import UserDep, get_current_user
from app.core.config import get_settings
from app.core.db import get_session
from app.core.tokens import verify_bearer_token
from app.models import Base
from app.models.review import Review
from app.models.user import User
from app.services.google_identity import GoogleIdentity, InvalidGoogleToken

TEST_SECRET = "test-auth-secret"
TEST_STATE = "known-state"

_ENV = {
    "GOOGLE_CLIENT_ID": "test-cid",
    "GOOGLE_CLIENT_SECRET": "test-cs",
    "GOOGLE_REDIRECT_URI": "http://localhost/cb",
}


def _setup_env() -> None:
    for k, v in _ENV.items():
        os.environ[k] = v
    get_settings.cache_clear()


def _fake_id_token(sub: str, email: str, name: str) -> str:
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256"}).encode()).decode().rstrip("=")
    payload = (
        base64.urlsafe_b64encode(json.dumps({"sub": sub, "email": email, "name": name}).encode())
        .decode()
        .rstrip("=")
    )
    sig = base64.urlsafe_b64encode(b"x").decode().rstrip("=")
    return f"{header}.{payload}.{sig}"


@pytest.fixture(autouse=True)
def _mock_google_verify():  # type: ignore[no-untyped-def]
    """Mock the verification seam for every test: decode the fake id_token's payload.
    The real google-auth signature/JWKS/audience path is covered in test_google_identity.py.
    """

    def _decode(raw, **_kwargs):  # type: ignore[no-untyped-def]
        payload_b64 = raw.split(".")[1]
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        p = json.loads(base64.urlsafe_b64decode(payload_b64))
        return GoogleIdentity(
            sub=p["sub"],
            email=p.get("email", ""),
            name=p.get("name", ""),
            picture=p.get("picture"),
        )

    with patch("app.api.auth.verify_google_id_token", side_effect=_decode):
        yield


def _make_app(
    db_path: str, *, with_401_handler: bool = False
) -> tuple[FastAPI, async_sessionmaker[AsyncSession]]:
    from app.api.auth import router as auth_router

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key=TEST_SECRET, session_cookie="test_session")

    if with_401_handler:
        from fastapi import Request
        from fastapi.responses import RedirectResponse, Response

        @app.exception_handler(401)
        async def unauthenticated_handler(request: Request, _exc: Exception) -> Response:
            return RedirectResponse(url="/login", status_code=302)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    app.include_router(auth_router)
    return app, factory


# ---------------------------------------------------------------------------
# GET /auth/login
# ---------------------------------------------------------------------------


def test_login_redirects_to_google(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        response = c.get("/auth/login", follow_redirects=False)
    assert response.status_code == 307
    location = response.headers["location"]
    assert "accounts.google.com/o/oauth2/v2/auth" in location
    assert "client_id=test-cid" in location


def test_login_sets_state_in_session(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        response = c.get("/auth/login", follow_redirects=False)
    assert response.cookies.get("test_session") is not None


def test_login_errors_when_client_id_empty(tmp_path: Path) -> None:
    os.environ["GOOGLE_CLIENT_ID"] = ""
    get_settings.cache_clear()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        response = c.get("/auth/login")
    assert response.status_code == 500


# ---------------------------------------------------------------------------
# GET /auth/callback
# ---------------------------------------------------------------------------


def test_callback_handles_user_lifecycle(tmp_path: Path) -> None:
    _setup_env()
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    async def seed() -> None:
        async with factory() as s:
            u = User(email="old@b.com", google_id="sub-2", name="Old")
            s.add(u)
            await s.commit()

    asyncio.run(seed())

    with (
        patch("app.api.auth._exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("secrets.token_urlsafe", return_value=TEST_STATE),
        TestClient(app) as c,
    ):
        mock_exchange.return_value = {
            "id_token": _fake_id_token("sub-2", "new@b.com", "New"),
        }
        login_resp = c.get("/auth/login", follow_redirects=False)
        cookies = login_resp.cookies

        c.get(
            f"/auth/callback?code=c&state={TEST_STATE}",
            cookies=cookies,
        )

    async def check() -> User | None:
        async with factory() as s:
            result = await s.execute(select(User).where(User.google_id == "sub-2"))
            return result.scalar_one_or_none()

    user = asyncio.run(check())
    assert user is not None
    assert user.email == "new@b.com"
    assert user.name == "New"


def test_callback_rejects_state_mismatch(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with patch("secrets.token_urlsafe", return_value=TEST_STATE), TestClient(app) as c:
        c.get("/auth/login", follow_redirects=False)
        response = c.get("/auth/callback?code=x&state=wrong")
    assert response.status_code == 400


def test_callback_rejects_missing_state(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        response = c.get("/auth/callback?code=x")
    assert response.status_code == 400


def test_callback_rejects_missing_code(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        response = c.get("/auth/callback?state=any")
    assert response.status_code == 400


def test_callback_rejects_google_denial(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        response = c.get("/auth/callback?error=access_denied")
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# GET /auth/logout
# ---------------------------------------------------------------------------


def test_logout_clears_session_and_redirects(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        response = c.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


# ---------------------------------------------------------------------------
# 401 handler
# ---------------------------------------------------------------------------


def test_401_handler_redirects_full_page(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"), with_401_handler=True)

    def raise_401() -> User:
        from fastapi import HTTPException

        raise HTTPException(status_code=401)

    app.dependency_overrides[get_current_user] = raise_401

    @app.get("/_test_protected")
    async def protected(user: UserDep) -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as c:
        response = c.get("/_test_protected", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/login"


# ---------------------------------------------------------------------------
# callback lifecycle tests
# ---------------------------------------------------------------------------


def test_callback_seeds_starter_vocab_for_new_user(tmp_path: Path) -> None:
    _setup_env()
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    with (
        patch("app.api.auth._exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("secrets.token_urlsafe", return_value=TEST_STATE),
        TestClient(app) as c,
    ):
        mock_exchange.return_value = {
            "id_token": _fake_id_token("sub-new", "new@b.com", "New"),
        }
        login_resp = c.get("/auth/login", follow_redirects=False)
        cookies = login_resp.cookies
        c.get(
            f"/auth/callback?code=c&state={TEST_STATE}",
            cookies=cookies,
        )

    async def check() -> int:
        async with factory() as s:
            u = (
                await s.execute(select(User).where(User.google_id == "sub-new"))
            ).scalar_one_or_none()
            assert u is not None
            result = await s.execute(select(Review).where(Review.user_id == u.id))
            return len(result.all())

    count = asyncio.run(check())
    assert count == 12


def test_callback_does_not_reseed_existing_user_with_reviews(tmp_path: Path) -> None:
    _setup_env()
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    from app.models.vocab_item import VocabItem

    async def insert_existing_user_with_one_review() -> None:
        async with factory() as s:
            user = User(
                email="active@b.com",
                google_id="sub-active",
                name="Active",
                avatar_url=None,
            )
            s.add(user)
            await s.flush()
            vocab = VocabItem(token="solo", language="en", definition="alone")
            s.add(vocab)
            await s.flush()
            s.add(Review(user_id=user.id, vocab_item_id=vocab.id))
            await s.commit()

    asyncio.run(insert_existing_user_with_one_review())

    with (
        patch("app.api.auth._exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("secrets.token_urlsafe", return_value=TEST_STATE),
        TestClient(app) as c,
    ):
        mock_exchange.return_value = {
            "id_token": _fake_id_token("sub-active", "active@b.com", "Active"),
        }
        login_resp = c.get("/auth/login", follow_redirects=False)
        cookies = login_resp.cookies
        c.get(
            f"/auth/callback?code=c&state={TEST_STATE}",
            cookies=cookies,
        )

    async def check() -> int:
        async with factory() as s:
            u = (
                await s.execute(select(User).where(User.google_id == "sub-active"))
            ).scalar_one_or_none()
            assert u is not None
            result = await s.execute(select(Review).where(Review.user_id == u.id))
            return len(result.all())

    count = asyncio.run(check())
    assert count == 1


def test_callback_heals_empty_definitions_on_returning_user_with_reviews(
    tmp_path: Path,
) -> None:
    _setup_env()
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    from app.models.vocab_item import VocabItem
    from app.services.account import STARTER_VOCAB

    async def preseed_user_with_bad_reviews() -> None:
        async with factory() as s:
            user = User(
                email="returning@b.com",
                google_id="sub-returning",
                name="Returning",
            )
            s.add(user)
            await s.flush()
            for entry in STARTER_VOCAB:
                item = VocabItem(token=entry["token"], language=entry["language"], definition="")
                s.add(item)
                await s.flush()
                s.add(Review(user_id=user.id, vocab_item_id=item.id))
            await s.commit()

    asyncio.run(preseed_user_with_bad_reviews())

    with (
        patch("app.api.auth._exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("secrets.token_urlsafe", return_value=TEST_STATE),
        TestClient(app) as c,
    ):
        mock_exchange.return_value = {
            "id_token": _fake_id_token("sub-returning", "returning@b.com", "Returning"),
        }
        login_resp = c.get("/auth/login", follow_redirects=False)
        cookies = login_resp.cookies
        c.get(
            f"/auth/callback?code=c&state={TEST_STATE}",
            cookies=cookies,
        )

    async def empty_def_count() -> int:
        async with factory() as s:
            result = await s.execute(select(VocabItem).where(VocabItem.definition == ""))
            return len(result.all())

    assert asyncio.run(empty_def_count()) == 0


def test_callback_heals_empty_definitions_on_existing_starter_vocab_items(
    tmp_path: Path,
) -> None:
    _setup_env()
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    from app.models.vocab_item import VocabItem
    from app.services.account import STARTER_VOCAB

    async def preseed_empty_vocab_items() -> None:
        async with factory() as s:
            for entry in STARTER_VOCAB:
                s.add(VocabItem(token=entry["token"], language=entry["language"], definition=""))
            await s.commit()

    asyncio.run(preseed_empty_vocab_items())

    with (
        patch("app.api.auth._exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("secrets.token_urlsafe", return_value=TEST_STATE),
        TestClient(app) as c,
    ):
        mock_exchange.return_value = {
            "id_token": _fake_id_token("sub-heal", "heal@b.com", "Heal"),
        }
        login_resp = c.get("/auth/login", follow_redirects=False)
        cookies = login_resp.cookies
        c.get(
            f"/auth/callback?code=c&state={TEST_STATE}",
            cookies=cookies,
        )

    async def empty_def_count() -> int:
        async with factory() as s:
            tokens = [e["token"] for e in STARTER_VOCAB]
            result = await s.execute(
                select(VocabItem).where(
                    VocabItem.token.in_(tokens),
                    VocabItem.language == "en",
                    VocabItem.definition == "",
                )
            )
            return len(result.all())

    assert asyncio.run(empty_def_count()) == 0


def test_callback_backfills_starter_vocab_for_existing_user_with_no_reviews(
    tmp_path: Path,
) -> None:
    _setup_env()
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    async def insert_existing_user() -> None:
        async with factory() as s:
            s.add(
                User(
                    email="old@b.com",
                    google_id="sub-old",
                    name="Old",
                    avatar_url=None,
                )
            )
            await s.commit()

    asyncio.run(insert_existing_user())

    with (
        patch("app.api.auth._exchange_code", new_callable=AsyncMock) as mock_exchange,
        patch("secrets.token_urlsafe", return_value=TEST_STATE),
        TestClient(app) as c,
    ):
        mock_exchange.return_value = {
            "id_token": _fake_id_token("sub-old", "old@b.com", "Old"),
        }
        login_resp = c.get("/auth/login", follow_redirects=False)
        cookies = login_resp.cookies
        c.get(
            f"/auth/callback?code=c&state={TEST_STATE}",
            cookies=cookies,
        )

    async def check() -> int:
        async with factory() as s:
            u = (
                await s.execute(select(User).where(User.google_id == "sub-old"))
            ).scalar_one_or_none()
            assert u is not None
            result = await s.execute(select(Review).where(Review.user_id == u.id))
            return len(result.all())

    count = asyncio.run(check())
    assert count == 12


# ---------------------------------------------------------------------------
# POST /auth/extension
# ---------------------------------------------------------------------------


def test_extension_auth_issues_bearer_and_seeds_new_user(tmp_path: Path) -> None:
    from app.services.account import STARTER_VOCAB

    _setup_env()
    app, factory = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        resp = c.post(
            "/auth/extension",
            json={"id_token": _fake_id_token("sub-ext", "kid@x.com", "Kid")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["email"] == "kid@x.com"

    async def _load() -> tuple[str, int]:
        async with factory() as s:
            user = (await s.execute(select(User).where(User.google_id == "sub-ext"))).scalar_one()
            reviews = (
                (await s.execute(select(Review).where(Review.user_id == user.id))).scalars().all()
            )
            return str(user.id), len(reviews)

    user_id, n_reviews = asyncio.run(_load())
    assert str(verify_bearer_token(data["token"])) == user_id  # bearer maps to the user
    assert n_reviews == len(STARTER_VOCAB)


def test_extension_auth_rejects_invalid_token(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with (
        patch("app.api.auth.verify_google_id_token", side_effect=InvalidGoogleToken("bad")),
        TestClient(app) as c,
    ):
        resp = c.post("/auth/extension", json={"id_token": "x.y.z"})
    assert resp.status_code == 401


def test_extension_auth_existing_user_is_not_duplicated(tmp_path: Path) -> None:
    _setup_env()
    app, factory = _make_app(str(tmp_path / "db.sqlite"))

    async def _seed() -> str:
        async with factory() as s:
            u = User(email="old@x.com", google_id="sub-ext", name="Old")
            s.add(u)
            await s.commit()
            await s.refresh(u)
            return str(u.id)

    existing_id = asyncio.run(_seed())
    with TestClient(app) as c:
        resp = c.post(
            "/auth/extension",
            json={"id_token": _fake_id_token("sub-ext", "new@x.com", "New")},
        )
    assert resp.status_code == 200
    assert str(verify_bearer_token(resp.json()["token"])) == existing_id

    async def _count() -> int:
        async with factory() as s:
            rows = (
                (await s.execute(select(User).where(User.google_id == "sub-ext"))).scalars().all()
            )
            return len(rows)

    assert asyncio.run(_count()) == 1
