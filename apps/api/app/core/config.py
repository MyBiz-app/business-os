from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from environment variables (and `.env` in local development)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="API_", extra="ignore")

    environment: str = "local"
    cors_origins: list[str] = [
        "http://localhost:3000",  # the business web app and the marketing site
        "http://localhost:8081",  # the client app (Expo web)
        "http://localhost:8082",  # the business app (Expo web)
        "http://localhost:8083",  # the MyBiz team app (Expo web)
    ]

    # Local defaults match `supabase start`. Other environments set these explicitly.
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
    jwks_url: str = "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json"
    jwt_audience: str = "authenticated"

    # AI assistant. Without a key the assistant is shown as "not set up yet".
    # Without an API key, answer common questions in demo mode instead of being unavailable.
    ai_demo: bool = True
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("API_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")
    )
    ai_model: str = "claude-opus-5-5"

    # Email (used by the send-emails job). "none" sends nothing; "log" prints instead.
    email_provider: str = "none"  # none | log | resend | gmail | smtp
    email_api_key: SecretStr | None = None  # Resend API key, or the SMTP (Gmail app) password
    email_from: str = "MyBiz <no-reply@example.com>"
    email_smtp_host: str = "smtp.gmail.com"  # smtp only; gmail always uses Gmail's server
    email_smtp_port: int = 465
    email_smtp_user: str | None = None  # defaults to the address in email_from
    # Outside services (decision X13, docs/integrations.md): the platform's default provider
    # per capability and its settings as a JSON object; a business can connect its own
    # (settings → Integrations) for payments, invoicing and messaging.
    payments_provider: str = "simulated"
    payments_settings: SecretStr | None = None
    invoicing_provider: str = "internal"
    invoicing_settings: SecretStr | None = None
    messaging_provider: str = "simulated"
    messaging_settings: SecretStr | None = None
    storage_provider: str = "database"
    storage_settings: SecretStr | None = None
    # Encrypts the businesses' provider secrets in the database (a Fernet key).
    secrets_key: SecretStr | None = None

    # Rate limits per caller (app/core/rate_limit.py). Off by default in local development and
    # tests (everything comes from one address there); on everywhere else unless set.
    rate_limits: bool | None = None
    # Behind the hosting proxy, count the first X-Forwarded-For address (the visitor).
    trust_forwarded_for: bool = False

    @property
    def rate_limits_on(self) -> bool:
        if self.rate_limits is not None:
            return self.rate_limits
        return self.environment not in ("local", "test")

    # Public addresses used in emails (links to the web app and the client app).
    web_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"  # this API's public address (signed file links)
    client_app_url: str = "http://localhost:8081"
    business_app_url: str = "http://localhost:8082"
    staff_app_url: str = "http://localhost:8083"

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
