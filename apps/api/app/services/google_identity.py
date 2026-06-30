from __future__ import annotations

import logging
from dataclasses import dataclass

from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class InvalidGoogleToken(Exception):
    """A Google id_token failed signature, claim, or audience verification."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str
    picture: str | None


def _allowed_audiences() -> set[str]:
    settings = get_settings()
    return {aud for aud in (settings.google_client_id, settings.google_extension_client_id) if aud}


def verify_google_id_token(
    raw: str, *, allowed_audiences: set[str] | None = None
) -> GoogleIdentity:
    """Verify a Google id_token and return the trusted identity, else raise.

    google-auth validates the signature against Google's JWKS plus the issuer and
    expiry; on top of that we require the audience to be one of our OAuth clients
    (web or extension). The `allowed_audiences` override exists so callers/tests can
    inject the set instead of reading settings.
    """
    allowed = allowed_audiences if allowed_audiences is not None else _allowed_audiences()
    if not allowed:
        raise InvalidGoogleToken("no Google client audiences configured")

    try:
        claims = google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            raw, google_requests.Request()
        )
    except (ValueError, GoogleAuthError) as exc:
        raise InvalidGoogleToken(f"token verification failed: {exc}") from exc

    if claims.get("aud") not in allowed:
        raise InvalidGoogleToken("token audience is not an allowed client")
    sub = claims.get("sub")
    if not sub:
        raise InvalidGoogleToken("token missing subject")

    return GoogleIdentity(
        sub=str(sub),
        email=str(claims.get("email", "")),
        name=str(claims.get("name", "")),
        picture=claims.get("picture"),
    )
