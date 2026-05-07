import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_loads_required_fields_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://u:p@h/d"
    assert settings.redis_url == "redis://h:6379/0"
    assert settings.llm_api_key == "k"
    assert settings.secret_key == "s"
    assert settings.llm_model == "z-ai/glm-4.5-air:free"
    assert settings.llm_base_url == "https://openrouter.ai/api/v1"
    assert settings.google_client_id == ""
    assert settings.google_client_secret == ""


def test_settings_overrides_llm_defaults_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-4o-mini")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")

    settings = Settings(_env_file=None)

    assert settings.llm_model == "openai/gpt-4o-mini"
    assert settings.llm_base_url == "https://example.test/v1"


def test_settings_missing_required_raises(monkeypatch):
    for key in ("DATABASE_URL", "REDIS_URL", "LLM_API_KEY", "SECRET_KEY"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
