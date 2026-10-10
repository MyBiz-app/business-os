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
