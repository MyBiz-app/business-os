from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from environment variables (and `.env` in local development)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="API_", extra="ignore")

    environment: str = "local"
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
