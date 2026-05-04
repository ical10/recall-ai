import pytest
from app.core.config import Settings
from pydantic import ValidationError


def test_settings_loads_required_fields_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://u:p@h/d"
    assert settings.redis_url == "redis://h:6379/0"
    assert settings.anthropic_api_key == "k"
    assert settings.secret_key == "s"
    assert settings.google_client_id == ""
    assert settings.google_client_secret == ""


def test_settings_missing_required_raises(monkeypatch):
    for key in ("DATABASE_URL", "REDIS_URL", "ANTHROPIC_API_KEY", "SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_get_settings_returns_cached_instance(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "k")
    monkeypatch.setenv("SECRET_KEY", "s")

    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2
