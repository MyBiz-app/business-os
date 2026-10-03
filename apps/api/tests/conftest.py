"""Test fixtures: a fresh database migrated with Alembic, and locally signed access tokens."""

import os
import time
from collections.abc import Callable, Iterator
from uuid import UUID, uuid4

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, make_url, text

from app.core.auth import get_key_source
from app.core.db import get_engine
from app.main import create_app

# Defaults to the local Supabase database server; CI points this at its Postgres service.
SERVER_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://postgres:postgres@127.0.0.1:54322/postgres"
)
STUDIO = {  # a typical first business
    "name": "Studio Flow",
    "vertical": "fitness",
    "locale": "he",
    "time_zone": "Asia/Jerusalem",
    "currency": "ILS",
}

TEST_DB_NAME = "business_os_test"
API_DIR = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    server = create_engine(SERVER_URL, isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)"))
        connection.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    server.dispose()

    url = make_url(SERVER_URL).set(database=TEST_DB_NAME)
    config = Config(os.path.join(API_DIR, "alembic.ini"))
    config.set_main_option("script_location", os.path.join(API_DIR, "migrations"))
    config.attributes["database_url"] = url.render_as_string(hide_password=False)
    command.upgrade(config, "head")

    test_engine = create_engine(url)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(engine: Engine) -> None:
    """Empties every app table before each test, including tables added later."""
    with engine.begin() as connection:
        tables = connection.execute(
            text(
                "SELECT string_agg(format('app.%I', tablename), ', ') FROM pg_tables "
                "WHERE schemaname = 'app'"
            )
        ).scalar_one()
        connection.execute(text(f"TRUNCATE {tables} CASCADE"))


class StaticKeySource:
    def __init__(self, key: object) -> None:
        self.key = key

    def key_for(self, token: str) -> object:
        return self.key


@pytest.fixture(scope="session")
def signing_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


TokenFactory = Callable[..., str]


@pytest.fixture
def make_token(signing_key: ec.EllipticCurvePrivateKey) -> TokenFactory:
    def factory(user_id: UUID, email: str = "", key: object = signing_key) -> str:
        now = int(time.time())
        claims = {
            "sub": str(user_id),
            "email": email or f"{user_id}@example.com",
            "aud": "authenticated",
            "role": "authenticated",
            "iat": now,
            "exp": now + 300,
        }
        return jwt.encode(claims, key, algorithm="ES256")

    return factory


@pytest.fixture
def client(engine: Engine, signing_key: ec.EllipticCurvePrivateKey) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_key_source] = lambda: StaticKeySource(signing_key.public_key())
    with TestClient(app) as test_client:
        yield test_client


AuthHeaders = Callable[..., dict[str, str]]


@pytest.fixture
def auth(make_token: TokenFactory) -> AuthHeaders:
    def headers(user_id: UUID, tenant_id: UUID | str | None = None) -> dict[str, str]:
        result = {"Authorization": f"Bearer {make_token(user_id)}"}
        if tenant_id:
            result["X-Tenant-Id"] = str(tenant_id)
        return result

    return headers


@pytest.fixture
def new_user_id() -> Callable[[], UUID]:
    return uuid4


def add_member(engine: Engine, tenant_id: UUID | str, user_id: UUID, role: str) -> None:
    """Adds a user to a tenant directly in the database (staff invites come later)."""
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO app.users (id, email) VALUES (:id, :email) ON CONFLICT DO NOTHING"),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        connection.execute(
            text("INSERT INTO app.tenant_members (tenant_id, user_id, role) VALUES (:t, :u, :r)"),
            {"t": tenant_id, "u": user_id, "r": role},
        )


@pytest.fixture
def studio(client: TestClient, auth: AuthHeaders, engine: Engine) -> dict:
    owner = uuid4()
    tenant_id = UUID(client.post("/tenants", json=STUDIO, headers=auth(owner)).json()["id"])
    headers = auth(owner, tenant_id)
    service = client.post(
        "/services",
        json={"name": "Pilates", "duration_minutes": 55, "capacity": 12},
        headers=headers,
    ).json()
    location = client.post("/locations", json={"name": "Main"}, headers=headers).json()
    room = client.post(
        f"/locations/{location['id']}/rooms", json={"name": "Studio A"}, headers=headers
    ).json()
    coach = uuid4()
    add_member(engine, tenant_id, coach, "staff")
    return {
        "owner": owner,
        "tenant_id": tenant_id,
        "headers": headers,
        "service": service,
        "location": location,
        "room": room,
        "coach": coach,
    }
