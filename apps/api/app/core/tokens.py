from __future__ import annotations

from uuid import UUID

from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.core.config import get_settings

_BEARER_SALT = "extension-bearer-token"
# 30 days — the extension session must survive browser restarts (PRD), so it
# outlives the 4h web session cookie. Stateless: validity is the signature + age.
_BEARER_MAX_AGE_SECONDS = 60 * 60 * 24 * 30


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(get_settings().secret_key.get_secret_value(), salt=_BEARER_SALT)


def sign_bearer_token(user_id: UUID) -> str:
    """Mint a signed, time-stamped bearer token for the extension to store."""
    return _serializer().dumps(str(user_id))


def verify_bearer_token(token: str) -> UUID | None:
    """Return the user id if the token's signature is valid and unexpired, else None."""
    try:
        raw = _serializer().loads(token, max_age=_BEARER_MAX_AGE_SECONDS)
    except BadSignature:  # covers SignatureExpired (a subclass)
        return None
    try:
        return UUID(str(raw))
    except (ValueError, TypeError):
        return None
