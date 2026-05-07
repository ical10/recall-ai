from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    openrouter_api_key: str
    secret_key: str
    llm_model: str = "z-ai/glm-4.5-air:free"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    google_client_id: str = ""
    google_client_secret: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
