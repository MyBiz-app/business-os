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
    settings = Settings(database_url=given)

    assert settings.database_url == "postgresql+psycopg://user:pw@db.example.com:5432/postgres"
