from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep, templates
from app.core.config import get_settings
from app.models.review import Review
from app.models.user import User
from app.models.vocab_item import VocabItem

router = APIRouter()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

STARTER_VOCAB = [
    {"token": "friend", "language": "en", "definition": "a person you like and play with"},
    {"token": "hungry", "language": "en", "definition": "wanting to eat food"},
    {"token": "happy", "language": "en", "definition": "feeling good and smiling"},
    {"token": "morning", "language": "en", "definition": "the early part of the day"},
    {"token": "family", "language": "en", "definition": "parents, brothers and sisters"},
    {"token": "school", "language": "en", "definition": "a place where children learn"},
    {"token": "play", "language": "en", "definition": "to have fun with toys or games"},
    {"token": "animal", "language": "en", "definition": "a living creature like a dog or cat"},
    {"token": "rain", "language": "en", "definition": "water that falls from clouds"},
    {"token": "color", "language": "en", "definition": "red, blue, green and other shades"},
    {"token": "night", "language": "en", "definition": "the dark time between sunset and sunrise"},
    {"token": "story", "language": "en", "definition": "a tale that you read or tell"},
]


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
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return f"{GOOGLE_AUTH_URL}?{query}"


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


async def _heal_starter_vocab_definitions(session: AsyncSession) -> int:
    healed = 0
    for entry in STARTER_VOCAB:
        canonical = entry.get("definition", "")
        if not canonical:
            continue
        item = (
            await session.execute(
                select(VocabItem).where(
                    VocabItem.token == entry["token"],
                    VocabItem.language == entry["language"],
                )
            )
        ).scalar_one_or_none()
        if item is not None and not item.definition:
            item.definition = canonical
            healed += 1
    if healed:
        await session.commit()
    return healed


async def _seed_starter_vocab(session: AsyncSession, user: User) -> int:
    created = 0
    now = datetime.now(UTC)
    for entry in STARTER_VOCAB:
        token = entry["token"]
        language = entry["language"]
        canonical_definition = entry.get("definition", "")
        existing = (
            await session.execute(
                select(VocabItem).where(VocabItem.token == token, VocabItem.language == language)
            )
        ).scalar_one_or_none()
        if existing is not None:
            item = existing
            if not item.definition and canonical_definition:
                item.definition = canonical_definition
        else:
            item = VocabItem(token=token, language=language, definition=canonical_definition)
            session.add(item)
            await session.flush()
        review = (
            await session.execute(
                select(Review).where(Review.user_id == user.id, Review.vocab_item_id == item.id)
            )
        ).scalar_one_or_none()
        if review is None:
            session.add(Review(user_id=user.id, vocab_item_id=item.id, due_at=now))
            created += 1
    await session.commit()
    return created


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
    id_token = token_data.get("id_token")
    if not id_token or not isinstance(id_token, str):
        raise HTTPException(status_code=400, detail="no id_token in response")

    payload_b64 = id_token.split(".")[1]
    payload_b64 += "=" * (4 - len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64))

    google_id = payload["sub"]
    email = payload.get("email", "")
    name = payload.get("name", "")
    avatar_url = payload.get("picture")

    user = (
        await session.execute(select(User).where(User.google_id == google_id))
    ).scalar_one_or_none()

    is_new = False
    if user is not None:
        user.email = email
        user.name = name
        user.avatar_url = avatar_url
    else:
        user = User(
            email=email,
            google_id=google_id,
            name=name,
            avatar_url=avatar_url,
        )
        session.add(user)
        is_new = True

    await session.commit()
    await session.refresh(user)
    existing_review_id = (
        await session.execute(select(Review.id).where(Review.user_id == user.id).limit(1))
    ).scalar_one_or_none()
    if is_new or existing_review_id is None:
        await _seed_starter_vocab(session, user)
    else:
        await _heal_starter_vocab_definitions(session)
    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard", status_code=307)


@router.get("/auth/logout")
async def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/", status_code=307)


@router.get("/auth/login-page")
async def login_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "pages/login.html")
