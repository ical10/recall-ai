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
    google_redirect_uri: str
    google_extension_client_id: str = ""
    session_https_only: bool = False
    voice_agent_provider: str = ""
    voice_agent_api_key: SecretStr = SecretStr("")
    voice_agent_model: str = "en-US-Standard-H"
    r2_access_key_id: str = ""
    r2_secret_access_key: SecretStr = SecretStr("")
    r2_bucket: str = ""
    r2_endpoint: str = ""
    r2_public_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue]
