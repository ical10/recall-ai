"""Tests for the Google identity verification seam (verify-only).

The signature/issuer/expiry checks belong to google-auth; here we test the seam's
own logic — audience allow-list, missing subject, and error wrapping — by mocking
`verify_oauth2_token` and injecting the allowed audiences.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services import google_identity
from app.services.google_identity import (
    GoogleIdentity,
    InvalidGoogleToken,
    verify_google_id_token,
)

VALID_CLAIMS = {
    "iss": "https://accounts.google.com",
    "aud": "web-client",
    "sub": "google-123",
    "email": "learner@example.com",
    "name": "Learner",
    "picture": "https://example.com/avatar.png",
}


def _mock_verify(return_value=None, side_effect=None):  # type: ignore[no-untyped-def]
    return patch.object(
        google_identity.google_id_token,
        "verify_oauth2_token",
        return_value=return_value,
        side_effect=side_effect,
    )


def test_returns_identity_for_valid_token() -> None:
    with _mock_verify(return_value=VALID_CLAIMS):
        identity = verify_google_id_token("raw", allowed_audiences={"web-client"})
    assert identity == GoogleIdentity(
        sub="google-123",
        email="learner@example.com",
        name="Learner",
        picture="https://example.com/avatar.png",
    )


def test_accepts_extension_audience() -> None:
    with _mock_verify(return_value={**VALID_CLAIMS, "aud": "ext-client"}):
        identity = verify_google_id_token("raw", allowed_audiences={"web-client", "ext-client"})
    assert identity.sub == "google-123"


def test_rejects_audience_not_allowed() -> None:
    with (
        _mock_verify(return_value={**VALID_CLAIMS, "aud": "attacker-client"}),
        pytest.raises(InvalidGoogleToken),
    ):
        verify_google_id_token("raw", allowed_audiences={"web-client"})


def test_rejects_when_google_auth_raises() -> None:
    with _mock_verify(side_effect=ValueError("Token expired")), pytest.raises(InvalidGoogleToken):
        verify_google_id_token("raw", allowed_audiences={"web-client"})


def test_rejects_missing_subject() -> None:
    with (
        _mock_verify(return_value={**VALID_CLAIMS, "sub": ""}),
        pytest.raises(InvalidGoogleToken),
    ):
        verify_google_id_token("raw", allowed_audiences={"web-client"})


def test_rejects_when_no_audiences_configured() -> None:
    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token("raw", allowed_audiences=set())
