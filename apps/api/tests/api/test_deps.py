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


def test_templates_points_to_apps_api_templates_directory() -> None:
    from pathlib import Path

    from fastapi.templating import Jinja2Templates

    from app.api.deps import templates

    assert isinstance(templates, Jinja2Templates)
    expected = Path(__file__).resolve().parent.parent.parent / "templates"
    assert (expected / "base.html").is_file()
    rendered = templates.get_template("base.html")
    assert rendered is not None
