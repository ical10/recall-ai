from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str
    llm_api_key: SecretStr
    llm_base_url: str
    llm_model: str
    secret_key: SecretStr
    google_client_id: str = ""
    google_client_secret: SecretStr = SecretStr("")
    google_redirect_uri: str = "http://localhost:8000/auth/callback"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
