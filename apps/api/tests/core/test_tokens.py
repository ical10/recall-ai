from __future__ import annotations

from uuid import uuid4

from app.core import tokens
from app.core.tokens import sign_bearer_token, verify_bearer_token


def test_roundtrip_returns_user_id() -> None:
    uid = uuid4()
    assert verify_bearer_token(sign_bearer_token(uid)) == uid


def test_garbage_token_returns_none() -> None:
    assert verify_bearer_token("not-a-real-token") is None


def test_tampered_token_returns_none() -> None:
    token = sign_bearer_token(uuid4())
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")
    assert verify_bearer_token(tampered) is None


def test_expired_token_returns_none(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(tokens, "_BEARER_MAX_AGE_SECONDS", -1)
    assert verify_bearer_token(sign_bearer_token(uuid4())) is None
