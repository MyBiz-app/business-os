import datetime as dt
from functools import lru_cache
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.brand import EMAILS as BRAND_EMAILS
from app.core.brand import NAME as BRAND_NAME

ENVIRONMENTS = ("local", "test", "staging", "production")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "host.docker.internal", None}


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
    # Background jobs switch to this role after connecting; empty runs them as the login itself.
    jobs_db_role: str = "app_jobs"
    jwks_url: str = "http://127.0.0.1:54321/auth/v1/.well-known/jwks.json"
    jwt_audience: str = "authenticated"

    # AI assistant. Without a key the assistant is shown as "not set up yet".
    # Without an API key, answer common questions in demo mode instead of being unavailable.
    ai_demo: bool = True
    anthropic_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("API_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY")
    )
    # Other vendors (OpenAI, Gemini) are built but off. Switching one on takes all three: the
    # vendor in API_AI_ENABLED_VENDORS, its key, and API_AI_PROVIDER naming it
    # (docs/deploy/go-live-checklist.md).
    ai_provider: str = "anthropic"  # anthropic | openai | gemini
    ai_enabled_vendors: str = ""  # comma separated extras, e.g. "openai,gemini"
    openai_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("API_OPENAI_API_KEY", "OPENAI_API_KEY")
    )
    gemini_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("API_GEMINI_API_KEY", "GEMINI_API_KEY")
    )
    # Everyday questions run on the cheap model; a turn that needs many tool calls escalates to
    # the stronger one (P0-6). Prices live in app/ai/gateway.py.
    ai_model: str = "claude-haiku-5-5"
    ai_strong_model: str = "claude-sonnet-5-5"
    # The top tier, used only when the console or the owner asks for it (never automatically).
    ai_top_model: str = "claude-opus-5-5"
    ai_escalate_after_steps: int = (
        3  # model calls in one message before switching to the strong model
    )
    ai_max_tokens: int = 4096  # per model call
    ai_timeout_seconds: float = 60.0
    # Per user, so one account (or a stolen session) cannot hammer the model: fixed windows.
    ai_user_messages_per_minute: int = 6
    ai_user_messages_per_hour: int = 60
    # Platform-wide spend alarm shown in the console: AI credits (a credit is one US cent) per
    # UTC day.
    ai_daily_alert_credits: int = 2000

    # Removing a person's sign-in when they delete their account in the app. Without both, only
    # their profile is emptied (the sign-in stays at Supabase); set them at go-live.
    supabase_url: str | None = None
    supabase_service_key: SecretStr | None = None

    # Error monitoring (Sentry). Without a DSN nothing is sent and nothing is loaded.
    sentry_dsn: SecretStr | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    sentry_release: str | None = None  # defaults to the commit Render deployed (RENDER_GIT_COMMIT)

    # Turning a branch's address into a point on the map (R34): "nominatim" (OpenStreetMap, free,
    # one request per saved address) or "none". Tests and local work run with "none".
    geocoder: str = "nominatim"
    geocoder_user_agent: str = f"{BRAND_NAME} business-os geocoder"

    # Email (used by the send-emails job). "none" sends nothing; "log" prints instead.
    email_provider: str = "none"  # none | log | resend | gmail | smtp
    push_provider: str = "expo"  # expo | log | off: push notifications to staff phones
    expo_access_token: SecretStr | None = None  # optional; only if Expo enhanced security is on
    email_api_key: SecretStr | None = None  # Resend API key, or the SMTP (Gmail app) password
    email_from: str = f"{BRAND_NAME} <{BRAND_EMAILS['sender']}>"
    # Resend's signing secret ("whsec_...") for /webhooks/email/resend (bounces, complaints).
    email_webhook_secret: SecretStr | None = None
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
    # Virus scanning of uploads (GL3): "none" (off) or "clamav" (a clamd daemon at host:port).
    file_scan_provider: str = "none"
    file_scan_host: str = "127.0.0.1"
    file_scan_port: int = 3310
    # Encrypts the businesses' provider secrets in the database (a Fernet key).
    secrets_key: SecretStr | None = None
    # Key rotation (GL6): a comma-separated list, newest first. The first key encrypts, every
    # key decrypts. When set it replaces `secrets_key`.
    secrets_keys: SecretStr | None = None
    # Pins the key behind the ID-number hashes (they cannot be re-keyed without recomputing, see
    # docs/runbooks/key-rotation.md). While unset the oldest of the secret keys is used.
    id_hash_key: SecretStr | None = None

    # Meta connector (content studio): the Meta app's id and secret, and the Threads app's own
    # pair. While missing, the networks stay "coming soon" and nothing breaks.
    meta_app_id: str | None = None
    meta_app_secret: SecretStr | None = None
    meta_threads_app_id: str | None = None
    meta_threads_app_secret: SecretStr | None = None
    # YouTube / Google Business Profile and TikTok connectors (content studio). Redirect URIs to
    # register: {API_API_URL}/social/callback/youtube, .../google_business and .../tiktok.
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: SecretStr | None = None
    tiktok_client_key: str | None = None
    tiktok_client_secret: SecretStr | None = None
    meta_graph_version: str = "v26.0"

    # Connection pool, per API worker process. Keep workers * (pool_size + max_overflow) under the
    # database's (or pooler's) client limit. Prepared statements are off by default so the URL can
    # point at a transaction-mode pooler (Supavisor, port 6543); every transaction here is
    # self-contained (`SET LOCAL`), so both pooler modes work.
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: float = 15.0  # seconds to wait for a free connection before failing
    db_pool_recycle: int = 1800  # seconds; replaces connections the pooler may have closed
    db_prepared_statements: bool = False

    # Model calls hold a request thread for seconds: at most this many run at once per worker,
    # the rest get "busy" (429) instead of using up the threads other requests need.
    ai_max_concurrent_calls: int = 8

    # Statements slower than this (milliseconds) are logged; 0 turns it off.
    slow_query_ms: int = 500

    # Rate limits per caller (app/core/rate_limit.py). Off by default in local development and
    # tests (everything comes from one address there); on everywhere else unless set.
    rate_limits: bool | None = None
    # Behind the hosting proxy, count the right-most X-Forwarded-For address (added by the proxy).
    trust_forwarded_for: bool = False
    # Shared with the web server, which then names the real visitor in X-Visitor-Address.
    internal_token: SecretStr | None = None

    # Shared rate-limit counts for several API instances (redis://…). Unset: counts per process.
    rate_limit_redis_url: SecretStr | None = None

    # Signed-in requests one business may make per minute (staff and clients together); 0 turns
    # the business ceiling off. Counted in the same store as the address limits.
    tenant_rate_limit_per_minute: int = 600

    # AI connectors (MCP): calls per business in a rolling 24 hours, over every connection (R37a);
    # 0 turns the ceiling off. How long a token lives.
    mcp_daily_calls_per_business: int = 600
    mcp_access_token_minutes: int = 60
    mcp_refresh_token_days: int = 90

    @property
    def rate_limits_on(self) -> bool:
        if self.rate_limits is not None:
            return self.rate_limits
        return self.environment not in ("local", "test")

    # Two-step sign-in (app/core/mfa.py). Off in local development and tests like the rate
    # limits; on everywhere else unless set. Owners' and managers' sensitive actions need a code
    # from `mfa_required_from` on (none: from the start), the MyBiz team and businesses that
    # require it of their team always do.
    mfa_enforced: bool | None = None
    mfa_required_from: dt.date | None = None
    # Comma-separated emails of demo owners who may browse staging without a code. Only read on
    # staging: production and local ignore it (see `mfa_exempt`).
    mfa_demo_exempt_emails: str = ""

    def mfa_exempt(self, email: str) -> bool:
        if self.environment != "staging" or not email:
            return False
        listed = {part.strip().lower() for part in self.mfa_demo_exempt_emails.split(",")}
        return email.strip().lower() in listed

    @property
    def mfa_on(self) -> bool:
        if self.mfa_enforced is not None:
            return self.mfa_enforced
        return self.environment not in ("local", "test")

    # Public addresses used in emails (links to the web app and the client app).
    web_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"  # this API's public address (signed file links)
    client_app_url: str = "http://localhost:8081"
    business_app_url: str = "http://localhost:8082"
    staff_app_url: str = "http://localhost:8083"

    @model_validator(mode="after")
    def refuse_unsafe_environment(self) -> "Settings":
        # Fail closed: a missing or mistyped API_ENVIRONMENT must not leave a deployment on the
        # public development key with rate limits off. Local/test only run against a local database.
        if self.environment not in ENVIRONMENTS:
            raise ValueError(f"environment must be one of {', '.join(ENVIRONMENTS)}")
        if self.environment in ("local", "test") and (
            urlparse(self.database_url).hostname not in LOCAL_HOSTS
        ):
            raise ValueError(
                "API_ENVIRONMENT is local/test (or unset) but the database is not local; "
                "set API_ENVIRONMENT to staging or production"
            )
        return self

    def secret_keys(self) -> list[str]:
        """The encryption keys, newest first: `API_SECRETS_KEYS`, else `API_SECRETS_KEY`."""
        if self.secrets_keys is not None:
            return [
                key.strip()
                for key in self.secrets_keys.get_secret_value().split(",")
                if key.strip()
            ]
        return [self.secrets_key.get_secret_value()] if self.secrets_key is not None else []

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, value: str) -> str:
        # Providers hand out plain postgres:// URLs; SQLAlchemy needs the driver named.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value.removeprefix(prefix)
        return value


def missing_production_settings(settings: Settings) -> list[str]:
    """Names of the settings a production API must not start without: a default would point it at
    local addresses, leave provider secrets unencrypted or let the web app's visitor header be
    forged. Empty outside production."""
    if settings.environment != "production":
        return []
    local = ("localhost", "127.0.0.1", "::1")
    missing: list[str] = []
    if urlparse(settings.jwks_url).hostname in local:
        missing.append("API_JWKS_URL")
    if not settings.secret_keys():
        missing.append("API_SECRETS_KEY")
    if settings.internal_token is None:
        missing.append("API_INTERNAL_TOKEN")
    for name, value in (("API_WEB_URL", settings.web_url), ("API_API_URL", settings.api_url)):
        if urlparse(value).hostname in local:
            missing.append(name)
    if not settings.cors_origins or any(
        urlparse(origin).hostname in local for origin in settings.cors_origins
    ):
        missing.append("API_CORS_ORIGINS")
    return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()
