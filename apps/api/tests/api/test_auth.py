"""Tests for auth routes: login, callback, logout, login-page."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from starlette.middleware.sessions import SessionMiddleware

from app.api.deps import UserDep, get_current_user
from app.core.config import get_settings
from app.core.db import get_session
from app.models import Base
from app.models.review import Review
from app.models.user import User

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
            if request.headers.get("hx-request"):
                return Response(status_code=401, headers={"HX-Redirect": "/auth/login-page"})
            return RedirectResponse(url="/auth/login-page", status_code=302)

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
    assert response.status_code == 307
    assert response.headers["location"] == "/"


# ---------------------------------------------------------------------------
# GET /auth/login-page
# ---------------------------------------------------------------------------


def test_login_page_renders(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"))
    with TestClient(app) as c:
        response = c.get("/auth/login-page")
    assert response.status_code == 200
    assert "Sign in with Google" in response.text


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
    assert response.headers["location"] == "/auth/login-page"


def test_401_handler_returns_hx_redirect(tmp_path: Path) -> None:
    _setup_env()
    app, _ = _make_app(str(tmp_path / "db.sqlite"), with_401_handler=True)

    def raise_401() -> User:
        from fastapi import HTTPException

        raise HTTPException(status_code=401)

    app.dependency_overrides[get_current_user] = raise_401

    @app.get("/_test_protected2")
    async def protected2(user: UserDep) -> dict[str, str]:
        return {"ok": "true"}

    with TestClient(app) as c:
        response = c.get(
            "/_test_protected2",
            headers={"HX-Request": "true"},
            follow_redirects=False,
        )

    assert response.status_code == 401
    assert response.headers["hx-redirect"] == "/auth/login-page"


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
    assert count == 4
