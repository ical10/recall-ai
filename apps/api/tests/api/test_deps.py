from fastapi.testclient import TestClient

from app.api.deps import DEV_USER_EMAIL


def test_get_current_user_creates_dev_user_when_absent(probe_client: TestClient) -> None:
    assert probe_client.get("/_user_count").json()["count"] == 0

    response = probe_client.get("/_probe")

    assert response.status_code == 200
    assert response.json()["email"] == DEV_USER_EMAIL
    assert probe_client.get("/_user_count").json()["count"] == 1


def test_get_current_user_is_idempotent(probe_client: TestClient) -> None:
    first = probe_client.get("/_probe").json()
    second = probe_client.get("/_probe").json()

    assert first["id"] == second["id"]
    assert probe_client.get("/_user_count").json()["count"] == 1


def test_get_current_user_returns_existing_row_when_present(probe_client: TestClient) -> None:
    seeded = probe_client.post("/_seed_dev_user").json()

    fetched = probe_client.get("/_probe").json()

    assert fetched["id"] == seeded["id"]
    assert fetched["email"] == DEV_USER_EMAIL
    assert probe_client.get("/_user_count").json()["count"] == 1


def test_get_current_user_recovers_when_concurrent_insert_wins_race() -> None:
    """If a parallel request commits the dev user between our SELECT and our
    INSERT, the failing INSERT must rollback and re-fetch instead of bubbling.
    Mock-based since SQLite serializable reads can't reproduce the race
    in-process."""
    import asyncio
    import uuid
    from unittest.mock import AsyncMock, MagicMock

    from sqlalchemy.exc import IntegrityError

    from app.api.deps import get_current_user
    from app.models.user import User

    winner = User(
        id=uuid.uuid4(),
        email=DEV_USER_EMAIL,
        google_id="dev-local",
        name="Dev",
    )

    first_select = MagicMock()
    first_select.scalar_one_or_none = MagicMock(return_value=None)
    second_select = MagicMock()
    second_select.scalar_one = MagicMock(return_value=winner)
    second_select.scalar_one_or_none = MagicMock(return_value=winner)

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[first_select, second_select])
    session.commit = AsyncMock(side_effect=IntegrityError("simulated", {}, Exception("race")))
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()

    user = asyncio.run(get_current_user(session))

    assert user is winner
    session.rollback.assert_awaited_once()


def test_user_dep_aliases_get_current_user() -> None:
    from typing import get_args

    from fastapi import Depends

    from app.api.deps import UserDep, get_current_user
    from app.models.user import User

    args = get_args(UserDep)
    assert args[0] is User
    dep_type = type(Depends(get_current_user))
    assert any(isinstance(arg, dep_type) and arg.dependency is get_current_user for arg in args[1:])


def test_templates_points_to_apps_api_templates_directory() -> None:
    from pathlib import Path

    from fastapi.templating import Jinja2Templates

    from app.api.deps import TEMPLATES_DIR, templates

    assert isinstance(templates, Jinja2Templates)
    expected = Path(__file__).resolve().parent.parent.parent / "templates"
    assert expected == TEMPLATES_DIR
    assert str(expected) in templates.env.loader.searchpath  # type: ignore[union-attr]
    templates.get_template("base.html")
