import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_loads_required_fields_from_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "z-ai/glm-4.5-air:free")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+asyncpg://u:p@h/d"
    assert settings.redis_url == "redis://h:6379/0"
    assert settings.llm_api_key.get_secret_value() == "k"
    assert settings.llm_base_url == "https://openrouter.ai/api/v1"
    assert settings.llm_model == "z-ai/glm-4.5-air:free"
    assert settings.secret_key.get_secret_value() == "s"
    assert settings.google_client_id == ""
    assert settings.google_client_secret.get_secret_value() == ""


def test_settings_missing_required_raises(monkeypatch):
    required = (
        "DATABASE_URL",
        "REDIS_URL",
        "LLM_API_KEY",
        "LLM_BASE_URL",
        "LLM_MODEL",
        "SECRET_KEY",
    )
    for key in required:
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_missing_llm_model_raises(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.delenv("LLM_MODEL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_missing_llm_base_url_raises(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.setenv("LLM_MODEL", "z-ai/glm-4.5-air:free")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_missing_llm_api_key_raises(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("REDIS_URL", "redis://h:6379/0")
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("LLM_MODEL", "z-ai/glm-4.5-air:free")
    monkeypatch.setenv("SECRET_KEY", "s")
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)
