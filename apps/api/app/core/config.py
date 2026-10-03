from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from environment variables (and `.env` in local development)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="API_", extra="ignore")

    environment: str = "local"
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:8081"]  

    # Local defaults match `supabase start`. Other environments set these explicitly.
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
    jwks_url: str = "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json"
    jwt_audience: str = "authenticated"

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Providers hand out plain postgres:// URLs; SQLAlchemy needs the driver named.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
