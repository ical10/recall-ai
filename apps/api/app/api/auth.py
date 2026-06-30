from __future__ import annotations

import asyncio
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.core.tokens import sign_bearer_token
from app.schemas.auth import ExtensionAuthIn, ExtensionAuthOut
from app.schemas.me import MeResponse
from app.services.account import provision_user
from app.services.google_identity import InvalidGoogleToken, verify_google_id_token

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _google_consent_url(state: str) -> str:
    settings = get_settings()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def _exchange_code(code: str) -> dict[str, object]:
    settings = get_settings()
    resp = await httpx.AsyncClient().post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret.get_secret_value(),
            "redirect_uri": settings.google_redirect_uri,
            "grant_type": "authorization_code",
        },
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="token exchange failed")
    data: dict[str, object] = resp.json()
    return data


@router.get("/auth/login")
async def login(request: Request) -> RedirectResponse:
    settings = get_settings()
    if not settings.google_client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")
    state = secrets.token_urlsafe(32)
    request.session["oauth_state"] = state
    return RedirectResponse(url=_google_consent_url(state), status_code=307)


@router.get("/auth/callback")
async def callback(
    request: Request,
    session: SessionDep,
    error: str | None = None,
    code: str | None = None,
    state: str | None = None,
) -> RedirectResponse:
    if error:
        raise HTTPException(status_code=400, detail=f"google denied: {error}")

    stored_state = request.session.pop("oauth_state", None)
    if not state or state != stored_state:
        raise HTTPException(status_code=400, detail="state mismatch")

    if not code:
        raise HTTPException(status_code=400, detail="missing authorization code")

    token_data = await _exchange_code(code)
    id_token_raw = token_data.get("id_token")
    if not id_token_raw or not isinstance(id_token_raw, str):
        raise HTTPException(status_code=400, detail="no id_token in response")

    try:
        identity = await asyncio.to_thread(verify_google_id_token, id_token_raw)
    except InvalidGoogleToken as exc:
        raise HTTPException(status_code=400, detail="invalid id_token") from exc

    user = await provision_user(session, identity)
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard", status_code=307)


@router.post("/auth/extension", response_model=ExtensionAuthOut)
async def auth_extension(session: SessionDep, body: ExtensionAuthIn) -> ExtensionAuthOut:
    """Extension login: verify the Google id_token (JWKS signature + web-or-extension
    audience), provision the user, and mint a stateless 30-day bearer the extension
    stores and sends as `Authorization: Bearer`. No session cookie — the bearer is the
    credential. Returns 401 on any verification failure.
    """
    try:
        identity = await asyncio.to_thread(verify_google_id_token, body.id_token)
    except InvalidGoogleToken as exc:
        raise HTTPException(status_code=401, detail="invalid id_token") from exc

    user = await provision_user(session, identity)
    return ExtensionAuthOut(
        token=sign_bearer_token(user.id),
        user=MeResponse.model_validate(user),
    )


@router.get("/auth/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)
