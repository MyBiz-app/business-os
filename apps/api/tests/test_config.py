import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "given",
    [
        "postgresql://user:pw@db.example.com:5432/postgres",
        "postgres://user:pw@db.example.com:5432/postgres",
        "postgresql+psycopg://user:pw@db.example.com:5432/postgres",
    ],
)
def test_database_url_uses_psycopg_driver(given: str) -> None:
    settings = Settings(environment="staging", database_url=given)

    assert settings.database_url == "postgresql+psycopg://user:pw@db.example.com:5432/postgres"


REMOTE_DB = "postgresql://user:pw@db.example.com:5432/postgres"


def test_refuses_to_start_without_environment_on_a_remote_database() -> None:
    with pytest.raises(ValueError, match="not local"):
        Settings(database_url=REMOTE_DB)  # environment defaults to local
    with pytest.raises(ValueError, match="environment must be one of"):
        Settings(environment="prod", database_url=REMOTE_DB)


def test_deployed_environments_and_local_database_are_accepted() -> None:
    assert Settings(environment="production", database_url=REMOTE_DB).rate_limits_on
    assert Settings().environment == "local"


def test_production_without_required_settings_is_listed() -> None:
    from app.core.config import missing_production_settings

    bare = Settings(environment="production", database_url=REMOTE_DB)
    assert missing_production_settings(bare) == [
        "API_JWKS_URL",
        "API_SECRETS_KEY",
        "API_INTERNAL_TOKEN",
        "API_WEB_URL",
        "API_API_URL",
        "API_CORS_ORIGINS",
    ]
    complete = Settings(
        environment="production",
        database_url=REMOTE_DB,
        jwks_url="https://x.supabase.co/auth/v1/.well-known/jwks.json",
        secrets_key="k",
        internal_token="t",
        web_url="https://app.example.com",
        api_url="https://api.example.com",
        cors_origins=["https://app.example.com"],
    )
    assert missing_production_settings(complete) == []
    staging = Settings(environment="staging", database_url=REMOTE_DB)
    assert missing_production_settings(staging) == []


def test_production_app_refuses_to_start_with_missing_settings(monkeypatch) -> None:
    from app.core import config
    from app.main import create_app

    monkeypatch.setattr(
        config,
        "get_settings",
        lambda: Settings(environment="production", database_url=REMOTE_DB),
    )
    monkeypatch.setattr("app.main.get_settings", config.get_settings)
    with pytest.raises(RuntimeError, match="API_SECRETS_KEY"):
        create_app()
